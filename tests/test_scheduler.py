"""Exercise serial execution, failure recovery and bounded shutdown."""

from __future__ import annotations

import argparse
import fcntl
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from threading import Event
from unittest.mock import patch

from scheduler import positive_seconds, run_command, schedule


class SchedulerTests(unittest.TestCase):
    """Verify process behavior rather than duplicating the source tests."""

    def test_child_exit_status(self) -> None:
        """A failed finite command is not reported as successful."""
        self.assertTrue(run_command([sys.executable, "-c", "pass"], 5, Event()))
        self.assertFalse(
            run_command([sys.executable, "-c", "raise SystemExit(1)"], 5, Event()),
        )

    def test_deadline_and_shutdown_stop_child(self) -> None:
        """A hanging collector cannot block its scheduler indefinitely."""
        for stop_before_start in (False, True):
            with self.subTest(stop_before_start=stop_before_start):
                stopped = Event()
                if stop_before_start:
                    stopped.set()
                self.assertFalse(
                    run_command(
                        [sys.executable, "-c", "import time; time.sleep(60)"],
                        1,
                        stopped,
                    ),
                )

    def test_shutdown_does_not_log_failure_or_wait(self) -> None:
        """An intentional stop during a run exits quietly without scheduling a retry."""
        stopped = Event()

        def stop_during_run(*_args: object) -> bool:
            stopped.set()
            return False

        with (
            patch("scheduler.run_command", side_effect=stop_during_run),
            patch.object(stopped, "wait") as wait,
            self.assertNoLogs("scheduler", level="WARNING"),
        ):
            schedule({"example": ["collector"]}, 600, 10, stopped)
            wait.assert_not_called()

    def test_stopping_child_does_not_warn(self) -> None:
        """Intentional child termination must not look like a deadline failure."""
        stopped = Event()
        stopped.set()
        with self.assertNoLogs("scheduler", level="WARNING"):
            self.assertFalse(
                run_command(
                    [sys.executable, "-c", "import time; time.sleep(60)"],
                    1,
                    stopped,
                ),
            )

    def test_failure_waits_before_retry(self) -> None:
        """Source failures do not create a tight retry loop."""
        stopped = Event()
        with (
            patch("scheduler.run_command", side_effect=[False, True]) as command,
            patch.object(stopped, "wait") as wait,
        ):
            calls = 0
            clock = 0.0

            def wait_and_stop(seconds: float) -> bool:
                nonlocal calls, clock
                calls += 1
                clock += seconds
                if calls == 2:
                    stopped.set()
                return stopped.is_set()

            wait.side_effect = wait_and_stop
            with patch("scheduler.monotonic", side_effect=lambda: clock):
                schedule({"example": ["collector"]}, 600, 10, stopped)
            self.assertEqual(command.call_count, 2)
            self.assertEqual(wait.call_count, 2)
            self.assertEqual([call.args[0] for call in wait.call_args_list], [300, 600])

    def test_failed_city_does_not_skip_or_refetch_the_successful_city(self) -> None:
        """One process schedules independent retries without another container."""
        stopped = Event()
        clock = 0.0
        waits = []

        def advance(seconds: float) -> bool:
            nonlocal clock
            waits.append(seconds)
            clock += seconds
            if len(waits) == 2:
                stopped.set()
            return stopped.is_set()

        with (
            patch("scheduler.monotonic", side_effect=lambda: clock),
            patch("scheduler.run_command", side_effect=[False, True, True]) as run,
            patch.object(stopped, "wait", side_effect=advance),
        ):
            schedule(
                {"a": ["collector", "a"], "b": ["collector", "b"]}, 600, 10, stopped
            )
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["collector", "a"],
                ["collector", "b"],
                ["collector", "a"],
            ],
        )
        self.assertEqual(waits, [300, 300])

    def test_shared_volume_rejects_second_scheduler(self) -> None:
        """A second container using the same volume cannot start another collector."""
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "collector.lock"
            with lock_path.open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = subprocess.run(  # noqa: S603
                    [
                        sys.executable,
                        str(Path(__file__).parents[1] / "scheduler.py"),
                        "--lock",
                        str(lock_path),
                        "--",
                        sys.executable,
                        "-c",
                        "print('must not run')",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                )
                self.assertEqual(result.returncode, 1)
                self.assertIn("Scheduler unavailable", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_rejects_nonpositive_intervals(self) -> None:
        """Configuration cannot accidentally busy-loop or disable the deadline."""
        for value in ("0", "-1"):
            with (
                self.subTest(value=value),
                self.assertRaises(argparse.ArgumentTypeError),
            ):
                positive_seconds(value)


if __name__ == "__main__":
    unittest.main()

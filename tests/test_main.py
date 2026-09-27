"""Offline coverage for the safe command and retained legacy entrypoint."""

import contextlib
import io
import os
import subprocess
import sys
import unittest
from unittest.mock import AsyncMock, patch

import main
from app.cities.germany import hamburg
from app.cities.netherlands import amsterdam


class CommandTests(unittest.TestCase):
    """Check execution boundaries without contacting providers or MySQL."""

    def test_import_and_default_command_need_no_environment_or_network(self) -> None:
        """A fresh process must not load the legacy database module."""
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import socket; from unittest.mock import patch; "
                    'guard = patch.object(socket.socket, "connect", '
                    'side_effect=AssertionError("Unexpected network access")); '
                    "guard.start(); import main; main.main([]); "
                    'import sys; sys.exit("app.database" in sys.modules)'
                ),
            ],
            env={},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--fetch", result.stdout)

    def test_fetch_uses_package_clients_once_without_writes(self) -> None:
        """Keep parsing in the packages and accept empty source responses."""
        for city, module, client_name, method, kwargs, records in (
            ("amsterdam", amsterdam, "ODPAmsterdam", "all_garages", {}, [object()]),
            ("hamburg", hamburg, "UDPHamburg", "park_and_rides", {"limit": 40}, []),
        ):
            with (
                self.subTest(city=city),
                patch.object(module, client_name) as client_class,
                patch.object(module.Municipality, "upload_data") as upload,
                patch("pymysql.connect") as database,
                patch("main.load_dotenv") as dotenv,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                client = client_class.return_value.__aenter__.return_value
                fetch = AsyncMock(return_value=records)
                setattr(client, method, fetch)
                self.assertEqual(main.main(["--fetch", city]), 0)
                fetch.assert_awaited_once_with(**kwargs)
                upload.assert_not_called()
                database.assert_not_called()
                dotenv.assert_not_called()
                self.assertIn(f"{len(records)} source records", output.getvalue())

    def test_failed_fetch_does_not_write_or_report_success(self) -> None:
        """Provider failures propagate to a nonzero process exit."""
        with (
            patch.object(
                amsterdam.Municipality,
                "async_get_locations",
                side_effect=RuntimeError("Source unavailable"),
            ),
            patch.object(amsterdam.Municipality, "upload_data") as upload,
            contextlib.redirect_stdout(io.StringIO()) as output,
            self.assertRaisesRegex(RuntimeError, "Source unavailable"),
        ):
            main.main(["--fetch", "amsterdam"])
        upload.assert_not_called()
        self.assertNotIn("source records retrieved", output.getvalue())

    def test_invalid_modes_fail_before_any_work(self) -> None:
        """Reject unknown cities and combined read/write modes."""
        for args in (["--fetch", "unknown"], ["--fetch", "hamburg", "--legacy"]):
            with (
                self.subTest(args=args),
                patch("main.run_legacy") as legacy,
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                main.main(args)
            self.assertEqual(error.exception.code, 2)
            legacy.assert_not_called()

    def test_legacy_loads_environment_before_reading_settings(self) -> None:
        """A dotenv-only deployment must work without import-time settings."""

        def load_settings() -> None:
            os.environ.update(CITY="Amsterdam", WAIT_TIME="10")

        with (
            patch.dict(os.environ, {}, clear=True),
            patch("main.load_dotenv", side_effect=load_settings),
            patch("main.run_legacy") as legacy,
        ):
            self.assertEqual(main.main(["--legacy"]), 0)
            legacy.assert_called_once_with("amsterdam", 10)

    def test_legacy_rejects_invalid_settings_before_writing(self) -> None:
        """Missing, nonnumeric and nonpositive intervals cannot start the loop."""
        for settings in (
            {},
            {"CITY": "unknown", "WAIT_TIME": "10"},
            *(
                {"CITY": "hamburg", "WAIT_TIME": value}
                for value in ("", "invalid", "0", "-1")
            ),
        ):
            with (
                self.subTest(settings=settings),
                patch.dict(os.environ, settings, clear=True),
                patch("main.load_dotenv"),
                patch("main.run_legacy") as legacy,
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                main.main(["--legacy"])
            self.assertEqual(error.exception.code, 2)
            legacy.assert_not_called()

    def test_legacy_preserves_updates_interval_and_hamburg_quiet_hour(self) -> None:
        """Only the explicit writer retains continuous updates and the pause."""
        for city, hour, expected_calls in (
            ("amsterdam", 0, 1),
            ("hamburg", 0, 0),
            ("hamburg", 1, 1),
        ):
            with (
                self.subTest(city=city, hour=hour),
                patch("main.CityProvider.provide_city") as provider,
                patch("main.datetime") as clock,
                patch(
                    "main.time.sleep", side_effect=RuntimeError("Stop loop")
                ) as sleep,
                contextlib.redirect_stdout(io.StringIO()),
                self.assertRaisesRegex(RuntimeError, "Stop loop"),
            ):
                clock.now.return_value.hour = hour
                clock.now.return_value.strftime.return_value = "01:00:00"
                provider.return_value.async_get_locations = AsyncMock(return_value=[])
                main.run_legacy(city, 10)
            self.assertEqual(
                provider.return_value.async_get_locations.await_count,
                expected_calls,
            )
            self.assertEqual(
                provider.return_value.upload_data.call_count, expected_calls
            )
            if expected_calls:
                provider.return_value.upload_data.assert_called_once_with(
                    [], "01:00:00"
                )
            sleep.assert_called_once_with(600)

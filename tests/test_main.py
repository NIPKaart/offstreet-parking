"""Offline boundaries for the unified private-R2 entry point."""

import contextlib
import io
import subprocess
import sys
import unittest
from unittest.mock import patch

import main


class CommandTests(unittest.TestCase):
    """Inspection no longer provides a second source-fetch path."""

    def test_default_command_needs_no_environment_or_network(self) -> None:
        """Default help never requires bucket credentials."""
        result = subprocess.run(
            [sys.executable, "main.py"],
            env={},
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--city", result.stdout)
        self.assertIn("--kind", result.stdout)

    def test_explicit_arguments_use_r2_collector(self) -> None:
        """The compatibility entry point forwards the selection and exit code."""
        with patch.object(main, "collect", return_value=1) as collect:
            self.assertEqual(main.main(["--city", "hamburg"]), 1)
        collect.assert_called_once_with(["--city", "hamburg"])

    def test_old_inspection_and_unknown_sources_are_rejected(self) -> None:
        """Removed fetch mode cannot bypass complete R2 delivery."""
        for args in (["--fetch", "hamburg"], ["--city", "unknown"]):
            with (
                self.subTest(args=args),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                main.main(args)
            self.assertEqual(error.exception.code, 2)

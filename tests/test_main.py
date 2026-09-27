"""Offline coverage for credential-free source inspection."""

import contextlib
import io
import socket
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
                patch.object(
                    socket.socket,
                    "connect",
                    side_effect=AssertionError("Unexpected network access"),
                ),
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                client = client_class.return_value.__aenter__.return_value
                fetch = AsyncMock(return_value=records)
                setattr(client, method, fetch)
                self.assertEqual(main.main(["--fetch", city]), 0)
                fetch.assert_awaited_once_with(**kwargs)
                self.assertIn(f"{len(records)} source records", output.getvalue())

    def test_failed_fetch_does_not_write_or_report_success(self) -> None:
        """Provider failures propagate to a nonzero process exit."""
        with (
            patch.object(
                amsterdam.Municipality,
                "async_get_locations",
                side_effect=RuntimeError("Source unavailable"),
            ),
            contextlib.redirect_stdout(io.StringIO()) as output,
            self.assertRaisesRegex(RuntimeError, "Source unavailable"),
        ):
            main.main(["--fetch", "amsterdam"])
        self.assertNotIn("source records retrieved", output.getvalue())

    def test_invalid_modes_fail_before_any_work(self) -> None:
        """Reject unknown cities and attempts to start a removed writer."""
        for args in (["--fetch", "unknown"], ["--legacy"]):
            with (
                self.subTest(args=args),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                main.main(args)
            self.assertEqual(error.exception.code, 2)

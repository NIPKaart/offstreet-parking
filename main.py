"""Compatibility entry point for the private-R2 offstreet collector."""

import sys

from collector import main as collect


def main(argv: list[str] | None = None) -> int:
    """Keep offline help as the default; explicit arguments use the R2 collector."""
    arguments = sys.argv[1:] if argv is None else argv
    return collect(arguments or ["--help"])


if __name__ == "__main__":
    raise SystemExit(main())

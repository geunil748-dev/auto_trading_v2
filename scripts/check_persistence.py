"""Compatibility entry point for the official DotNet persistence diagnostic."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_dotnet_persistence import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())

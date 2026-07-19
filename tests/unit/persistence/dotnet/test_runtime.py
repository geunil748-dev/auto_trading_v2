from __future__ import annotations

import subprocess
import sys

from auto_trading_v2.adapters.persistence.dotnet.runtime import load_sqlclient_runtime


def test_module_import_does_not_load_pythonnet_or_clr() -> None:
    code = (
        "import sys; "
        "import auto_trading_v2.adapters.persistence.dotnet.runtime; "
        "print(int('pythonnet' in sys.modules), int('clr' in sys.modules))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stdout.strip() == "0 0"


def test_explicit_netfx_load_is_idempotent_and_sanitized() -> None:
    first = load_sqlclient_runtime()
    second = load_sqlclient_runtime()

    assert first is second
    assert first.provider == "dotnet"
    assert first.runtime_kind == ".NET Framework"
    assert first.runtime_version == "4.0.30319.42000"
    assert first.process_bitness == 64
    assert "\\" not in repr(first)

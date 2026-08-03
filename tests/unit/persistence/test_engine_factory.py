from typing import Any, cast

from sqlalchemy import Engine

from auto_trading_v2.adapters.persistence import engine as engine_module
from auto_trading_v2.config import DatabaseSettings, SecretValue


def test_engine_factory_is_lazy_and_uses_safe_options(monkeypatch: Any) -> None:
    calls: list[tuple[object, dict[str, object]]] = []
    sentinel = object()

    def fake_create_engine(url: object, **options: object) -> object:
        calls.append((url, options))
        return sentinel

    monkeypatch.setattr(engine_module, "create_engine", fake_create_engine)
    settings = DatabaseSettings(
        database_url=SecretValue("mssql+pyodbc://example/auto_trading_v2"),
        admin_url=None,
        test_admin_url=None,
    )

    engine = engine_module.create_mssql_engine(settings)

    assert engine is cast(Engine, sentinel)
    assert len(calls) == 1
    assert calls[0][1] == {
        "echo": False,
        "hide_parameters": True,
        "pool_pre_ping": True,
    }

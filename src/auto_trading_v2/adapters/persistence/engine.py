"""Explicit lazy MSSQL engine construction boundary."""

from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url

from auto_trading_v2.config import DatabaseSettings


def create_mssql_engine(database_settings: DatabaseSettings) -> Engine:
    """Build an engine from validated settings without opening a connection."""

    url = make_url(database_settings.database_url.reveal())
    return create_engine(
        url,
        echo=False,
        hide_parameters=True,
        pool_pre_ping=True,
    )

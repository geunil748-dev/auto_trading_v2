"""Reuse the guarded temporary MSSQL fixture without duplicating lifecycle code."""

from tests.integration.persistence.conftest import mssql_database

__all__ = ["mssql_database"]

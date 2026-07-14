"""Reuse the guarded PR2/PR4 temporary MSSQL fixture without duplicating lifecycle code."""

from tests.integration.persistence.conftest import mssql_database as mssql_database

__all__ = ["mssql_database"]

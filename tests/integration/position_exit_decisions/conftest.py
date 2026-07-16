"""Function-isolated MSSQL database for position-exit integration tests."""

from collections.abc import Iterator

import pytest

from tests.integration.persistence.conftest import (
    TemporaryMssqlDatabase,
    temporary_mssql_database,
)


@pytest.fixture
def mssql_database() -> Iterator[TemporaryMssqlDatabase]:
    with temporary_mssql_database() as database:
        yield database

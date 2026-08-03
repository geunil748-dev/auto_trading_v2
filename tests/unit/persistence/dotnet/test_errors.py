import pytest
from sqlalchemy.exc import IntegrityError

from auto_trading_v2.adapters.persistence.dotnet.errors import (
    DotNetErrorCategory,
    classify_sql_number,
    safe_persistence_error,
    translate_dotnet_error,
)
from auto_trading_v2.adapters.persistence.errors import translate_persistence_error
from auto_trading_v2.application.errors import (
    CheckConstraintViolationError,
    ForeignKeyViolationError,
    PersistenceError,
)


@pytest.mark.parametrize(
    ("number", "category"),
    [
        (2601, DotNetErrorCategory.UNIQUE_VIOLATION),
        (2627, DotNetErrorCategory.UNIQUE_VIOLATION),
        (547, DotNetErrorCategory.CONSTRAINT_VIOLATION),
        (1205, DotNetErrorCategory.DEADLOCK),
        (-2, DotNetErrorCategory.TIMEOUT),
        (18456, DotNetErrorCategory.AUTHENTICATION),
        (4060, DotNetErrorCategory.DATABASE_UNAVAILABLE),
        (999999, DotNetErrorCategory.UNKNOWN),
        (None, DotNetErrorCategory.UNKNOWN),
    ],
)
def test_only_known_sql_numbers_are_classified(
    number: int | None,
    category: DotNetErrorCategory,
) -> None:
    assert classify_sql_number(number) is category


def test_raw_exception_text_is_not_retained() -> None:
    sentinel = "PRIVATE_SERVER_LOGIN_PASSWORD"

    class FakeSqlException(Exception):
        Number = 18456

    translated = safe_persistence_error(FakeSqlException(sentinel), operation="open")

    assert translated.category is DotNetErrorCategory.AUTHENTICATION
    assert translated.number == 18456
    assert sentinel not in str(translated)
    assert sentinel not in repr(translated)


@pytest.mark.parametrize(
    ("message", "category", "application_error"),
    [
        (
            "conflict with FOREIGN KEY constraint fk_children_parent",
            DotNetErrorCategory.FOREIGN_KEY_VIOLATION,
            ForeignKeyViolationError,
        ),
        (
            "conflict with CHECK constraint ck_amount_positive",
            DotNetErrorCategory.CHECK_CONSTRAINT_VIOLATION,
            CheckConstraintViolationError,
        ),
    ],
)
def test_constraint_547_uses_only_safe_constraint_classification(
    message: str,
    category: DotNetErrorCategory,
    application_error: type[PersistenceError],
) -> None:
    class FakeSqlException(Exception):
        Number = 547

    safe = safe_persistence_error(FakeSqlException(message), operation="execute_non_query")
    translated = translate_dotnet_error(safe, entity="sample", operation="insert")

    assert safe.category is category
    assert isinstance(translated, application_error)
    assert safe.constraint in {"fk_children_parent", "ck_amount_positive"}


@pytest.mark.parametrize(
    ("category", "application_error"),
    [
        ("FOREIGN_KEY_VIOLATION", ForeignKeyViolationError),
        ("CHECK_CONSTRAINT_VIOLATION", CheckConstraintViolationError),
    ],
)
def test_core_bridge_categories_preserve_constraint_kind_without_raw_text(
    category: str,
    application_error: type[PersistenceError],
) -> None:
    original = Exception(category, "547", "safe_constraint")
    error = IntegrityError(None, None, original)

    translated = translate_persistence_error(error, entity="sample", operation="insert")

    assert isinstance(translated, application_error)

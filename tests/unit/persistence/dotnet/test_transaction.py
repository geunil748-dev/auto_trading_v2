from __future__ import annotations

import pytest

from auto_trading_v2.adapters.persistence.dotnet.errors import (
    DotNetPersistenceError,
    DotNetTransactionStateError,
)
from auto_trading_v2.adapters.persistence.dotnet.transaction import (
    DotNetTransaction,
    DotNetTransactionState,
)


class FakeTransaction:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.disposals = 0
        self.fail_rollback = False

    def Commit(self) -> None:
        self.commits += 1

    def Rollback(self) -> None:
        self.rollbacks += 1
        if self.fail_rollback:
            raise RuntimeError("PRIVATE_ROLLBACK_MESSAGE")

    def Dispose(self) -> None:
        self.disposals += 1


class FakeConnection:
    def __init__(self, transaction: FakeTransaction) -> None:
        self.transaction = transaction

    def BeginTransaction(self) -> FakeTransaction:
        return self.transaction


def test_active_transaction_rolls_back_and_disposes_on_exit() -> None:
    raw = FakeTransaction()
    transaction = DotNetTransaction(FakeConnection(raw))

    with transaction:
        assert transaction.state is DotNetTransactionState.ACTIVE
        assert transaction.raw_transaction is raw

    assert raw.rollbacks == 1
    assert raw.commits == 0
    assert raw.disposals == 1
    assert transaction.state is DotNetTransactionState.FINISHED


def test_commit_is_one_shot_and_blocks_reuse() -> None:
    raw = FakeTransaction()
    transaction = DotNetTransaction(FakeConnection(raw))

    with transaction:
        transaction.commit()
        assert transaction.state is DotNetTransactionState.COMMITTED
        with pytest.raises(DotNetTransactionStateError):
            transaction.commit()
        with pytest.raises(DotNetTransactionStateError):
            transaction.rollback()

    assert raw.commits == 1
    assert raw.rollbacks == 0
    assert raw.disposals == 1


def test_explicit_rollback_is_one_shot() -> None:
    raw = FakeTransaction()
    transaction = DotNetTransaction(FakeConnection(raw))

    with transaction:
        transaction.rollback()
        with pytest.raises(DotNetTransactionStateError):
            transaction.commit()

    assert raw.rollbacks == 1
    assert raw.disposals == 1


def test_rollback_failure_does_not_mask_original_exception() -> None:
    raw = FakeTransaction()
    raw.fail_rollback = True

    with pytest.raises(LookupError, match="original"), DotNetTransaction(FakeConnection(raw)):
        raise LookupError("original")

    assert raw.rollbacks == 1
    assert raw.disposals == 1


def test_rollback_failure_without_original_is_sanitized() -> None:
    raw = FakeTransaction()
    raw.fail_rollback = True

    with pytest.raises(DotNetPersistenceError) as caught, DotNetTransaction(FakeConnection(raw)):
        pass

    assert "PRIVATE" not in str(caught.value)

from typing import cast
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine

from auto_trading_v2.adapters.persistence.unit_of_work import SqlAlchemyUnitOfWork
from auto_trading_v2.application.errors import TransactionStateError


def _uow() -> tuple[SqlAlchemyUnitOfWork, MagicMock, MagicMock]:
    transaction = MagicMock()
    transaction.is_active = True
    connection = MagicMock()
    connection.begin.return_value = transaction
    engine = MagicMock()
    engine.connect.return_value = connection
    return SqlAlchemyUnitOfWork(cast(Engine, engine)), connection, transaction


def test_normal_exit_without_commit_rolls_back_and_closes() -> None:
    uow, connection, transaction = _uow()

    with uow:
        assert uow.feature_snapshots is not None
        assert uow.universe_snapshots is not None
        assert uow.daily_feature_pipeline_runs is not None
        assert uow.daily_feature_scoring_runs is not None
        assert uow.daily_market_bars is not None
        assert uow.recommendations is not None
        assert uow.market_snapshots is not None
        assert uow.strategy_decisions is not None
        assert uow.trade_intents is not None
        assert uow.paper_orders is not None
        assert uow.paper_fills is not None
        assert uow.paper_positions is not None
        assert uow.position_events is not None

    transaction.rollback.assert_called_once_with()
    transaction.commit.assert_not_called()
    connection.close.assert_called_once_with()


def test_fifteen_repositories_share_the_same_connection() -> None:
    uow, connection, _ = _uow()

    with uow:
        repositories = (
            uow.daily_market_bars,
            uow.feature_snapshots,
            uow.universe_snapshots,
            uow.daily_feature_pipeline_runs,
            uow.daily_feature_scoring_runs,
            uow.recommendations,
            uow.market_snapshots,
            uow.candidates,
            uow.filter_evaluations,
            uow.strategy_decisions,
            uow.trade_intents,
            uow.paper_orders,
            uow.paper_fills,
            uow.paper_positions,
            uow.position_events,
        )
        assert len(repositories) == 15
        assert all(repository._connection is connection for repository in repositories)


def test_commit_is_explicit_and_blocks_further_operations() -> None:
    uow, connection, transaction = _uow()

    with uow:
        uow.commit()
        with pytest.raises(TransactionStateError):
            _ = uow.candidates
        with pytest.raises(TransactionStateError):
            uow.commit()

    transaction.commit.assert_called_once_with()
    transaction.rollback.assert_not_called()
    connection.close.assert_called_once_with()


def test_explicit_rollback_and_instance_reuse_are_forbidden() -> None:
    uow, _, transaction = _uow()

    with uow:
        uow.rollback()
        with pytest.raises(TransactionStateError):
            uow.rollback()

    transaction.rollback.assert_called_once_with()
    with pytest.raises(TransactionStateError):
        uow.__enter__()


def test_exception_exit_rolls_back_without_masking_original() -> None:
    uow, connection, transaction = _uow()

    with pytest.raises(LookupError, match="original"), uow:
        raise LookupError("original")

    transaction.rollback.assert_called_once_with()
    connection.close.assert_called_once_with()


def test_repository_failure_marks_transaction_rollback_only() -> None:
    uow, _, transaction = _uow()

    with uow:
        uow._mark_failed()
        with pytest.raises(TransactionStateError):
            uow.commit()

    transaction.rollback.assert_called_once_with()

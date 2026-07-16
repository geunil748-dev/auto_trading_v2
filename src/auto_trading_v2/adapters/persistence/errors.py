"""Translate SQLAlchemy/MSSQL failures into safe application errors."""

from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy.exc import DBAPIError, IntegrityError, SQLAlchemyError

from auto_trading_v2.application.errors import (
    CheckConstraintViolationError,
    DuplicateRecordError,
    ForeignKeyViolationError,
    PersistenceError,
    PersistenceUnavailableError,
)

_MSSQL_ERROR_CODE = re.compile(r"(?:\(|\b)(2601|2627|547)(?:\)|\b)")
_UNIQUE_CONSTRAINTS = frozenset(
    {
        "uq_market_snapshots_source_symbol_observed",
        "uq_candidates_run_snapshot_source",
        "uq_filter_evaluations_candidate_set_version",
        "uq_strategy_decisions_decision_key",
        "ix_strategy_decisions_candidate_unique",
        "uq_trade_intents_decision_id",
        "uq_trade_intents_idempotency_key",
        "uq_paper_orders_trade_intent_id",
        "uq_paper_orders_client_order_id",
        "ix_paper_orders_broker_ref_unique",
        "uq_paper_fills_execution_key",
        "uq_paper_fills_order_sequence",
        "ix_paper_positions_open_unique",
        "uq_position_events_fill_id",
        "uq_position_events_position_sequence",
    }
)
_FOREIGN_KEY_CONSTRAINTS = frozenset(
    {
        "fk_candidates_market_snapshot_id_market_snapshots",
        "fk_filter_evaluations_candidate_id_candidates",
        "fk_strategy_decisions_candidate_id_candidates",
        "fk_strategy_decisions_filter_evaluation_id_filter_evaluations",
        "fk_strategy_decisions_position_id_paper_positions",
        "fk_trade_intents_decision_id_strategy_decisions",
        "fk_paper_orders_trade_intent_id_trade_intents",
        "fk_paper_fills_order_id_paper_orders",
        "fk_position_events_position_id_paper_positions",
        "fk_position_events_fill_id_paper_fills",
    }
)
_CHECK_CONSTRAINTS = frozenset(
    {
        "ck_market_snapshots_symbol",
        "ck_market_snapshots_required_prices_positive",
        "ck_market_snapshots_previous_close_positive",
        "ck_market_snapshots_volume_nonnegative",
        "ck_market_snapshots_ohlc_consistent",
        "ck_market_snapshots_previous_range_consistent",
        "ck_candidates_rank_positive",
        "ck_filter_evaluations_details_json_object",
        "ck_strategy_decisions_action",
        "ck_strategy_decisions_candidate_xor_position",
        "ck_strategy_decisions_filter_requires_candidate",
        "ck_strategy_decisions_position_without_filter",
        "ck_strategy_decisions_reason_codes_json_array",
        "ck_trade_intents_symbol",
        "ck_trade_intents_currency",
        "ck_trade_intents_side",
        "ck_trade_intents_order_type",
        "ck_trade_intents_time_in_force",
        "ck_trade_intents_quantity_positive",
        "ck_trade_intents_limit_price_by_order_type",
        "ck_paper_orders_status",
        "ck_paper_orders_broker_code_nonempty",
        "ck_paper_orders_version_positive",
        "ck_paper_orders_status_closed_at",
        "ck_paper_fills_fee_currency",
        "ck_paper_fills_sequence_positive",
        "ck_paper_fills_quantity_positive",
        "ck_paper_fills_price_positive",
        "ck_paper_fills_fee_nonnegative",
        "ck_paper_positions_symbol",
        "ck_paper_positions_currency",
        "ck_paper_positions_status",
        "ck_paper_positions_quantity_nonnegative",
        "ck_paper_positions_average_cost_nonnegative",
        "ck_paper_positions_version_positive",
        "ck_paper_positions_status_state",
        "ck_position_events_event_type",
        "ck_position_events_sequence_positive",
        "ck_position_events_quantity_delta_nonzero",
        "ck_position_events_quantity_after_nonnegative",
        "ck_position_events_average_cost_nonnegative",
    }
)
_KNOWN_CONSTRAINTS = _UNIQUE_CONSTRAINTS | _FOREIGN_KEY_CONSTRAINTS | _CHECK_CONSTRAINTS


def _safe_fragments(exc: SQLAlchemyError) -> tuple[str, ...]:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    if not isinstance(args, Iterable) or isinstance(args, (str, bytes)):
        args = ()
    return tuple(str(item) for item in args if isinstance(item, (str, int)))


def _known_constraint(text: str) -> str | None:
    folded = text.casefold()
    return next((name for name in sorted(_KNOWN_CONSTRAINTS) if name in folded), None)


def translate_persistence_error(
    exc: SQLAlchemyError,
    *,
    entity: str,
    operation: str,
) -> PersistenceError:
    """Return a sanitized error without retaining SQL, parameters, or credentials."""

    fragments = _safe_fragments(exc)
    internal_text = " ".join(fragments)
    code_match = _MSSQL_ERROR_CODE.search(internal_text)
    code = None if code_match is None else code_match.group(1)
    constraint = _known_constraint(internal_text)

    if isinstance(exc, IntegrityError):
        if code in {"2601", "2627"}:
            return DuplicateRecordError(
                entity=entity,
                operation=operation,
                reason="duplicate_record",
                constraint=constraint,
            )
        if code == "547" and (
            constraint in _FOREIGN_KEY_CONSTRAINTS
            or "foreign key constraint" in internal_text.casefold()
        ):
            return ForeignKeyViolationError(
                entity=entity,
                operation=operation,
                reason="foreign_key_violation",
                constraint=constraint,
            )
        if code == "547" and (
            constraint in _CHECK_CONSTRAINTS or "check constraint" in internal_text.casefold()
        ):
            return CheckConstraintViolationError(
                entity=entity,
                operation=operation,
                reason="check_constraint_violation",
                constraint=constraint,
            )
        return PersistenceError(
            entity=entity,
            operation=operation,
            reason="integrity_violation",
            constraint=constraint,
        )

    if isinstance(exc, DBAPIError):
        sqlstate = next((part for part in fragments if len(part) == 5), "")
        if exc.connection_invalidated or sqlstate.startswith("08"):
            return PersistenceUnavailableError(
                entity=entity,
                operation=operation,
                reason="database_unavailable",
            )
    return PersistenceError(entity=entity, operation=operation)

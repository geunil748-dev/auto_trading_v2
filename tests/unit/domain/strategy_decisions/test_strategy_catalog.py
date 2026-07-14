from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from auto_trading_v2.domain.filtering.catalog import (
    BALANCED,
    OBSERVATION,
    SCORE_ONLY,
    STRICT,
)
from auto_trading_v2.domain.strategy_decisions.catalog import BUILT_IN_STRATEGIES
from auto_trading_v2.domain.strategy_decisions.models import StrategyName

EXPECTED = (
    (
        StrategyName.STRICT_ENTRY,
        "10c3fbc4-7db0-5980-9f85-8fbfc944a26c",
        STRICT.filter_set_id,
        STRICT.name,
    ),
    (
        StrategyName.BALANCED_ENTRY,
        "4bb90f07-6f29-5a8f-ada7-7d5952eb0c9a",
        BALANCED.filter_set_id,
        BALANCED.name,
    ),
    (
        StrategyName.SCORE_ONLY_ENTRY,
        "78b1169a-80d4-5894-8f45-b3c85cf5b2b6",
        SCORE_ONLY.filter_set_id,
        SCORE_ONLY.name,
    ),
    (
        StrategyName.OBSERVATION_ONLY,
        "86132628-8c1d-5eec-abcc-02ca3c3c39a5",
        OBSERVATION.filter_set_id,
        OBSERVATION.name,
    ),
)


def test_catalog_has_exact_stable_order_identity_and_mapping() -> None:
    assert len(BUILT_IN_STRATEGIES) == 4
    assert (
        tuple(
            (
                item.name,
                item.strategy_id.serialize(),
                item.source_filter_set_id,
                item.source_filter_set_name,
            )
            for item in BUILT_IN_STRATEGIES
        )
        == EXPECTED
    )
    assert all(item.strategy_version == "v1" for item in BUILT_IN_STRATEGIES)
    assert all(item.source_evaluation_version == "v1" for item in BUILT_IN_STRATEGIES)
    assert len({item.strategy_id for item in BUILT_IN_STRATEGIES}) == 4
    assert len({item.name for item in BUILT_IN_STRATEGIES}) == 4


def test_only_observation_policy_is_observation_only() -> None:
    assert tuple(item.observation_only for item in BUILT_IN_STRATEGIES) == (
        False,
        False,
        False,
        True,
    )


def test_definition_is_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        BUILT_IN_STRATEGIES[0].strategy_version = "v2"  # type: ignore[misc]


def test_catalog_source_has_no_runtime_or_environment_policy() -> None:
    source = Path("src/auto_trading_v2/domain/strategy_decisions/catalog.py").read_text(
        encoding="utf-8"
    )

    assert "uuid4" not in source
    assert ".env" not in source
    assert "getenv" not in source

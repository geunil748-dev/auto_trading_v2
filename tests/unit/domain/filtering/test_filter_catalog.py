from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

import pytest

from auto_trading_v2.domain.filtering.catalog import (
    BUILT_IN_FILTER_SETS,
    COMMON_THRESHOLDS,
    COMMON_WEIGHTS,
)
from auto_trading_v2.domain.filtering.models import FilterCheckName, FilterSetName

EXPECTED_IDS = {
    FilterSetName.STRICT: "aaad2a67-4080-5805-90d5-2b6c350b8cdd",
    FilterSetName.BALANCED: "58865908-eb8a-5089-bc66-b38b49578f84",
    FilterSetName.SCORE_ONLY: "e5f2aa3d-82e1-566a-aeb4-7313b49fc436",
    FilterSetName.OBSERVATION: "bf66c976-b971-571e-b688-d21abfacfb4d",
}


def test_catalog_has_exact_stable_order_ids_and_version() -> None:
    assert tuple(item.name for item in BUILT_IN_FILTER_SETS) == tuple(FilterSetName)
    assert len(BUILT_IN_FILTER_SETS) == 4
    assert len({item.name for item in BUILT_IN_FILTER_SETS}) == 4
    assert len({item.filter_set_id for item in BUILT_IN_FILTER_SETS}) == 4
    for item in BUILT_IN_FILTER_SETS:
        assert item.filter_set_id.serialize() == EXPECTED_IDS[item.name]
        assert item.evaluation_version == "v1"
        assert item.name.value == item.mode.value


def test_catalog_has_exact_thresholds_weights_and_check_order() -> None:
    assert COMMON_THRESHOLDS.minimum_price.value == Decimal("10")
    assert COMMON_THRESHOLDS.maximum_price.value == Decimal("300")
    assert COMMON_THRESHOLDS.minimum_opening_change == Decimal("0.03")
    assert COMMON_THRESHOLDS.maximum_entry_change == Decimal("0.15")
    assert COMMON_THRESHOLDS.breakout_factor == Decimal("0.5")
    assert tuple(item.name for item in COMMON_WEIGHTS) == tuple(FilterCheckName)
    assert tuple(item.weight for item in COMMON_WEIGHTS) == (
        Decimal("20"),
        Decimal("20"),
        Decimal("20"),
        Decimal("30"),
        Decimal("10"),
    )
    assert sum((item.weight for item in COMMON_WEIGHTS), Decimal("0")) == Decimal("100")


def test_catalog_definitions_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        BUILT_IN_FILTER_SETS[0].minimum_score = Decimal("0")  # type: ignore[misc]


def test_catalog_has_no_runtime_random_or_environment_configuration() -> None:
    source = (
        Path(__file__).resolve().parents[4] / "src" / "auto_trading_v2" / "domain" / "filtering"
    )
    text = "\n".join(path.read_text(encoding="utf-8") for path in source.rglob("*.py"))

    assert "uuid4" not in text
    assert "os.getenv" not in text
    assert "os.environ" not in text
    assert "auto_trading_v2.config" not in text

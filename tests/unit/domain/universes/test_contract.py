from datetime import UTC, datetime
from uuid import UUID

import pytest

from auto_trading_v2.domain.primitives import Symbol, UniverseSnapshotID
from auto_trading_v2.domain.universes import (
    UniverseCode,
    UniverseDefinition,
    UniverseMember,
    UniverseSnapshot,
    UniverseSnapshotValidationError,
    UniverseVersion,
    universe_content_digest,
    universe_key,
)

NOW = datetime(2026, 7, 31, 22, tzinfo=UTC)


def member(index: int, mic: str = "XNGS") -> UniverseMember:
    return UniverseMember(Symbol(f"S{index:03d}"), mic)


def definition(
    members: tuple[UniverseMember, ...],
    code: str = "CORE_US",
    version: str = "2026-07-31",
) -> UniverseDefinition:
    return UniverseDefinition(UniverseCode(code), UniverseVersion(version), members)


@pytest.mark.parametrize("count", (1, 100))
def test_member_count_boundaries_are_accepted(count: int) -> None:
    value = definition(tuple(member(index) for index in range(count)))

    assert len(value.members) == count


@pytest.mark.parametrize("count", (0, 101))
def test_member_count_outside_v1_boundary_is_rejected(count: int) -> None:
    with pytest.raises(UniverseSnapshotValidationError, match="UNIVERSE_MEMBER_COUNT_INVALID"):
        definition(tuple(member(index) for index in range(count)))


def test_duplicate_symbol_is_rejected_even_when_mic_differs() -> None:
    with pytest.raises(UniverseSnapshotValidationError, match="UNIVERSE_DUPLICATE_SYMBOL"):
        definition(
            (
                UniverseMember(Symbol("AAPL"), "XNGS"),
                UniverseMember(Symbol("AAPL"), "XNYS"),
            )
        )


@pytest.mark.parametrize("mic", ("XNAS", "XLON", "", "ABC", None, 123))
def test_unsupported_or_malformed_mic_is_rejected_without_echo(mic: object) -> None:
    with pytest.raises(UniverseSnapshotValidationError) as caught:
        UniverseMember(Symbol("AAPL"), mic)  # type: ignore[arg-type]

    if str(mic):
        assert str(mic) not in str(caught.value)
    assert caught.value.category == "UNIVERSE_MIC_UNSUPPORTED"


def test_input_order_is_irrelevant_and_canonical_order_is_mic_then_symbol() -> None:
    values = (
        UniverseMember(Symbol("IBM"), "XNYS"),
        UniverseMember(Symbol("MSFT"), "XNGS"),
        UniverseMember(Symbol("AAPL"), "XNGS"),
    )

    first = definition(values)
    second = definition(tuple(reversed(values)))

    assert first.members == second.members
    assert [(item.mic_code, item.symbol.value) for item in first.members] == [
        ("XNGS", "AAPL"),
        ("XNGS", "MSFT"),
        ("XNYS", "IBM"),
    ]
    assert universe_key(first) == universe_key(second)
    assert universe_content_digest(first) == universe_content_digest(second)


def test_key_tracks_code_version_while_digest_tracks_only_members() -> None:
    original = definition((member(1), member(2)))
    changed_version = definition(original.members, version="2026-08-01")
    changed_members = definition((member(1), member(3)))

    assert universe_key(original) != universe_key(changed_version)
    assert universe_content_digest(original) == universe_content_digest(changed_version)
    assert universe_key(original) == universe_key(changed_members)
    assert universe_content_digest(original) != universe_content_digest(changed_members)


def test_snapshot_validates_deterministic_identity_and_content() -> None:
    source = definition((member(1),))
    snapshot = UniverseSnapshot(
        UniverseSnapshotID(UUID(int=1)),
        universe_key(source),
        universe_content_digest(source),
        source,
        NOW,
        NOW,
    )

    assert snapshot.members == source.members
    with pytest.raises(UniverseSnapshotValidationError, match="UNIVERSE_DIGEST_MISMATCH"):
        UniverseSnapshot(
            UniverseSnapshotID(UUID(int=2)),
            universe_key(source),
            "0" * 64,
            source,
            NOW,
            NOW,
        )

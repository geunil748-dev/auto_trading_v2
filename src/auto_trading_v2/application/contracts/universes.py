"""Immutable contracts for caller-provided UniverseSnapshot creation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from auto_trading_v2.domain.primitives import UniverseSnapshotID
from auto_trading_v2.domain.universes import (
    UniverseCode,
    UniverseDefinition,
    UniverseMember,
    UniverseSnapshot,
    UniverseVersion,
    universe_content_digest,
    universe_key,
)


@dataclass(frozen=True, slots=True)
class CreateUniverseSnapshotCommand:
    universe_code: str
    universe_version: str
    members: Sequence[UniverseMember] = field(repr=False)
    _definition: UniverseDefinition = field(init=False, repr=False)

    def __post_init__(self) -> None:
        definition = UniverseDefinition(
            UniverseCode(self.universe_code),
            UniverseVersion(self.universe_version),
            self.members,
        )
        object.__setattr__(self, "universe_code", definition.universe_code.value)
        object.__setattr__(self, "universe_version", definition.universe_version.value)
        object.__setattr__(self, "members", definition.members)
        object.__setattr__(self, "_definition", definition)

    @property
    def definition(self) -> UniverseDefinition:
        return self._definition


@dataclass(frozen=True, slots=True)
class NewUniverseSnapshot:
    universe_snapshot_id: UniverseSnapshotID
    universe_key: str
    content_digest: str
    definition: UniverseDefinition = field(repr=False)
    generated_at: datetime

    def __post_init__(self) -> None:
        if self.universe_key != universe_key(self.definition):
            raise ValueError("universe key mismatch")
        if self.content_digest != universe_content_digest(self.definition):
            raise ValueError("universe digest mismatch")

    def stored(self, recorded_at: datetime) -> UniverseSnapshot:
        return UniverseSnapshot(
            self.universe_snapshot_id,
            self.universe_key,
            self.content_digest,
            self.definition,
            self.generated_at,
            recorded_at,
        )


class UniverseSnapshotCreationOutcome(StrEnum):
    CREATED = "CREATED"
    ALREADY_EXISTS = "ALREADY_EXISTS"


@dataclass(frozen=True, slots=True)
class UniverseSnapshotCreationResult:
    outcome: UniverseSnapshotCreationOutcome
    snapshot: UniverseSnapshot

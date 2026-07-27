from pathlib import Path

import pytest

from auto_trading_v2.adapters.persistence.dotnet.repositories import (
    DotNetCandidateRepository,
    DotNetFeatureSnapshotRepository,
    DotNetFilterEvaluationRepository,
    DotNetMarketSnapshotRepository,
    DotNetPaperFillRepository,
    DotNetPaperOrderRepository,
    DotNetPaperPositionRepository,
    DotNetPositionEventRepository,
    DotNetStrategyDecisionRepository,
    DotNetTradeIntentRepository,
)
from auto_trading_v2.adapters.persistence.repositories import (
    SqlAlchemyCandidateRepository,
    SqlAlchemyFeatureSnapshotRepository,
    SqlAlchemyFilterEvaluationRepository,
    SqlAlchemyMarketSnapshotRepository,
    SqlAlchemyPaperFillRepository,
    SqlAlchemyPaperOrderRepository,
    SqlAlchemyPaperPositionRepository,
    SqlAlchemyPositionEventRepository,
    SqlAlchemyStrategyDecisionRepository,
    SqlAlchemyTradeIntentRepository,
)


@pytest.mark.parametrize(
    ("dotnet_repository", "contract_implementation"),
    [
        (DotNetMarketSnapshotRepository, SqlAlchemyMarketSnapshotRepository),
        (DotNetFeatureSnapshotRepository, SqlAlchemyFeatureSnapshotRepository),
        (DotNetCandidateRepository, SqlAlchemyCandidateRepository),
        (DotNetFilterEvaluationRepository, SqlAlchemyFilterEvaluationRepository),
        (DotNetStrategyDecisionRepository, SqlAlchemyStrategyDecisionRepository),
        (DotNetTradeIntentRepository, SqlAlchemyTradeIntentRepository),
        (DotNetPaperOrderRepository, SqlAlchemyPaperOrderRepository),
        (DotNetPaperFillRepository, SqlAlchemyPaperFillRepository),
        (DotNetPaperPositionRepository, SqlAlchemyPaperPositionRepository),
        (DotNetPositionEventRepository, SqlAlchemyPositionEventRepository),
    ],
)
def test_each_dotnet_repository_preserves_the_existing_contract_implementation(
    dotnet_repository: type[object],
    contract_implementation: type[object],
) -> None:
    assert issubclass(dotnet_repository, contract_implementation)
    assert dotnet_repository.__mro__[1] is contract_implementation


def test_dotnet_repository_types_do_not_own_connections_or_transactions() -> None:
    source = Path("src/auto_trading_v2/adapters/persistence/dotnet/repositories.py").read_text(
        encoding="utf-8"
    )

    for forbidden in (".Open(", ".Close(", ".Commit(", ".Rollback(", ".BeginTransaction("):
        assert forbidden not in source

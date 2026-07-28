"""Explicit DotNet persistence foundation for local V2 runtime use."""

from auto_trading_v2.adapters.persistence.dotnet.commands import (
    DotNetCommandExecutor,
    DotNetSqlParameter,
    DotNetSqlType,
)
from auto_trading_v2.adapters.persistence.dotnet.composition import (
    compose_dotnet_persistence,
    load_dotnet_unit_of_work_factory,
)
from auto_trading_v2.adapters.persistence.dotnet.connection import DotNetConnectionFactory
from auto_trading_v2.adapters.persistence.dotnet.core_adapter import DotNetCoreConnection
from auto_trading_v2.adapters.persistence.dotnet.errors import (
    DotNetErrorCategory,
    DotNetParameterError,
    DotNetPersistenceError,
    DotNetResultConversionError,
    DotNetRuntimeError,
    DotNetTransactionStateError,
    classify_sql_number,
    translate_dotnet_error,
)
from auto_trading_v2.adapters.persistence.dotnet.probe import (
    DotNetProbeResult,
    DotNetTransactionSmokeResult,
    run_read_only_probe,
    run_transaction_rollback_smoke,
)
from auto_trading_v2.adapters.persistence.dotnet.repositories import (
    DotNetCandidateRepository,
    DotNetFeatureSnapshotRepository,
    DotNetFilterEvaluationRepository,
    DotNetMarketSnapshotRepository,
    DotNetPaperFillRepository,
    DotNetPaperOrderRepository,
    DotNetPaperPositionRepository,
    DotNetPositionEventRepository,
    DotNetRecommendationRepository,
    DotNetStrategyDecisionRepository,
    DotNetTradeIntentRepository,
)
from auto_trading_v2.adapters.persistence.dotnet.results import DotNetRow, DotNetRows
from auto_trading_v2.adapters.persistence.dotnet.runtime import (
    DotNetRuntimeInfo,
    load_sqlclient_runtime,
)
from auto_trading_v2.adapters.persistence.dotnet.transaction import (
    DotNetTransaction,
    DotNetTransactionState,
)
from auto_trading_v2.adapters.persistence.dotnet.unit_of_work import (
    DotNetUnitOfWork,
    DotNetUnitOfWorkFactory,
)

__all__ = [
    "DotNetCommandExecutor",
    "DotNetConnectionFactory",
    "DotNetCoreConnection",
    "DotNetCandidateRepository",
    "DotNetErrorCategory",
    "DotNetFeatureSnapshotRepository",
    "DotNetFilterEvaluationRepository",
    "DotNetMarketSnapshotRepository",
    "DotNetParameterError",
    "DotNetPaperFillRepository",
    "DotNetPaperOrderRepository",
    "DotNetPaperPositionRepository",
    "DotNetPersistenceError",
    "DotNetProbeResult",
    "DotNetResultConversionError",
    "DotNetPositionEventRepository",
    "DotNetRecommendationRepository",
    "DotNetRow",
    "DotNetRows",
    "DotNetRuntimeError",
    "DotNetRuntimeInfo",
    "DotNetSqlParameter",
    "DotNetSqlType",
    "DotNetStrategyDecisionRepository",
    "DotNetTradeIntentRepository",
    "DotNetTransaction",
    "DotNetTransactionSmokeResult",
    "DotNetTransactionState",
    "DotNetTransactionStateError",
    "DotNetUnitOfWork",
    "DotNetUnitOfWorkFactory",
    "classify_sql_number",
    "compose_dotnet_persistence",
    "load_dotnet_unit_of_work_factory",
    "load_sqlclient_runtime",
    "run_read_only_probe",
    "run_transaction_rollback_smoke",
    "translate_dotnet_error",
]

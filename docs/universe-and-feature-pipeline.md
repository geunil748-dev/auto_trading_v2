# UniverseSnapshot and daily feature pipeline

## Caller-provided universe

P3 does not discover symbols from an external API. The caller supplies `universe_code`,
`universe_version`, and 1 to 100 members. Each member has an existing canonical `Symbol` and one
supported listing MIC: `XNGS`, `XNGM`, `XNCM`, `XNYS`, or `XASE`. Duplicate symbols are rejected.
Input order is ignored; persistence and processing use MIC then symbol order.

`universe_key` hashes code/version. `content_digest` hashes the canonical members and excludes IDs
and timestamps. Reusing code/version with the same members is an exact retry; changing membership
requires a new version. A same-identity content conflict is categorical and payload-safe.

## Run contract

The fixed v1 contract is `US_EQUITY_DAILY_FEATURE_BATCH/v1`, split-adjusted daily bars,
`US_EQUITY_DAILY_TECHNICAL/v1`, a 1 to 5 trading-day horizon, and at least 21 requested completed
sessions (30 by default). The P2.2 `US_EQUITY_CORE/2026.v1` resolver and request factory determine
one eligible completed session for every member. No-session and out-of-coverage results do not call
the provider.

Twelve Data is the only primary P3 source. Alpaca IEX remains validation-only. The application
estimates maximum credits for all members and fails closed when the daily budget is unknown or too
small. Execution is sequential in canonical member order. There is no fallback or mixed-provider
FeatureSnapshot.

For each member, the pipeline ingests or reuses DailyMarketBars and invokes the existing daily
technical FeatureSnapshot service. Outcomes are READY, DEGRADED, DATA_INSUFFICIENT, NO_DATA,
PROVIDER_ERROR, CALENDAR_ERROR, NOT_ATTEMPTED_BUDGET, or NOT_ATTEMPTED_ABORTED. Symbol failures are
isolated. Fatal provider/system failures abort remaining symbols; three consecutive transient
failures open the circuit and a successful symbol resets it.

## Persistence and retry

The immutable `daily_feature_pipeline_runs` row stores identity, status, counts, credit summary, and
timestamps. Ordered `daily_feature_pipeline_items` rows store safe per-symbol results and optional
FeatureSnapshot references. The run and all items commit together after symbol processing. Earlier
DailyMarketBar and FeatureSnapshot commits are deliberately retained if final summary persistence
fails.

The deterministic run key is checked before run ID creation. An exact retry performs zero provider
network calls, zero DailyMarketBar writes, and zero FeatureSnapshot builds. Run-key uniqueness races
rollback and re-read the stored aggregate using a fresh Unit of Work.

P3 does not calculate probability, expected return, entry/target/stop prices, or ranks. It creates
no Recommendation, StrategyDecision, TradeIntent, broker call, order, notification, or scheduler
execution. Those prediction outputs begin with P4.

## External batch validation status

`EXTERNAL_BATCH_LIVE: NOT_RUN_CREDENTIAL_MISSING`. The P3 worktree configuration was inspected
without exposing secrets; Twelve Data was disabled and no credential was configured. This does not
block a draft PR after all local unit, MSSQL integration, static, cleanup, and preservation gates
pass.

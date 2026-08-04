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

The explicit v2 policy is `US_EQUITY_DAILY_FEATURE_BATCH/v2` paired only with
`US_EQUITY_DAILY_TECHNICAL/v2`. The command must select that immutable policy and the application
must be configured with the v2 feature service; otherwise it fails before provider I/O. v1 remains
the default. Both policy versions keep the same universe order, single-provider sequential
execution, budget preflight, failure isolation, bounded circuit, and exact-retry behavior. Their run
keys and v2 content digest carry the selected policy versions, so v1 and v2 coexist without fallback
or identity collision. Complete Twelve Data prices with null canonical volume are `READY` under v2.

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
execution. P4A consumes the immutable run without mutating it.

The existing P4A scoring policy accepts only the documented v1 pipeline. Price-only P4A scoring is
outside this slice; v2 FeatureSnapshots do not silently enter v1 scoring.

## P4A downstream scoring boundary

P4A accepts only eligible completed P3 statuses produced by
`US_EQUITY_DAILY_FEATURE_BATCH/v1`, `TWELVE_DATA_TIME_SERIES`, and split-adjusted
`US_EQUITY_DAILY_TECHNICAL/v1`. READY and supported volume-related DEGRADED items enter the
same-run price population; volume percentiles use READY items only. All other P3 outcomes remain
visible as unscorable audit items. Exact scoring retry performs no network request, bar write,
FeatureSnapshot build, or Recommendation creation. See [relative scoring](relative-scoring.md).

## P4B.1 downstream outcome boundary

P4B.1 reuses the P3 run's completed session and 1–5 trading-day horizon. It validates the persisted
P4A→P3→FeatureSnapshot chain, takes the reference price from FeatureSnapshot `last_close`, and reads
only existing canonical future DailyMarketBars at an observation cutoff. It does not rerun P3,
change a snapshot, call a provider, or create a Recommendation. The static calendar supports only
2026; see [forward outcomes](forward-outcomes.md).

## External batch validation status

`EXTERNAL_BATCH_LIVE: NOT_RUN_CREDENTIAL_MISSING`. The P3 worktree configuration was inspected
without exposing secrets; Twelve Data was disabled and no credential was configured. This does not
block a draft PR after all local unit, MSSQL integration, static, cleanup, and preservation gates
pass.

## Multi-year calendar compatibility

The multi-year `US_EQUITY_CORE / 2018-2026.v1` calendar is a separately selected research boundary.
P3 v1 and v2 continue to use the existing `2026.v1` operational calendar; neither pipeline changes
calendar version automatically or starts historical replay. Historical DailyMarketBar backfill is
the next slice and is not implemented here.

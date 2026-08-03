# Persistence boundary

PR 4 introduced the first V2 persistence vertical slice:

```text
market_snapshots -> candidates -> filter_evaluations
```

That paragraph is historical. The current foundation exposes fifteen repositories, including
independent `daily_market_bars`, `feature_snapshots`, `recommendations`, `universe_snapshots`, and
`daily_feature_pipeline_runs` repositories plus the P4A `daily_feature_scoring_runs` aggregate
repository.
Existing trade and paper repositories remain optional shadow simulation infrastructure.

## Dependency direction

Application contracts and ports import only domain primitives and Python standard-library types.
They do not expose SQLAlchemy tables, engines, connections, rows, or DBAPI exceptions. SQLAlchemy
Core implementations live under `adapters/persistence` and reuse the canonical table metadata.

The immutable `New*` contracts validate identifiers, finite `Decimal` values, non-empty technical
codes, non-negative volume, positive rank, and timezone-aware timestamps normalized to UTC. The
corresponding `Stored*` contracts add the database-generated `recorded_at` timestamp.

Filter details accept a top-level JSON object containing only `None`, booleans, integers, strings,
lists, and nested mappings. Input is copied into a deeply immutable representation. Floats,
`Decimal`, timestamps, UUIDs, secrets, bytes, sets, tuples, and arbitrary objects are rejected.
Callers must convert decimal values to strings explicitly. Storage uses compact, Unicode-preserving,
stable-key JSON serialization.

FeatureSnapshot uses a stricter separate JSON contract. It accepts nested finite Decimal values and
canonicalizes them to fixed non-scientific strings, while rejecting Python float at every depth.
Provenance is sorted, payload mappings are key-sorted, and quality reason codes are sorted. The
semantic snapshot key excludes content and generation time; the content digest excludes ID,
generation time, and database `recorded_at`.

## Transaction lifecycle

`SqlAlchemyUnitOfWorkFactory` creates a fresh one-shot Unit of Work. Entering it checks out one
connection, starts one root transaction, and supplies that connection to all fifteen repositories.
Only the Unit of Work may commit or roll back.

- `commit()` persists the whole slice atomically.
- Normal exit without `commit()` rolls back.
- Exception exit and explicit `rollback()` roll back.
- A repository failure marks the transaction rollback-only.
- Operations after commit or rollback, repeated completion, nesting the same instance, and instance
  reuse are rejected.
- Context exit always closes the connection; it never disposes the application-owned engine.

Repositories provide only the specified add/get/list operations. They do not start transactions,
commit, roll back, read configuration, construct engines, update, delete, or upsert.

`FeatureSnapshotCreationService` validates Point-in-Time input before opening a Unit of Work, calls
the Clock exactly once, reads by deterministic `snapshot_key`, and commits exactly once only for a
new insert. Exact retry returns `ALREADY_EXISTS` without ID generation, insert, or commit. A same-key
different-digest request raises a payload-safe conflict. Unique races rollback and recheck in a new
Unit of Work; no path overwrites an existing row.

`DailyMarketBarCreationService` applies the same immutable retry/conflict/race policy to provider
semantic identity. Its repository adds ID/key reads plus `list_latest_available`, implemented once
as a deterministic SQLAlchemy Core window query and reused by DotNet. The query excludes
`available_at > as_of`, selects one latest revision per session, limits distinct sessions, and
returns chronological bars without owning a transaction.

`RecommendationCreationService` calls the Clock once, then reads the referenced FeatureSnapshot and
the Recommendation identity in the same Unit of Work. It rejects missing sources, actionable
recommendations from DEGRADED sources, generation before the source cutoff, and plans beyond the
source horizon. New content receives one ID and one commit. Exact retry performs no ID generation,
insert, or commit; conflicts and unique-race rechecks remain payload-safe. Recommendation creation
does not call TradeIntent, broker, order, fill, position, KIS, or Telegram paths.

## Safe errors

Adapter errors are translated to the application persistence hierarchy. MSSQL 2601 and 2627 map to
`DuplicateRecordError`; MSSQL 547 maps to either `ForeignKeyViolationError` or
`CheckConstraintViolationError` when the violation category is known. Messages contain only a safe
entity, operation category, and allow-listed constraint name. They never include a URL, host, login,
SQL text, parameters, JSON payload, row data, or raw driver exception representation.

## Engine and diagnostics

`create_mssql_engine(DatabaseSettings)` is the only new engine factory. It reveals the protected URL
only at engine construction, enables hidden parameters and pool pre-ping, disables echo, and does not
connect or migrate when called.

Run the read-only development diagnostic with:

```powershell
python scripts/check_persistence.py
```

The diagnostic explicitly loads the repository `.env`, requires the database setting source to be
`dotenv`, verifies the V2 development database, `trading` schema, all 25 canonical tables, and the
Alembic head revision, then closes the connection and disposes the engine. It performs no inserts,
updates, deletes, migrations, database creation, or schema creation and does not print connection
details.

All write integration tests reuse the guarded `auto_trading_v2_test_*` temporary database fixture.
The development database remains read-only during persistence verification.

Local Windows integration may explicitly select `local_shared_memory` for both SQLAlchemy
administration and temporary-target persistence. That path constructs a fresh LPC
Windows-integrated ODBC connection, uses `NullPool`, verifies the connected database and shared
memory transport before migration or persistence, and disposes target connections before guarded
drop. The default remains `tcp_url`; there is no TCP/LPC fallback in either direction. Application
runtime persistence continues to use DotNet SqlClient over TCP SQL authentication. DotNet
integration tests use an immutable `environment=test` copy of the official runtime settings with
only the temporary database name replaced, so they do not derive endpoint or authentication from a
SQLAlchemy engine.

FeatureSnapshot live integration exercises the same temporary database through both providers.
SQLAlchemy supplies guarded migration administration and one persistence implementation; DotNet
uses a test-only copy of the validated runtime settings with only the database name replaced by the
fixture's `auto_trading_v2_test_*` name. Tests cover the 0004-to-0003-to-0004 round trip, the live
catalog and constraints, commit and rollback visibility, canonical Unicode/Decimal/UTC round trips,
idempotent retry and conflict behavior, and bidirectional SQLAlchemy/DotNet reads. No write or DDL
test targets the development database.

Recommendation live integration uses the same guarded fixture and common Core repository statements
for SQLAlchemy and DotNet. It covers the `0005`-to-`0004`-to-`0005` round trip while preserving the
prior 12-table catalog, actionable and NULL-plan shapes, invalid constraint rollback residue,
idempotent retry/conflict, commit/implicit rollback visibility, list/get operations, and
bidirectional full canonical equality. No provider-specific raw SQL repository is used.

DailyMarketBar live integration verifies `0006` to `0005` to `0006` while preserving the prior
13-table catalog, constraints and invalid-insert rollback, SQLAlchemy/DotNet retry and conflict,
latest PIT revisions, bidirectional equality, and READY/DEGRADED/DATA_INSUFFICIENT FeatureSnapshot
builds. Tests use only guarded `auto_trading_v2_test_*` databases; the development DB is unchanged.
DotNet connection pooling remains enabled for development/paper settings and is disabled only when
the validated environment is `test`, so temporary databases have no pooled session at cleanup.

P3 adds `UniverseSnapshotRepository` and `DailyFeaturePipelineRunRepository` to both Unit of Work
implementations. The run repository inserts a run and its ordered items on the caller-owned
connection and transaction; repositories never commit. SQLAlchemy and DotNet share the same Core
statements and row/JSON mappings. Exact run retry reads the aggregate before ID generation or work,
and a unique-key race rolls back then re-reads through a fresh Unit of Work.

Migration `0007_multi_symbol_feature_pipeline` round-trips to `0006` only in guarded
`auto_trading_v2_test_*` databases. It removes and recreates only the three P3 tables while a catalog
signature proves all prior fourteen tables unchanged. Scripted P3 integration uses one sequential
Twelve Data-compatible provider, writes DailyMarketBars and FeatureSnapshots per symbol, persists
the immutable run aggregate, and verifies SQLAlchemy/DotNet canonical equality. It creates no
Recommendation, TradeIntent, or PaperOrder rows.

P4A adds `DailyFeatureScoringRunRepository` to both Unit of Work implementations. It inserts one
run and its canonically ordered items on the caller-owned connection, maps `DECIMAL(9,6)` directly
to `Decimal`, and supplies ID/key/aggregate/item reads. Exact retry performs no feature reads,
calculation, insert, or commit. A unique race rolls back the current Unit of Work and re-reads in a
fresh one; equal content returns the stored aggregate while different content raises a sanitized
conflict. SQLAlchemy Core statements and mappings are reused by the DotNet adapter.

Migration `0008_daily_feature_scoring` round-trips to `0007` only in guarded temporary databases.
It removes and recreates only the two P4A tables while preserving the prior seventeen-table catalog
signature. Scripted integration persists a mixed READY/DEGRADED/unscorable P3 source, verifies
quality-tier ranking, SQLAlchemy/DotNet equality, exact retry, and zero Recommendation, TradeIntent,
or PaperOrder rows.

P4B.1 adds `DailyFeatureOutcomeRepository` and
`DailyFeatureOutcomeObservationRunRepository` to both Unit of Work providers, increasing the shared
repository count from 15 to 17. Outcome add/read/latest-as-of and observation aggregate operations
reuse provider-neutral Core statements and mappings. Repositories never commit or roll back.

Migration `0009_daily_feature_outcomes` round-trips to `0008` only in guarded temporary databases.
It removes and recreates only the three P4B.1 tables while preserving the prior nineteen-table
catalog signature. Future-bar selection is read-only and Point-in-Time; no provider, DailyMarketBar,
FeatureSnapshot, scoring, Recommendation, or order write occurs.

P4B.2A adds `DailyFeatureOutcomeLabelRepository` and
`ProbabilityCalibrationDatasetRepository`, increasing both Unit of Work providers from 17 to 19
repositories on one caller-owned connection and transaction. SQLAlchemy and DotNet reuse the same
Core mappings and statements. A separate provider-neutral source reader performs one windowed query
to choose the latest eligible outcome revision per scoring item with all four as-of cutoffs.

Migration `0010_outcome_labels_calibration_dataset` round-trips to `0009` only in guarded temporary
databases. It removes and recreates only the three P4B.2A tables while preserving the prior
twenty-two-table catalog signature. Label creation uses an independent immutable transaction per
source; the dataset header and all ordered items commit together. Unique races roll back and re-read
through a fresh Unit of Work; equal digests reuse the winner and different digests raise sanitized
conflicts.

Prediction Readiness R1 adds one read-only lineage method to the existing
`ProbabilityCalibrationDatasetRepository`; it does not add a repository to either UoW. Both
providers reuse one Core SELECT and mapping. `TrainingReadinessAuditService` opens a UoW, reads the
explicit dataset header/items and lineage, never calls `commit()`, and relies on normal-exit
rollback. Repository count remains 19, table count remains 25, and no migration changes.

Price-only FeatureSet v2 reuses the existing `FeatureSnapshotRepository`, P3 run repository, and
Unit of Work boundaries. Its identity differs by explicit feature/pipeline version, while its JSON
payload omits the three volume keys. No repository, table, migration, development-DB backfill, or
existing-row mutation is added; repository count remains 19, table count remains 25, and Alembic
head remains `0010_outcome_labels_calibration_dataset`.

The current local Windows account has the temporary-database permissions needed by the LPC test
path. No login or credential is created or committed. A dedicated least-privilege test
administrator remains a separate hardening option. Further ODBC TCP/TLS/trust diagnosis is outside
this test-infrastructure boundary.

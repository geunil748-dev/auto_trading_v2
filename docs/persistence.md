# Persistence boundary

PR 4 introduced the first V2 persistence vertical slice:

```text
market_snapshots -> candidates -> filter_evaluations
```

That paragraph is historical. The current foundation exposes twelve repositories, including
independent `daily_market_bars`, `feature_snapshots`, and `recommendations` repositories.
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
connection, starts one root transaction, and supplies that connection to all twelve repositories.
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
`dotenv`, verifies the V2 development database, `trading` schema, all 14 canonical tables, and the
Alembic head revision, then closes the connection and disposes the engine. It performs no inserts,
updates, deletes, migrations, database creation, or schema creation and does not print connection
details.

All write integration tests reuse the guarded `auto_trading_v2_test_*` temporary database fixture.
The development database remains read-only during persistence verification.

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

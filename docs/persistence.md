# Persistence boundary

PR 4 introduced the first V2 persistence vertical slice:

```text
market_snapshots -> candidates -> filter_evaluations
```

That paragraph is historical. The current foundation exposes ten repositories and adds the
independent `feature_snapshots` repository for the recommendation pivot. Existing trade and paper
repositories remain optional shadow simulation infrastructure.

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
connection, starts one root transaction, and supplies that connection to all ten repositories.
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
`dotenv`, verifies the V2 development database, `trading` schema, all 12 canonical tables, and the
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

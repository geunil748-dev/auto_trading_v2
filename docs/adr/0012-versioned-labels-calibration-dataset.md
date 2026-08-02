# ADR 0012: Versioned labels and leakage-safe calibration datasets

Status: Accepted

## Decision

Use immutable, versioned positive-close labels and immutable Point-in-Time calibration-dataset
snapshots. Label v1 classifies strictly positive terminal-close return as `POSITIVE`; flat and
negative returns are `NOT_POSITIVE`. Each P4B.1 outcome revision receives its own label identity.

Dataset v1 includes only P4A READY scoring items. It chooses one latest outcome revision per scoring
item after applying both data-availability and database-recorded-at cutoffs to outcomes, plus
generated/recorded cutoffs to scoring sources. It preserves prospective and replay modes, separates
horizons, and uses deterministic item order.

## Consequences

Corrections cannot backdate themselves into an earlier dataset snapshot, retry is deterministic,
and SQLAlchemy/DotNet share one Core selection contract. DEGRADED labels remain available for audit
but are excluded from initial calibration input. Empty datasets are valid evidence of no eligible
samples.

P4B.2A does not fit a model, calculate probability/confidence/expected value, invent target/stop
thresholds, create a Recommendation, or invoke a provider. Positive-close labels also ignore trading
costs. P4B.2B owns walk-forward sigmoid fitting and evaluation; P4C owns actionable Recommendations.

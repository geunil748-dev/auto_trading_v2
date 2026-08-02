# Prospective forward outcome observations

P4B.1 records raw realized forward paths for eligible P4A scoring items. It does not predict a
return and does not create a probability, confidence, label, expected value, Recommendation,
entry/target/stop proposal, or VIRTUAL/ACTUAL trade. Labels and walk-forward calibration remain a
P4B.2 concern; actionable Recommendations remain a later P4C concern.

## Source and maturity contract

The immutable chain is P4A scoring run/item → P3 run/item → FeatureSnapshot. The reference price is
the source snapshot's canonical Decimal `last_close`. Horizon, provider, adjustment basis,
feature-set version, as-of timestamp, quality, symbol, MIC, and completed session must match across
the chain. Horizon is the P3 value of 1–5 trading days and cannot be overridden by the command.

Future sessions start after the P3 completed session and come only from
`US_EQUITY_CORE/2026.v1`. An item matures at terminal session close plus completion grace, with
equality accepted. A horizon requiring a 2027 session is `CALENDAR_OUT_OF_COVERAGE`; no synthetic
calendar date is invented. Emergency closures are not represented by the static 2026 calendar.

## Point-in-Time bars and raw metrics

The service performs no provider or network call. For each exact future session it reads the latest
`TWELVE_DATA_TIME_SERIES`/symbol/`SPLIT_ADJUSTED` bar with `available_at <= observation_as_of`, ordered
by `available_at DESC, bar_key DESC`. Missing, duplicated, mixed, late, non-USD, or otherwise invalid
bars do not create an outcome.

Using Decimal precision 38 and `ROUND_HALF_EVEN` in a local context, P4B.1 stores terminal close,
terminal close return, MFE from future highs, MAE from future lows, exact future-bar count, and the
terminal session. MAE must be no greater than terminal return, which must be no greater than MFE.
Ordered provenance contains only bar ID, session, source identity/version, availability, and content
digest—never OHLC, raw provider payload, URL, or credentials.

## Revisions, modes, and retry

The outcome key includes source scoring item, fixed policy/version, horizon, and a SHA-256 digest of
the ordered future-bar revisions. Corrected bars therefore create a new immutable outcome instead of
overwriting history. Latest-as-of reads use the outcome's latest input availability.

`PROSPECTIVE` means the scoring run was generated no later than the first future-session open.
Otherwise it is `RETROSPECTIVE_REPLAY`. Raw metrics are identical in both modes, but later evaluation
must not merge the populations automatically.

An observation run key includes source scoring run, fixed policy/version, observation as-of, and
completion grace. Exact retry returns its stored run/items before source reads, bar reads,
calculation, inserts, or commits. Migration `0009_daily_feature_outcomes` adds the three P4B.1 tables;
the canonical table count is 22.

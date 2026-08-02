# Versioned positive-close outcome labels

`US_EQUITY_POSITIVE_FORWARD_CLOSE_LABEL/v1` derives one binary label from one immutable
`US_EQUITY_FORWARD_PATH_OBSERVATION/v1` outcome revision:

- `forward_close_return > 0` becomes `POSITIVE`.
- Zero or negative return becomes `NOT_POSITIVE`.

The source must use `TWELVE_DATA_TIME_SERIES`, `US_EQUITY_CORE/2026.v1`, horizon 1–5, a complete
future-bar path, and a valid source chain. Both `PROSPECTIVE` and `RETROSPECTIVE_REPLAY` are retained.
The semantic label identity is source outcome ID plus label policy/version. A corrected outcome is a
new revision with a new ID and therefore a new label key; existing labels are never overwritten.

The label means only that the terminal close exceeded the reference close. It ignores commissions,
spread, slippage, and execution. It is not a probability, confidence, Recommendation, stop result,
or trading-success claim. Target/stop labels remain outside P4B.2A.

Exact retry returns the existing same-digest label before source reads, clock use, ID generation,
insert, or commit. A unique race rolls back and re-reads in a fresh Unit of Work. Same content reuses
the winner; different content raises a sanitized conflict.

# Prediction MVP v1 contract

The first executable research target is a decision-support outcome, not automatic execution.
A source regular session must be complete before a signal is generated. The signal is locked
before the next regular session. Research assumes entry at that next regular-session open and
exit at a fixed future-session close, initially three trading days later.

Each virtual observation uses fixed notional and produces `BUY` or `NO_TRADE`. The first
execution-aligned outcome does not contain a model-generated target or stop. Target and stop
policies belong to a later independently validated slice.

Transaction cost, spread, slippage, and benchmark policies must be versioned before OutcomePolicy
v2 is implemented. Their numeric values are intentionally not invented here. The unresolved
blocker is:

`TRANSACTION_COST_POLICY_VALUES_NOT_FROZEN`

OutcomePolicy v2 and cost-adjusted LabelPolicy v2 are outside this task. Until they exist, the
P4B.2A positive-close label remains `LEGACY_POSITIVE_CLOSE_RESEARCH_LABEL` and cannot support a
claim about executable net-profitable trades.

A later Recommendation Generator must permit these normal outputs:

- `RECOMMEND`
- `WATCH`
- `NO_RECOMMENDATION`
- `MARKET_RISK`
- `DATA_INSUFFICIENT`

No recommendation is an expected result when the opportunity, market, or data contract is not
qualified. PREDICTION, VIRTUAL, and ACTUAL result streams must never be combined.

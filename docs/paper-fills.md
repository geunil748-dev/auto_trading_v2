# Deterministic internal paper fills

## Canonical facts and current state

A `PaperOrder` is the current state of one submitted TradeIntent. A `PaperFill` is a separate,
immutable canonical execution fact. The order advances from `ACCEPTED` to `PARTIALLY_FILLED` and
then `FILLED`, while each fill remains append-only.

Cumulative filled quantity and average fill price are deliberately not stored on either record.
They are derived from the ordered canonical fills, avoiding a second mutable aggregate that could
disagree with execution facts. A future position projector must consume only canonical fills; the
projector, positions, position events, equity, and P&L remain outside this PR.

## `INTERNAL_PAPER_SPLIT_FILL/v1`

The immutable policy accepts only orders from `INTERNAL_PAPER` and creates exactly one fill per
service call. Quantity one has the single-fill plan `(1)`. For quantity two or greater, the plan is:

```text
first_quantity = requested_quantity // 2
second_quantity = requested_quantity - first_quantity
```

Thus 2 becomes `(1, 1)`, 3 becomes `(1, 2)`, 40 becomes `(20, 20)`, and 41 becomes `(20, 21)`.
The first split fill advances the order to `PARTIALLY_FILLED`; the final fill advances it to
`FILLED`. A quantity-one order advances directly from `ACCEPTED` to `FILLED`.

Both fills use the `last_price` of the canonical market snapshot linked through
PaperOrder → TradeIntent → StrategyDecision → Candidate → MarketSnapshot. No live quote is fetched.
There is no slippage, delay, randomness, price improvement, or fee calculation. Fee is always
zero `Money` in the TradeIntent currency.

## Identity and history validation

Fill sequence starts at one and is continuous. The deterministic execution key is exactly:

```text
order:{order_id}|fill-policy:internal-paper-split-fill|version:v1|sequence:{sequence}
```

Changing policy semantics requires a new version; existing `v1` meaning is never changed silently.
The database enforces both unique execution key and unique `(order_id, fill_sequence)` as the final
race defense.

Before any clock call, ID generation, or write, the service validates the canonical source chain,
symbol and accepted request shape. Existing history must match the exact plan, execution keys,
order ID, source price, zero fee, currency, timestamps, contiguous sequence, cumulative quantity,
and order state. Invalid or exhausted history is rejected without repair, upsert, or mutation.

## Atomic order transition

PaperFill insert and PaperOrder transition share one Unit of Work, connection, root transaction,
and commit. The Unit of Work now exposes exactly seven repositories. Repositories never start,
commit, or roll back transactions themselves.

The fill-only transition API permits only:

- `ACCEPTED → PARTIALLY_FILLED`;
- `ACCEPTED → FILLED`;
- `PARTIALLY_FILLED → FILLED`.

One guarded SQL update requires the expected order status and version and increments the version by
exactly one. It changes only status, closed time, updated time, and version. A partial order stays
open; a filled order's closed time equals the final fill execution time. Submission and acceptance
times, broker identity, source TradeIntent, and rejection data are preserved.

A duplicate fill rolls back without an order transition. A missing or stale order transition rolls
back the new fill, preserving the already committed order state. There is no retry, merge, generic
update, delete, or upsert.

## Deliberate limits

Execution remains single-order and single-fill per invocation. There is no batch fill API because
each partial fill is a separate canonical operation and transaction boundary. This slice does not
add a scheduler, background worker, KIS call, position projector, position mutation, average-cost
calculation, or P&L calculation. No V1 fill logic, SQL, credentials, or runtime behavior was read,
copied, or adapted.

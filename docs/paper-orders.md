# Internal paper-order submission

## Canonical boundaries

A `TradeIntent` is the immutable instruction approved by strategy and risk policy. A `PaperOrder`
is the canonical result of submitting exactly one of those instructions to a paper broker. It does
not duplicate the intent's symbol, side, order type, quantity, or price. A `PaperFill` is a later,
separate execution record; this slice creates no fills and performs no position or P&L projection.

The initial adapter is `InternalPaperBroker`, identified by the exact broker code
`INTERNAL_PAPER`. It is a pure deterministic adapter: it uses no database, network, file, clock,
sleep, retry, UUID generation, random source, mutable order book, fill logic, or position logic.
It returns the request's `submitted_at` as `processed_at`.

## Identities and references

`OrderID` is the canonical V2 database identity of a PaperOrder. `ClientOrderID` is the broker
submission identity and is derived deterministically from the source TradeIntent. The current
policy is `TRADE_INTENT_CLIENT_ORDER_ID/v1`, using `UUID5(NAMESPACE_URL, name)` with this exact
name:

```text
urn:auto-trading-v2:client-order:v1:{trade_intent_id}
```

The internal broker reference policy is `INTERNAL_PAPER_REFERENCE/v1`. Accepted and rejected
requests both receive this deterministic reference:

```text
internal-paper:v1:{client_order_id}
```

These deterministic identities support local deduplication. They do not claim external KIS
exactly-once delivery. Before a KIS adapter is introduced, dispatch claiming, an outbox, or an
external broker idempotency design is required.

## Initial outcomes

The internal broker accepts only a valid `USD / BUY / MARKET / no limit price / DAY / positive
quantity` request. A successful submission is stored initially as `ACCEPTED`, with `accepted_at`
set and `closed_at` absent. A valid but unsupported request is a normal broker result and is stored
as a canonical `REJECTED` order with `closed_at` and a rejection code; it is not an application
failure.

Rejections use this exact priority:

1. non-USD: `UNSUPPORTED_CURRENCY`
2. non-BUY: `UNSUPPORTED_SIDE`
3. non-MARKET: `UNSUPPORTED_ORDER_TYPE`

A technical `PaperBrokerError` is different from a rejection. It is safely translated, rolls back
the transaction, and writes no order. An invalid broker result is also rejected before `OrderID`
creation or persistence.

## Deduplication and transactions

Submission is deliberately single-intent: there is no `submit_all(candidate_id)` operation and no
candidate batch of broker side effects. Future scheduling can dispatch pending TradeIntents one at
a time, keeping every strategy order independent.

At most one PaperOrder can exist for a TradeIntent. The service checks the TradeIntent identity,
deterministic ClientOrderID, and returned broker reference before insert. The database remains the
final race defense through:

- unique `trade_intent_id`;
- unique `client_order_id`;
- filtered unique `(broker_code, broker_order_ref)` when the reference is not null.

The PaperOrder Repository never starts, commits, or rolls back a transaction and exposes no generic
update, delete, or upsert API. The Unit of Work owns one root transaction and one connection.
Successful ACCEPTED and REJECTED orders commit once; failures roll back. PR 9 adds only the dedicated
fill transition and a seventh, immutable PaperFill Repository.

## Deliberate limits

PR 8 itself did not implement post-submission state transitions. PR 9 now adds deterministic partial
and full internal fills as documented in [paper fills](paper-fills.md), but still does not implement
cancellation, expiration, slippage, non-zero fees, positions, events, equity, P&L, scheduling, KIS,
or notifications.
No V1 broker implementation was read, copied, adapted, or made compatible with this boundary.

# Deterministic TradeIntent와 초기 수량 정책

## 의미와 경계

Strategy decision은 저장된 필터 결과를 바탕으로 전략이 선택한 `ENTER_LONG`, `SKIP`,
`OBSERVE` 행동이다. TradeIntent는 그중 실제 주문을 의도한 결정과 요청 수량을 canonical
형태로 기록하지만 주문 자체는 아니다. `PaperOrder`, broker 호출, 체결, 포지션 및 손익은 이
단계에서 생성하지 않는다.

현재 entry 전략의 `ENTER_LONG`만 TradeIntent eligibility를 가진다. `SKIP`은 진입하지 않기로
한 정상 결정이고 `OBSERVE`는 관찰 전용 결정이므로 둘 다 intent를 만들지 않는다. 저장된
decision만 source로 사용하며 필터나 전략 action을 다시 계산하지 않는다.

## FIXED_USD_NOTIONAL v1

초기 paper risk policy는 코드에 고정된 `FIXED_USD_NOTIONAL`의 `v1`이다.

- currency: `USD`
- maximum requested notional: `USD 1,000`
- reference price: candidate가 참조하는 `market_snapshot.last_price`
- side / order type / time in force: `BUY` / `MARKET` / `DAY`
- `limit_price`: `NULL`
- requested quantity: `floor(Decimal("1000") / reference_price)`
- fractional share: 지원하지 않음
- minimum approved quantity: 1

계산은 `Decimal`과 precision 38의 local context만 사용한다. 정수 변환은 `ROUND_FLOOR`이며
global Decimal context를 변경하지 않는다. 결과가 0이면 `QUANTITY_BELOW_MINIMUM`으로
거부하고 intent write와 commit을 수행하지 않는다. 승인된 estimated notional은 항상 USD
1,000 이하이다.

이 정책은 account cash, 기존 position, portfolio exposure, fee 또는 slippage를 확인하거나
sizing에 포함하지 않는다. policy 의미나 금액을 변경할 때 기존 `v1`을 수정하지 말고 새
version을 추가해야 한다. 정책은 `.env`로 override하지 않는다.

## Idempotency와 transaction

semantic idempotency key의 정확한 형식은 다음과 같다.

```text
decision:{decision_id}|intent-policy:fixed-usd-notional|version:v1
```

key에는 TradeIntentID, timestamp, quantity 또는 random 값이 포함되지 않는다. 같은 decision과
policy version은 항상 같은 key를 만든다. policy version이 변경되면 key도 변경된다.

DB의 `decision_id UNIQUE`와 `idempotency_key UNIQUE`가 최종 중복 방어선이다. 사전 조회만으로
중복 방지를 보장하지 않으며, 기존 intent를 반환·수정·삭제하거나 upsert하지 않는다.

한 candidate의 eligible intent는 built-in strategy catalog 순서로 하나의 Unit of Work와 하나의
transaction에서 저장한다. 모든 intent는 동일한 snapshot price, 수량 및 `created_at`을 공유한다.
중간에 duplicate가 발생하면 이번 batch 전체를 rollback하므로 부분 신규 batch가 남지 않는다.

## 현재 제한과 다음 단계

현재 canonical schema에는 별도의 risk evaluation table이 없으므로 risk rejection은 안전한
application error로만 반환되고 DB에 기록하지 않는다. 향후 trading event writer가 추가될 때
canonical event 기록을 설계한다.

다음 단계는 TradeIntent를 소비하는 `PaperOrder`와 `InternalPaperBroker`다. 이번 구현에는
PaperOrder Repository, ClientOrderID 생성, order state machine, fill, position projector, P&L,
KIS/Telegram/network 또는 scheduler가 없다. V1 수량·risk 로직을 참고하거나 복사하지 않고 V2
primitive, Repository 및 Unit of Work 경계만 사용한다.

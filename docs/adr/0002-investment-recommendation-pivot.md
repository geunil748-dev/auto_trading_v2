# ADR 0002: Investment recommendation pivot

## Status

Accepted.

## Context

기존 V2는 deterministic filter, StrategyDecision, TradeIntent, PaperOrder, PaperFill,
PaperPosition으로 이어지는 자동매매·paper simulation 기반을 단계적으로 구축했다. 그러나
제품의 최종 목표는 자동 주문이 아니라 해외 주식 투자 추천이다. 사용자는 Recommendation을
받고 실제 매매 여부와 시점을 직접 결정한다.

과거 파이프라인에는 재현 가능한 시뮬레이션과 정책 검증 자산이 있으므로 이를 삭제하면 감사
가능성과 회귀 검증 능력을 잃는다. 동시에 TradeIntent를 사용자 추천으로 재해석하면 주문
요청과 설명 가능한 사용자 출력의 의미가 섞인다.

## Decision

`Recommendation`을 향후 시스템의 canonical 사용자 출력으로 정의한다. Recommendation은
TradeIntent, StrategyDecision, FeatureSnapshot과 서로 다른 aggregate이며 자동 주문을
의미하지 않는다. 추천을 받은 사용자가 외부 증권 시스템에서 수동으로 거래한다.

canonical 흐름은 다음과 같다.

```text
External Source Observations
  -> Point-in-Time FeatureSnapshot
  -> Recommendation
  -> Notification
  -> UserAction
  -> PREDICTION / VIRTUAL / ACTUAL Outcome
  -> Performance Evaluation
```

Recommendation 생성 결과에는 추천, 관망, 데이터 부족처럼 기록 가능한 정상 결과가 포함될
수 있다. 데이터 부족이나 시장 위험으로 추천하지 않는 것은 기술 실패가 아니다.

기존 paper 경로는 선택적 shadow simulation으로 보존한다.

```text
Recommendation
  -> optional shadow simulation
  -> TradeIntent
  -> PaperOrder
  -> PaperFill
  -> PaperPosition
  -> VirtualOutcome
```

Outcome은 다음 의미를 분리한다.

- `PREDICTION`: 추천 시점에 선언한 미래 기대
- `VIRTUAL`: 동일 추천의 선택적 paper simulation 결과
- `ACTUAL`: 사용자가 제공하거나 확인한 실제 행동·성과

PR13의 SELL intent 작업은 향후 optional simulation 후보이며, 현재 official runtime이나
Recommendation 구현으로 간주하지 않는다.

## Consequences

기존 자동매매 코드는 삭제하지 않는다. 선택적 shadow simulation, 회귀 테스트, 정책 비교에
재사용하되 Recommendation 없이 자동으로 실제 주문하는 최종 제품 흐름은 만들지 않는다.
FeatureSnapshot, Recommendation, Outcome 사이에는 이후 명시적인 계약을 추가하며, 이 P0는
그중 FeatureSnapshot 기반만 구현한다.

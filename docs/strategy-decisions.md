# 결정론적 전략 결정

PR 6는 이미 저장된 canonical filter evaluation을 읽어 candidate 기반 전략 결정을 만든다.
필터는 시장 입력을 평가하고, 전략은 그 저장 결과를 `ENTER_LONG`, `SKIP`, `OBSERVE` 중 하나로
변환한다. 전략 엔진은 필터 check, threshold 또는 score를 다시 계산하지 않는다.

## 경계와 데이터 흐름

Application service는 candidate와 해당 candidate의 filter evaluation을 기존 Repository로
조회한다. Domain에는 필요한 evaluation 값만 담은 immutable `StrategySignal`을 전달한다.
Domain은 Repository, Unit of Work, SQLAlchemy, `.env`, Clock, UUID 생성기 또는 네트워크를 모른다.

```text
candidate + canonical filter_evaluations 4개
    → pure strategy decision engine
    → candidate strategy_decisions 4개
    → one Unit of Work / one commit
```

이번 범위는 candidate 기반 결정만 표현한다. `position_id`는 저장 시 `NULL`이며, position 기반
`EXIT_LONG` 결정은 포함하지 않는다. 결정은 `filter_evaluation_id`로 세부 필터 근거와 연결되므로
filter details 전체를 reason code에 복제하지 않는다.

## Built-in 전략과 stable identity

모든 전략 version은 `v1`이고 초기 FilterSet과 1:1로 연결된다.

| Strategy | Stable StrategyID | FilterSet | Action policy |
| --- | --- | --- | --- |
| `STRICT_ENTRY` | `10c3fbc4-7db0-5980-9f85-8fbfc944a26c` | `STRICT` `v1` | passed면 `ENTER_LONG`, 아니면 `SKIP` |
| `BALANCED_ENTRY` | `4bb90f07-6f29-5a8f-ada7-7d5952eb0c9a` | `BALANCED` `v1` | passed면 `ENTER_LONG`, 아니면 `SKIP` |
| `SCORE_ONLY_ENTRY` | `78b1169a-80d4-5894-8f45-b3c85cf5b2b6` | `SCORE_ONLY` `v1` | persisted passed 값을 그대로 사용 |
| `OBSERVATION_ONLY` | `86132628-8c1d-5eec-abcc-02ca3c3c39a5` | `OBSERVATION` `v1` | 항상 `OBSERVE` |

`OBSERVATION_ONLY`는 `passed`나 score와 무관하게 주문 진입 신호를 만들지 않는다. `OBSERVE`는
분석용 기록이며 `ENTER_LONG`이 아니다.

StrategyID는 장기 identity다. action mapping이나 판단 의미가 바뀌면 strategy version을
증가시킨다. 연결 filter evaluation version이 바뀔 때도 strategy version 변경 여부를
명시적으로 검토한다. 기존 `v1` 의미는 조용히 변경하지 않는다. StrategyID, version, 정책은
재현 가능하도록 코드로 version 관리하며 `.env`나 DB 설정으로 덮어쓰지 않는다.

## Action과 reason code

허용되는 Domain action은 다음 세 가지뿐이다.

- `ENTER_LONG`: 해당 entry 정책이 저장된 filter evaluation의 `passed=true`를 허용했다.
- `SKIP`: 해당 entry 정책의 filter evaluation이 실패했다.
- `OBSERVE`: 관찰 결과만 저장하며 주문이나 TradeIntent를 만들지 않는다.

통과한 entry 정책은 정확히 다음 순서를 사용한다.

```text
FILTER_SET_PASSED
ENTRY_ALLOWED
```

실패한 entry 정책은 다음 순서를 사용한다.

```text
FILTER_SET_FAILED
<filter evaluation blocking_reason_codes>
ENTRY_BLOCKED
```

Reason code는 `^[A-Z][A-Z0-9_]{0,63}$` 형식이다. Filter details의 top-level
`blocking_reason_codes`만 읽으며 JSON array, string 항목, 최대 16개를 검증한다. 중복은 원래
순서를 보존해 제거한다. 실패 evaluation에 유효한 blocking code가 없으면 canonical data가
손상된 것으로 처리한다. 오류에는 details 또는 reason-code JSON 전체를 포함하지 않는다.

`OBSERVATION_ONLY`의 reason code는 항상 `OBSERVATION_ONLY` 하나다.

## Deterministic decision key

Candidate 결정의 semantic key는 다음 exact 형식이다.

```text
candidate:{candidate_id}|strategy:{strategy_id}|version:{strategy_version}
```

Filter evaluation ID, DecisionID, timestamp 또는 random 값은 key에 포함하지 않는다. 같은
candidate/strategy/version은 항상 같은 key를 만들며 공백 없이 160자 이하여야 한다.

## Application transaction 정책

`CandidateStrategyDecisionService.decide_all(candidate_id)`는 다음 순서를 지킨다.

1. 한 Unit of Work에서 candidate와 모든 filter evaluation을 조회한다.
2. 각 전략의 exact FilterSetID와 evaluation version `v1` 조합을 선택한다.
3. 네 evaluation의 존재, candidate 일치, score와 details contract를 write 전에 검증한다.
4. Clock을 정확히 한 번 호출하고 같은 `decided_at`을 네 결정에 사용한다.
5. catalog 순서로 DecisionID와 semantic key를 만들고 네 row를 추가한다.
6. 모두 성공한 경우에만 정확히 한 번 commit한다.

필수 evaluation이 하나라도 없거나 잘못되면 decision write는 0건이다. Repository add 중
duplicate가 발생하면 이번 batch 전체를 rollback한다. 기존 row를 자동 반환하거나 수정하지
않으며 upsert, overwrite, delete 후 재삽입도 하지 않는다. `decision_key` unique와
candidate/strategy/version filtered unique index가 최종 중복 방어선이다.

같은 candidate를 같은 strategy version으로 재실행하면 safe conflict가 발생하고 기존 네 row는
유지된다. 다른 의미의 재평가는 명시적인 strategy version 정책이 필요하다.

## 포함하지 않는 기능

이번 PR은 TradeIntent, 주문 수량·가격, risk manager, broker, order/fill, position projector,
P&L, candidate 수집, filter 재계산, KIS/Telegram, scheduler, CLI/UI를 구현하지 않는다.
`TradeIntent`와 위험·수량 정책은 전략 결정 이후의 별도 단계다.

모든 write 검증은 guarded `auto_trading_v2_test_*` 임시 MSSQL DB에서만 수행한다. 개발 DB의
`scripts/check_persistence.py`는 계속 읽기 전용이다.

# ADR 0003: Point-in-Time FeatureSnapshots

## Status

Accepted.

## Context

추천과 모델 성능은 추천 당시 실제로 이용 가능했던 정보만으로 재현돼야 한다. 나중에 수정된
데이터, 사후 발표 정보, 미래 가격이나 label이 입력에 섞이면 backtest와 실제 성능을 비교할 수
없다. 단일 가격 관측인 MarketSnapshot만으로는 여러 출처에서 정규화한 모델 입력과 각 입력의
이용 가능 시점을 표현할 수 없다.

## Decision

`FeatureSnapshot`은 `(symbol, as_of, trading-day horizon, feature set)`에 대한 불변의 정규화
모델 입력 bundle이다. `MarketSnapshot`은 특정 시각의 단일 가격 관측이며 둘은 대체 관계가
아니다. FeatureSnapshot은 Recommendation, StrategyDecision 또는 Outcome이 아니다.

시간 의미는 다음과 같다.

- `observed_at`: 원천 사건이나 값이 실제로 관측된 시각
- `available_at`: 해당 정보가 시스템 또는 일반 시장에 처음 이용 가능해진 시각
- `as_of`: snapshot이 사용할 수 있는 정보의 cutoff
- `generated_at`: 주입된 Clock으로 snapshot 생성을 시도한 시각

모든 시각은 timezone-aware이며 UTC로 정규화한다. 다음 순서를 강제하고 equality를 허용한다.

```text
observed_at <= available_at <= as_of <= generated_at
```

`available_at`을 신뢰할 수 없으면 fetch 시각 등으로 추정하지 않고 snapshot 전체를 거부한다.
한 provenance라도 cutoff 이후라면 저장하지 않는다.

`TradingDayHorizon`은 `TRADING_DAY` 단위의 정수 1~5만 허용한다. 이 기반에서는 거래소 달력
계산이나 calendar-day 변환을 하지 않는다.

### Feature payload와 provenance

feature payload는 deterministic JSON object이다. 문자열 key와 `null`, bool, int, string,
list, object, 유한한 Decimal을 허용한다. Decimal은 trailing zero와 지수 표기를 제거한 고정
소수점 문자열로 canonicalize한다. Python float, NaN, infinity, 비문자열 key, tuple, set,
bytes, datetime은 중첩 깊이와 관계없이 거부한다. object key는 정렬하고 UTF-8 Unicode
compact JSON으로 직렬화한다.

payload에는 raw API 응답, 뉴스 본문, URL, credential, 대형 시계열, 미래 가격·수익률,
label, outcome, recommendation 또는 prediction 결과를 저장하지 않는다.

각 provenance entry는 안전한 `source_code`, 불투명 `source_record_key`, `observed_at`,
`available_at`, 원천 content의 소문자 SHA-256, 선택적 `source_version`만 가진다. URL과
secret은 금지한다. 동일 source identity의 중복 entry는 거부하고 canonical order로 정렬한다.
`latest_input_available_at`은 entry의 최댓값을 계산하며 caller 값을 받지 않는다.

### Quality

- `READY`: feature와 provenance가 각각 하나 이상이고 reason은 비어 있음
- `DEGRADED`: feature와 provenance가 각각 하나 이상이고 reason이 하나 이상

reason code는 중복을 거부하고 정렬한다. `BLOCKED`는 저장 상태가 아니다. 유효한 snapshot을
만들 수 없으면 안전한 validation error를 발생시키며 write/commit하지 않는다.

### Identity and content

semantic identity는 다음 필드뿐이다.

```text
symbol, feature_set_code, feature_set_version, horizon_trading_days, as_of
```

`snapshot_key`는 정렬된 canonical identity JSON의 SHA-256이며
`feature-snapshot:v1:{64 lowercase hex}` 형식이다. ID, generated_at, payload, provenance,
quality는 identity에서 제외한다.

`content_digest`는 canonical feature values, canonical provenance, quality status, 정렬된
quality reason codes, 계산된 latest input available 시각의 SHA-256이다. ID, snapshot_key,
generated_at, recorded_at은 제외한다.

동일 identity·동일 digest는 exact retry로 기존 row를 반환한다. 동일 identity·다른 digest는
sanitized conflict이며 overwrite, upsert, delete/reinsert하지 않는다. 입력 mapping이나
provenance 순서는 digest에 영향을 주지 않는다. 다른 identity는 내용이 같아도 별도 snapshot이다.
DB unique race는 rollback 후 새 Unit of Work에서 재조회하여 동일 digest면 retry, 다르면
conflict로 판정한다.

## Consequences

`trading.feature_snapshots`는 독립 aggregate로 추가되며 Candidate나 StrategyDecision FK를
두지 않는다. 외부 API 수집, feature engineering, 모델, Recommendation, Outcome, 알림,
scheduler와 자동 주문은 이 ADR 구현 범위가 아니다.

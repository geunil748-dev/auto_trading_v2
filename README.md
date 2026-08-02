# auto_trading_v2

## 현재 목표: 해외 주식 투자 추천

최종 사용자 출력은 자동 주문이 아니라 canonical `Recommendation`이며, 사용자가 실제 매매를
직접 결정합니다. 현재 P0는 미래 정보 누수를 차단하는 불변 Point-in-Time `FeatureSnapshot`
도메인·계약·영속성 기반을 제공하고, P1은 이를 필수 근거로 참조하는 immutable
`Recommendation` 도메인·생성 계약·영속성 기반을 추가합니다. 기존
TradeIntent→PaperOrder→PaperFill→PaperPosition 경로는 Recommendation과 연결하지 않고 선택적
shadow simulation 기반으로 유지합니다.

자세한 결정은 [추천 시스템 전환 ADR](docs/adr/0002-investment-recommendation-pivot.md)과
[Point-in-Time FeatureSnapshot ADR](docs/adr/0003-point-in-time-feature-snapshots.md),
[canonical Recommendation ADR](docs/adr/0004-canonical-recommendations.md)을 참고하십시오.

## 로컬 설정

V2 로컬 설정은 repository root의 `.env`를 명시적으로 로드하며 Git에 포함하지 않습니다.
실제 `.env`가 이미 있으면 덮어쓰지 마십시오. 새로 시작할 때만 다음 명령을 사용합니다.

```powershell
Copy-Item .env.example .env
python scripts/check_config.py
```

진단 명령은 DB나 외부 API에 연결하지 않으며 secret과 raw URL을 출력하지 않습니다. 설정 key,
source precedence, KIS paper 및 Telegram disabled 규칙은
[설정 문서](docs/configuration.md)를 참고하십시오.

Twelve Data는 최초 실제 일봉 provider이며 기본적으로 disabled입니다. 로컬 ignored `.env`에
명시적으로 enable/key를 구성한 경우에만 네트워크를 사용합니다. provider 선택은 항상
명시적이고 자동 fallback은 없습니다. 상세 운영 계약은
[Twelve Data 문서](docs/providers/twelve-data.md)와
[provider matrix](docs/providers/provider-matrix.md)를 참고하십시오.

Alpaca IEX는 `ALPACA_IEX_STOCK_BARS`라는 별도 validation-only 일봉 source입니다. IEX 한
거래소의 단일 종목 historical bars만 읽으며 Twelve Data의 fallback, 대체 source, 자동
선택 기준이 아닙니다. 비교 서비스는 두 source를 각각 Point-in-Time 조회한 뒤 겹치는
session의 close 차이와 return 방향 일치율만 immutable report로 계산합니다. 결과를
저장하거나 Recommendation·TradeIntent·주문을 만들지 않습니다. 자세한 계약은
[Alpaca IEX provider](docs/providers/alpaca-iex.md)와
[ADR 0007](docs/adr/0007-alpaca-iex-validation-provider.md)을 참고하십시오.

`auto_trading_v2`는 기존 `auto_trading`과 코드, 데이터베이스, 런타임 상태를 공유하지 않는
독립 프로젝트입니다. Microsoft SQL Server canonical schema 위에서 filter evaluation, strategy
decision, TradeIntent, internal paper fill과 BUY position projection 경계를 구현합니다. 실제
주문 실행은 포함하지 않습니다.

## 개발 환경

- Python 3.12 이상
- 공식 금액과 가격 계산은 `Decimal` 사용
- 시간은 UTC aware `datetime`만 사용
- 식별자는 타입이 구분되는 UUID 값 객체로 표현

```powershell
python -m pip install -e ".[dev]"
python -m pytest
ruff check .
ruff format --check .
mypy src scripts
```

## MSSQL 준비와 마이그레이션

V2는 기존 SQL Server 인스턴스를 사용할 수 있지만, V1과 분리된 `auto_trading_v2`
데이터베이스와 `trading` 스키마만 사용합니다. URL은 `mssql+pyodbc` SQLAlchemy 형식이어야
하며 저장소나 로그에 실제 값을 남기지 않습니다. 설치된 ODBC 드라이버는 다음처럼 확인합니다.

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

PowerShell:

```powershell
$env:AUTO_TRADING_V2_MSSQL_ADMIN_URL = "<redacted-admin-sqlalchemy-url>"
$env:AUTO_TRADING_V2_DATABASE_URL = "<redacted-v2-database-url>"
$env:AUTO_TRADING_V2_TEST_ADMIN_URL = "<redacted-test-admin-url>"
$env:AUTO_TRADING_V2_TEST_ADMIN_TRANSPORT = "tcp_url"

python scripts/create_database.py
alembic upgrade head
alembic current
alembic check
python -m pytest tests/unit
python -m pytest tests/integration -m integration
```

Bash:

```bash
export AUTO_TRADING_V2_MSSQL_ADMIN_URL="<redacted-admin-sqlalchemy-url>"
export AUTO_TRADING_V2_DATABASE_URL="<redacted-v2-database-url>"
export AUTO_TRADING_V2_TEST_ADMIN_URL="<redacted-test-admin-url>"
export AUTO_TRADING_V2_TEST_ADMIN_TRANSPORT="tcp_url"

python scripts/create_database.py
alembic upgrade head
alembic current
alembic check
python -m pytest tests/unit
python -m pytest tests/integration -m integration
```

`AUTO_TRADING_V2_TEST_ADMIN_URL`이 없으면 통합 테스트는 명시적으로
`AUTO_TRADING_V2_MSSQL_ADMIN_URL`을 재사용할 수 있습니다. 테스트는 실행마다
`auto_trading_v2_test_` 접두사의 임시 DB를 만들고 자신이 만든 DB만 삭제합니다. 세 변수 중
필요한 URL이 없으면 해당 통합 테스트는 skip됩니다. URL을 화면에 출력하거나 `echo`하지
마세요. 상세 정책은 [데이터베이스 스키마 문서](docs/database-schema.md)를 참고하세요.

로컬 Windows의 default SQL Server instance에서만 통합 테스트 관리 경로를
`local_shared_memory`로 명시적으로 선택할 수 있습니다. 이 모드는 SQLAlchemy admin/target에
LPC Windows 통합 인증을 사용하며, DotNet target은 기존 공식 TCP SQL 인증 설정을 유지합니다.
기본값은 `tcp_url`이고 두 transport 사이의 자동 fallback은 없습니다. 실제 `.env`를 변경하지
않고 실행하려면 현재 process에만
`AUTO_TRADING_V2_TEST_ADMIN_TRANSPORT=local_shared_memory`를 설정합니다.

## 설계 원칙

- 의존 방향은 Adapter/CLI → Application → Domain입니다.
- Domain은 프레임워크, 환경 변수, DB, 네트워크에 의존하지 않습니다.
- `Money`와 `Price`는 `float`의 암시적 입력을 허용하지 않습니다.
- 소수점 반올림 기본 정책은 `ROUND_HALF_EVEN`이지만, PR 1에서는 통화별 자릿수를 가정해
  일괄 양자화하지 않습니다.
- 모든 타임스탬프는 UTC로 정규화하고 RFC 3339의 `Z` 형식으로 직렬화합니다.
- 기본 ID 팩토리는 UUID4를 사용합니다. 향후 UUIDv7 전환은 팩토리 구현 교체로 처리합니다.

## 현재 범위

현재 포함되는 것은 도메인 원시 타입, 변동성 돌파와 deterministic filter/strategy/risk 계산,
Clock과 typed ID 포트, SQLAlchemy Core Repository, 명시적 Unit of Work, canonical metadata 및
additive Alembic 마이그레이션, immutable DailyMarketBar, Twelve Data 일봉 adapter,
21-session daily technical
FeatureSnapshot과 canonical Recommendation 생성·저장 기반입니다. Recommendation은 사용자에게
제공할 추천 또는 비추천 결과를 검증·보존할 뿐 실제 값을 계산하지 않습니다. 실제 외부 데이터
기반 중 구현된 범위는 Twelve Data completed daily bars뿐이며, 모델, ranking/run,
Outcome, 알림, 스케줄러와 실제 매매는 포함하지 않습니다. 상세 계약은
[Recommendation 문서](docs/recommendations.md)를 참고하세요.

자세한 경계는 [아키텍처 경계 문서](docs/architecture-boundaries.md)를 참고하세요.

## Prediction P2 daily market features

완료된 미국주식 일봉은 기존 `MarketSnapshot`과 분리된 immutable `DailyMarketBar`로 저장됩니다.
Point-in-Time 조회는 `available_at <= as_of`인 session별 최신 revision만 선택합니다.
`US_EQUITY_DAILY_TECHNICAL/v1` builder는 최신 21개 `SPLIT_ADJUSTED` bar에서 Decimal 기반
17개 기술 feature를 계산하며 READY, DEGRADED, DATA_INSUFFICIENT를 구분합니다.
`TWELVE_DATA_TIME_SERIES`는 공식 `/time_series` API에서 split-adjusted OHLC를 적재합니다.
조정 거래량 의미는 미검증이므로 volume은 `None`, snapshot은
`DEGRADED / VOLUME_DATA_INCOMPLETE`입니다. Recommendation 계산은 구현하지 않습니다.

상세 계약은 [DailyMarketBar](docs/daily-market-bars.md),
[feature building](docs/feature-building.md), [ADR 0005](docs/adr/0005-canonical-daily-market-bars.md),
[multi-provider ADR](docs/adr/0006-multi-provider-market-data.md)를 참고하세요.

## Prediction P3 multi-symbol daily feature pipeline

P3 accepts an explicit caller-provided universe of 1 to 100 US-equity listings and freezes it as
an immutable `UniverseSnapshot`. Members are ordered by listing MIC and then symbol; the supported
MICs are `XNGS`, `XNGM`, `XNCM`, `XNYS`, and `XASE`. A universe is an evaluation set, not a ranking.

`DailyFeaturePipelineService` resolves one shared completed session through the P2.2 calendar,
performs a provider-budget preflight, and processes members sequentially. One run uses exactly one
provider: `TWELVE_DATA_TIME_SERIES` is the primary feature source and
`ALPACA_IEX_STOCK_BARS` remains validation-only. There is no automatic fallback, provider blending,
or parallel provider request path. Symbol failures are isolated; authentication, configuration,
schema, calendar-coverage, and persistence failures stop the remaining work safely. Three
consecutive transient failures open the bounded v1 circuit.

The immutable run and per-symbol items preserve READY, DEGRADED, DATA_INSUFFICIENT, NO_DATA, error,
and not-attempted outcomes. Exact retry returns the existing aggregate with zero provider network,
DailyMarketBar writes, or FeatureSnapshot builds. Migration `0007_multi_symbol_feature_pipeline`
adds `universe_snapshots`, `daily_feature_pipeline_runs`, and `daily_feature_pipeline_items`, taking
the canonical table count from 14 to 17. P3 creates FeatureSnapshots only; scoring, ranking,
Recommendation generation, TradeIntent, broker, and order behavior remain excluded for P4.

See [universe and feature pipeline](docs/universe-and-feature-pipeline.md) and
[ADR 0009](docs/adr/0009-multi-symbol-daily-feature-pipeline.md).

## Prediction P4A transparent relative scoring

P4A consumes exactly one persisted P3 run and compares only its eligible
`US_EQUITY_DAILY_TECHNICAL/v1` FeatureSnapshots. Policy
`US_EQUITY_DAILY_TECHNICAL_RELATIVE_SCORE/v1` calculates Decimal-only cross-sectional percentiles
and component scores. Ranking policy `QUALITY_TIERED_CROSS_SECTIONAL_PERCENTILE/v1` always ranks
READY items before the two supported volume-related DEGRADED states, then applies deterministic
score, MIC, and symbol tie-breaks.

The resulting 0-to-100 value is a same-run relative score. It is neither a probability nor an
expected return and it is not comparable across different universes or runs. P4A creates no
Recommendation, entry/target/stop plan, TradeIntent, broker request, or order. Migration
`0008_daily_feature_scoring` adds immutable scoring run/item audit tables and raises the canonical
table count from 17 to 19. See [relative scoring](docs/relative-scoring.md) and
[ADR 0010](docs/adr/0010-transparent-relative-scoring.md).

## Prediction P4B.1 prospective forward outcomes

P4B.1 observes one eligible persisted P4A scoring run against existing canonical DailyMarketBars.
It takes the reference price from the source FeatureSnapshot `last_close`, derives the next exact
1–5 official trading sessions from the P3 horizon and `US_EQUITY_CORE/2026.v1`, and stores only
terminal close return, MFE, and MAE. Each read is Point-in-Time at `observation_as_of`; a corrected
bar path creates a new immutable outcome revision.

`PROSPECTIVE` scoring existed by the first future open, while `RETROSPECTIVE_REPLAY` was produced
later. The modes remain separate evidence populations. This slice is not a prediction, probability,
label, expected value, Recommendation, entry/target/stop proposal, or VIRTUAL/ACTUAL trade. Migration
`0009_daily_feature_outcomes` adds three tables and raises the canonical count from 19 to 22. The
calendar is limited to 2026 and future bars must already exist canonically. See
[forward outcomes](docs/forward-outcomes.md) and
[ADR 0011](docs/adr/0011-prospective-forward-outcome-observation.md).

아래 PR 5~12 절은 현재 자동 주문 제품 목표가 아니라, 향후 Recommendation의 선택적 shadow
simulation으로 재사용할 수 있는 역사적 기반을 기록합니다.

## PR 5 deterministic filtering

The current V2 foundation evaluates one canonical candidate and market snapshot against four stable
filter sets (`STRICT`, `BALANCED`, `SCORE_ONLY`, and `OBSERVATION`) and atomically stores only their
versioned evaluation rows. Filtering is pure Decimal-based Domain policy; application orchestration
injects the clock and evaluation-ID factory and uses the existing Repository/Unit of Work boundary.
No strategy, order, broker, fill, position, P&L, scheduler, or external API behavior is included.

See [deterministic filtering policy](docs/filtering.md) for thresholds, scoring, stable IDs, details
JSON, and re-evaluation rules.

## PR 6 deterministic strategy decisions

저장된 네 filter evaluation을 `STRICT_ENTRY`, `BALANCED_ENTRY`, `SCORE_ONLY_ENTRY`,
`OBSERVATION_ONLY`의 결정으로 변환하고 기존 `strategy_decisions` table에 원자적으로 저장합니다.
전략은 필터를 재계산하지 않으며, `OBSERVATION_ONLY`는 항상 `OBSERVE`입니다. TradeIntent, 주문,
브로커, 체결, 포지션과 P&L은 아직 생성하지 않습니다.

Stable StrategyID, version, reason code, decision key와 rollback 정책은
[전략 결정 문서](docs/strategy-decisions.md)를 참고하세요.

## PR 7 deterministic TradeIntent와 수량 정책

저장된 네 strategy decision 중 `ENTER_LONG`만 canonical `trade_intents`로 변환합니다. 초기
`FIXED_USD_NOTIONAL/v1` 정책은 snapshot last price를 기준으로 USD 1,000 이하의 정수 수량을
계산하며, 여러 eligible intent를 하나의 Unit of Work에서 원자적으로 저장합니다. `SKIP`과
`OBSERVE`는 intent를 만들지 않고 duplicate는 batch 전체를 rollback합니다. PaperOrder와 broker는
아직 생성하지 않습니다.

정확한 수량, idempotency key, transaction 및 제한사항은
[TradeIntent 정책 문서](docs/trade-intents.md)를 참고하세요.

## PR 8 internal paper-order submission

PR 8 submits one canonical TradeIntent at a time to the deterministic `InternalPaperBroker` and
atomically stores either an `ACCEPTED` or `REJECTED` PaperOrder through the existing Unit of Work.
ClientOrderID and broker references are versioned and deterministic. This slice does not create
fills, update positions, calculate P&L, call KIS, or schedule submissions. See
[internal paper-order submission](docs/paper-orders.md) for the identity, rejection, transaction,
and deduplication policies.

## PR 9 deterministic internal paper fills

`INTERNAL_PAPER_SPLIT_FILL/v1` now records exactly one immutable canonical PaperFill per call and
atomically advances its PaperOrder with optimistic status/version guards. Quantity one fills once;
larger quantities split deterministically into two fills using the source snapshot's last price and
zero fee. Positions, events, equity, P&L, KIS, and scheduling remain unimplemented. See
[deterministic paper fills](docs/paper-fills.md) for policy, identity, history, and rollback rules.

## PR 10 canonical BUY Fill Position Projector

The Position Projector now accepts one canonical `fill_id` and derives strategy, symbol, currency,
quantity, and price through the existing Fill-to-snapshot chain. A first BUY fill atomically creates
an OPEN PaperPosition and `OPENED` PositionEvent; later BUY fills append `INCREASED` events and
optimistically update quantity, weighted average cost, and version. Fill-level idempotency is
protected by lookup and existing MSSQL unique constraints. SELL, closing, P&L, equity, KIS, and
scheduling remain outside this slice. See
[canonical BUY Fill projection](docs/position-projector.md) for calculation and rollback rules.

## PR 11 position decision canonical snapshot source

Position-based StrategyDecision persistence now stores both the canonical `position_id` and the
exact `market_snapshot_id` used as its source. Additive migration `0002_position_snapshot` adds the
snapshot FK, source-shape checks, semantic filtered uniqueness, and lookup indexes while preserving
existing candidate decisions. The immutable position contract accepts only `EXIT_LONG` or `SKIP`,
and the existing StrategyDecision Repository gains position-specific add/get/semantic lookup
methods without increasing the Unit of Work's nine repositories.

This slice does not calculate take-profit, stop-loss, time-exit, stale-snapshot policy, or create
SELL intents. See [position decision source boundary](docs/position-decision-source.md).

## PR 12 version-pinned deterministic EXIT_LONG decisions

Position exit evaluation now pins each decision to the exact canonical PositionEvent version and
the exact MarketSnapshot. `FIXED_POSITION_EXIT/v1` uses Decimal return calculations with inclusive
-5% stop-loss, +10% take-profit, and six-hour elapsed-time thresholds. Snapshot age is limited to
five minutes with 30 seconds of future clock-skew tolerance, and the initial policy supports USD
positions from `STRICT_ENTRY`, `BALANCED_ENTRY`, and `SCORE_ONLY_ENTRY`.

Repeated evaluation of the same position/snapshot/strategy tuple returns the immutable existing
decision. This slice does not create SELL intents or orders, reduce or close positions, calculate
P&L/equity, write trading events, schedule work, or call KIS. See
[version-pinned EXIT_LONG decisions](docs/position-exit-decisions.md) and
[position decision source boundary](docs/position-decision-source.md).

## Prediction P2.2 US equity completed-session calendar

`US_EQUITY_CORE / 2026.v1` now provides a deterministic NYSE/Nasdaq core-session
calendar for listing MICs `XNGS`, `XNGM`, `XNCM`, `XNYS`, and `XASE`. Core hours are
09:30–16:00 America/New_York, with 13:00 closes on 2026-11-27 and 2026-12-24. Ten
explicit official closures include 2026-07-03 as a full-day closure; the generated
schedule contains 251 sessions.

`ZoneInfo("America/New_York")` supplies DST-aware UTC conversion. A caller-provided
completion grace separates scheduled market close from daily-bar eligibility. Operational
provider requests resolve the latest eligible session through a common factory, while
explicit historical cutoffs remain supported. Twelve Data and Alpaca observations pass a
shared calendar validator before persistence, with no automatic provider fallback.

Coverage is deliberately limited to 2026 and fails closed outside that range. Unscheduled
emergency closures, scheduler execution, Recommendation/ranking, and orders remain outside
this slice. See [market calendar policy](docs/market-calendar.md) and
[ADR 0008](docs/adr/0008-us-equity-core-calendar.md).

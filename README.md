# auto_trading_v2

`auto_trading_v2`는 기존 `auto_trading`과 코드, 데이터베이스, 런타임 상태를 공유하지 않는
독립 프로젝트입니다. 첫 번째 변경 범위는 애플리케이션 기능이 아닌 도메인 기반과 경계의
정의입니다.

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
mypy src
```

## 설계 원칙

- 의존 방향은 Adapter/CLI → Application → Domain입니다.
- Domain은 프레임워크, 환경 변수, DB, 네트워크에 의존하지 않습니다.
- `Money`와 `Price`는 `float`의 암시적 입력을 허용하지 않습니다.
- 소수점 반올림 기본 정책은 `ROUND_HALF_EVEN`이지만, PR 1에서는 통화별 자릿수를 가정해
  일괄 양자화하지 않습니다.
- 모든 타임스탬프는 UTC로 정규화하고 RFC 3339의 `Z` 형식으로 직렬화합니다.
- 기본 ID 팩토리는 UUID4를 사용합니다. 향후 UUIDv7 전환은 팩토리 구현 교체로 처리합니다.

## 현재 범위

현재 포함되는 것은 도메인 원시 타입, 변동성 돌파의 순수 계산, Clock 포트와 구현,
일반 재시도 도우미, 민감정보 마스킹입니다. DB, 브로커, 주문·체결·포지션, 외부 API,
스케줄러와 실제 매매는 포함하지 않습니다. 다음 PR에서 애플리케이션 유스케이스와 영속성
경계를 별도로 설계합니다.

자세한 경계는 [아키텍처 경계 문서](docs/architecture-boundaries.md)를 참고하세요.

# auto_trading_v2

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

`auto_trading_v2`는 기존 `auto_trading`과 코드, 데이터베이스, 런타임 상태를 공유하지 않는
독립 프로젝트입니다. 현재 변경 범위는 도메인 기반과 Microsoft SQL Server용 canonical
스키마입니다. 애플리케이션 유스케이스와 실제 주문 실행은 아직 포함하지 않습니다.

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
일반 재시도 도우미, 민감정보 마스킹, SQLAlchemy Core metadata와 Alembic 초기
마이그레이션입니다. 테이블은 시장 관측부터 paper 주문·체결·포지션·자산 곡선·감사 이벤트까지
사실과 상태를 저장할 구조만 정의합니다. Repository, Unit of Work, 브로커, 외부 API,
스케줄러와 실제 매매는 포함하지 않습니다.

자세한 경계는 [아키텍처 경계 문서](docs/architecture-boundaries.md)를 참고하세요.

# V2 로컬 설정 경계

## 목적과 보안 원칙

V2는 개발자가 로컬 설정을 관리할 때 repository root의 `.env`를 사용한다. 이 파일은
Git에 포함하지 않으며 백업본이나 복사본도 repository 안에 만들지 않는다. 운영 및 CI에서는
같은 canonical key를 process environment 또는 별도 secret store로 제공할 수 있다.

`.env`는 application configuration boundary가 명시적으로 `load_settings()`를 호출할 때만
읽힌다. package import, Domain import, migration module import만으로는 파일을 읽거나 DB 또는
network에 연결하지 않는다. loader는 상위 디렉터리를 검색하지 않으며 V1 설정을 import하거나
V1 key alias를 지원하지 않는다. 심볼릭 링크인 `.env`도 안전하지 않은 source로 거부한다.

## 시작 방법

실제 `.env`가 아직 없다면 다음 명령으로 예시 파일을 복사한 후 빈 값을 로컬 환경에 맞게
직접 채운다. 기존 `.env`가 있다면 덮어쓰지 않는다.

```powershell
Copy-Item .env.example .env
python scripts/check_config.py
```

진단 명령은 DB, KIS, Telegram에 연결하지 않는다. URL이나 credential 값, unknown key 이름도
출력하지 않고 `configured`, `missing`, source 종류와 개수만 표시한다.

## Source precedence

각 key는 다음 순서로 한 번만 선택한다.

1. 테스트나 CLI가 명시적으로 전달한 override mapping
2. repository root `.env`
3. 현재 process environment
4. 코드에 정의된 안전한 기본값

`.env`에 key가 존재하면 같은 이름의 Windows User/process environment보다 `.env` 값이
우선한다. 빈 값도 명시된 값이므로 process 값으로 대체하지 않고 validation에서 `missing`으로
진단한다. `load_settings(env_file=..., environ=...)`를 사용하면 테스트가 실제 사용자 `.env`에
접근하지 않고 임시 파일과 mapping만으로 설정을 구성할 수 있다.

## Canonical V2 key

Application:

- `AUTO_TRADING_V2_ENVIRONMENT`: `development`, `test`, `paper`; 기본 `development`
- `AUTO_TRADING_V2_LOG_LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`; 기본 `INFO`

MSSQL:

- `AUTO_TRADING_V2_DATABASE_URL`: 필수, `mssql+pyodbc`, database `auto_trading_v2`
- `AUTO_TRADING_V2_MSSQL_ADMIN_URL`: 선택, database `master`
- `AUTO_TRADING_V2_TEST_ADMIN_URL`: 선택, database `master`

설정 검증은 URL을 parse할 뿐 engine을 생성하거나 SQL Server에 연결하지 않는다. URL은
`SecretValue`로 보관되어 `repr()`과 `str()`에서 항상 redacted된다.

KIS paper:

- `AUTO_TRADING_V2_KIS_ENABLED`: 기본 `false`
- `AUTO_TRADING_V2_KIS_ENVIRONMENT`: 이 단계에서는 `paper`만 허용
- `AUTO_TRADING_V2_KIS_BASE_URL`
- `AUTO_TRADING_V2_KIS_APP_KEY`
- `AUTO_TRADING_V2_KIS_APP_SECRET`
- `AUTO_TRADING_V2_KIS_ACCOUNT_NUMBER`
- `AUTO_TRADING_V2_KIS_ACCOUNT_PRODUCT_CODE`

KIS가 disabled이면 URL과 credential은 필요하지 않고 설정 객체에도 보관하지 않는다. enabled이면
HTTPS base URL과 모든 credential이 필요하다. base URL에는 user info, query, fragment를 허용하지
않는다. `live`와 `real`은 지원하지 않는다. access token key는 정의하지 않으며 향후 runtime token
cache가 관리해야 한다. 이 PR에는 KIS HTTP client, token 발급, broker adapter가 없다.

Telegram:

- `AUTO_TRADING_V2_TELEGRAM_ENABLED`: 기본 `false`
- `AUTO_TRADING_V2_TELEGRAM_BOT_TOKEN`
- `AUTO_TRADING_V2_TELEGRAM_CHAT_ID`

Telegram이 disabled이면 token과 chat ID는 필요하지 않고 보관하지 않는다. enabled일 때는 둘 다
비어 있지 않아야 한다. token 형식이나 실제 유효성을 network로 확인하지 않으며 이 PR에는
Telegram client와 메시지 전송 기능이 없다.

Boolean은 대소문자와 앞뒤 공백을 정규화한 뒤 `true`, `1`, `yes`, `on` 또는 `false`, `0`,
`no`, `off`만 허용한다.

## Typed settings와 secret redaction

`AppSettings`와 하위 설정 객체는 frozen dataclass다. Domain은 설정 객체나 credential을 알지
않는다. 민감 값은 `SecretValue`가 보관하며 실제 adapter가 필요한 시점에만 명시적인
`reveal()`을 호출해야 한다. 이번 범위에는 DB engine 또는 외부 API client 생성이 없으므로
새로운 reveal 호출도 없다.

오류에는 canonical key, missing/invalid 사유, 허용 값만 포함되고 실제 입력값은 포함되지 않는다.
진단 출력과 dataclass representation에도 URL, App Key, App Secret, 계좌번호, Telegram token,
chat ID가 나타나지 않는다.

## 오류 진단

`python scripts/check_config.py`의 exit code는 valid일 때 0, configuration invalid일 때 2다.
unknown key는 실패 원인이 아니며 이름 대신 개수만 출력한다. canonical key가 누락된 경우 해당
canonical 이름과 안전한 사유만 표시한다.

다음 단계에서는 DB Repository와 transaction boundary를 별도 PR에서 구현한다. 그 전까지
Repository, Unit of Work, 주문·체결 상태 전이, position projector, P&L, scheduler는 이 설정
경계에 포함하지 않는다.

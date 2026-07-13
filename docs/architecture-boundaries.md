# 아키텍처 경계

## 독립성

V2는 V1의 소스 모듈, 데이터베이스, 설정 파일 또는 런타임 상태를 import하거나 공유하지
않습니다. V1 기준 커밋 `ef843b0929e9bf7d73de380da0d3e0277c9dc2fc`에서 확인한 순수 동작 중
다음 세 가지 의미만 독립적으로 재구현했습니다.

- `strategy.py`: 변동성 돌파 가격과 돌파 여부
- `retry.py`: 제한 횟수 재시도와 최종 예외 보존
- `trading_event_logger.py`: 중첩 데이터의 민감정보 마스킹

V1 파일이나 패키지를 복사하거나 import하지 않습니다.

## 의존 방향

```text
Adapters / CLI → Application → Domain
```

Domain은 가장 안쪽 계층입니다. 표준 라이브러리 외 프레임워크, DB, HTTP 클라이언트,
환경 변수 접근을 두지 않습니다. 외부 시간은 `Clock` 포트를 통해서만 전달합니다.

MSSQL 관련 SQLAlchemy Core metadata, 연결 설정과 안전한 관리 도구는
`adapters.persistence`에만 둡니다. 모듈 import만으로 연결, 마이그레이션 또는
`metadata.create_all()`이 실행되지 않습니다. Alembic만 `trading` 테이블을 생성하며,
Domain은 SQLAlchemy, Alembic, pyodbc와 환경 변수에 계속 의존하지 않습니다.

## 값 정책

- 금액과 가격: 유한한 `Decimal`; `float` 입력 거부
- 반올림: 기본 정책은 `ROUND_HALF_EVEN`; 통화별 양자화는 아직 적용하지 않음
- 통화: 대문자 영문 3자리 값 객체이며 특정 통화에 고정하지 않음
- 시간: timezone-aware 값만 허용하고 UTC로 정규화
- 식별자: UUID 기반 불변 타입별 ID; 서로 다른 ID 타입은 같지 않음
- ID 생성: 교체 가능한 팩토리 뒤에 두며 기본 구현은 UUID4

## PR 2 범위와 비목표

이 PR은 V2 전용 MSSQL 데이터베이스의 canonical table 11개, 초기 Alembic migration,
DB 생성·검사 도구와 스키마 검증 테스트만 추가합니다. 다음 항목은 의도적으로 포함하지
않습니다.

- Repository, Unit of Work, transaction boundary
- 브로커 포트나 KIS 연동
- 후보 선정, 필터, 의사결정, 주문·체결·포지션 projector 업무 로직
- 텔레그램, 알림 outbox, 스케줄러, 분석 CLI, CSV, UI
- 실매매와 모든 외부 네트워크 호출

## 다음 단계와 제한사항

다음 PR에서는 현재 도메인 타입과 canonical schema를 기반으로 Repository 인터페이스,
SQLAlchemy 구현 및 명시적 transaction boundary를 설계합니다. PR 2에는 거래 세션 달력,
DST/휴장일 처리, 통화별 소수 자릿수, UUIDv7,
실시간 데이터 또는 멱등 주문 정책이 없습니다. 재시도는 기술적 실패 처리일 뿐이며,
주문 멱등성과 중복 주문 방지는 별도의 애플리케이션 정책으로 다뤄야 합니다.

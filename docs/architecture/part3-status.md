# Part 3 착수 상태

이 문서는 로컬 Codex와 Codex cloud가 같은 기준으로 Part 3 작업을 이어가기 위한 현재 상태 기록이다.

2026-09-03 기준으로 `feature/part3`에서 Part 3 공통 기반, SQLAlchemy Repository, Unit of Work와 상점 구매 서비스를 점검했다.

## 완료된 기반

- 16개 업무 테이블 마이그레이션
- 모든 PK의 `GENERATED ALWAYS AS IDENTITY`
- 모든 업무 테이블의 UUID `public_id`
- `uq_users_email_lower` 인덱스
- `request_id` 전역 UNIQUE
- `user_cats`의 고양이/아이템 XOR 및 수량 제약
- 5개 교차 정합성 트리거
- 응답 스키마에서 내부 INTEGER `id` 제외
- 기본 `/health` 테스트와 Ruff 검사 통과
- Alembic 및 psycopg 3 의존성
- PostgreSQL 16 서비스 기반 CI
- 단일 SQLAlchemy `Base`와 16개 모델 메타데이터 등록 검사
- 신규 DB와 기존 DB 모두에 적용되는 `pgcrypto` 활성화 마이그레이션
- Alembic 신규 설치, 전체 롤백, 재설치 CI 순환
- 5개 교차 정합성 트리거의 허용·거부 PostgreSQL 통합 테스트

## Part 3 전에 해결할 공통 기반 문제

### 1. PostgreSQL 마이그레이션 실행 환경 — 구현 완료, CI 확인 필요

- `pyproject.toml`에 `alembic`과 `psycopg[binary]`가 등록되어 있다.
- 최초 마이그레이션과 후속 멱등 마이그레이션이 `pgcrypto`를 활성화한다.
- CI는 PostgreSQL 16에서 upgrade → downgrade base → upgrade 순환을 실행한다.
- 로컬 PostgreSQL 접속 정보는 저장소에 커밋하지 않고 개발자별 `.env`/`alembic.ini`로 관리한다.

### 2. SQLAlchemy Base와 Alembic 메타데이터 — 완료

- 실제 선언 Base는 `app.models.base.Base` 하나만 사용한다.
- `app.db.base.Base`는 기존 import 호환성을 위한 재노출이며 동일 객체다.
- Alembic은 `app.models` 패키지를 통해 16개 모델을 모두 등록한다.
- 단위 테스트가 Base 동일성과 정확히 16개 테이블 등록을 검증한다.

### 3. 공개 UUID 응답 직렬화 — 완료

- `UserCatRead`는 `to_user_cat_read()`로 `cat_public_id`와 `item_public_id`를 명시적으로 변환한다.
- `PlacedObjectRead`는 `to_placed_object_read()`로 `item_public_id`를 명시적으로 변환한다.
- `CatMemoryRead`는 `to_cat_memory_read()`로 `user_cat_public_id`를 명시적으로 변환한다.
- 변환 함수는 내부 INTEGER PK/FK를 응답 DTO에 복사하지 않는다.
- `tests/unit/schemas/test_public_id_serialization.py`가 고양이·아이템·배치 객체·고양이 기억 변환을 검증한다.

### 4. 멱등성 claim과 비용 컬럼 — 완료

통합 계약처럼 실행을 먼저 `claim()`한 뒤 비용을 계산할 수 있도록 `GachaExecution.balance_cost`에 ORM 기본값과 DB 서버 기본값 `0`을 적용했다. `NOT NULL`과 `balance_cost >= 0` 제약은 그대로 유지한다.

- `app/models/gacha_execution.py`에 `default=0`, `server_default=text("0")`을 추가했다.
- `be8999b8f41e_add_balance_cost_default.py` 마이그레이션으로 기존 PostgreSQL 스키마에도 서버 기본값을 추가한다.
- `tests/unit/models/test_gacha_execution.py`가 ORM 및 서버 기본값 메타데이터를 검증한다.
- `tests/integration/db/test_migrations.py`가 비용을 생략한 실행 행의 값이 `0`인지 검증한다.
- 새 마이그레이션은 `6e7f8a9b0c1d`를 잇는 유일한 Alembic head다.
- 통합 계약에 `claim()` 시 초기 비용 `0`과 `complete()` 시 실제 비용 갱신 규칙을 명시했다.

모델 단위 테스트와 정적 검사는 통과했다. Docker의 PostgreSQL 16에 전체 마이그레이션을 적용한 뒤 `tests/integration/db/test_migrations.py`의 6개 테스트도 모두 통과했다. `complete()` 구현은 이후 멱등성 실행 엔진 단계에서 이 계약을 따른다.

### 5. 요청 해시 정규화 — 완료

- `app/core/request_hash.py`의 `build_request_hash()`를 구매와 가챠가 함께 사용하는 단일 해시 함수로 구현했다.
- JSON 키 정렬, 공백 제거, UTF-8, UUID 표준 문자열 변환과 SHA-256 규칙을 적용한다.
- `operation_type`은 포함하고 `request_id`와 가격·잔액·마일리지 등 서버 결정값은 제외한다.
- `tests/unit/core/test_request_hash.py`가 키 순서, 제외 필드, 업무 종류와 요청 내용 변경을 검증한다.

### 6. Repository 계약과 Fake — 완료

- `app/core/repository_contracts.py`에 Execution, User, Item, Cat, Asset, PlacedObject, CatMemory Repository Protocol을 정의했다.
- `ClaimStatus`와 `ExecutionClaim`으로 멱등 요청 선점 결과를 표현한다.
- 잠금 메서드는 `for_update` 이름을 사용하고 모든 Repository에서 `commit()`과 `rollback()`을 제외했다.
- `tests/fakes/repositories.py`에 동일 계약을 따르는 7개 메모리 Fake를 구현했다.
- Fake 실행 저장소는 신규 선점, 완료 결과 재사용, 사용자·해시 충돌을 재현한다.
- 나머지 Fake는 공개 UUID 조회, 자산 지급·수량 합산, 배치 수 집계와 고양이 기억 누적을 지원한다.

### 7. SQLAlchemy Repository — 완료

- `app/db/repositories.py`에 User, Item, Cat, Asset, PlacedObject, CatMemory, Execution Repository 구현체를 추가했다.
- 공개 UUID 조회와 저장 동작을 분리하고, Repository 내부에서는 `commit()`하지 않는다.
- 사용자와 아이템 자산 변경 조회는 `SELECT ... FOR UPDATE`를 사용한다.
- 배치 개수 조회는 PostgreSQL에서 허용되지 않는 `COUNT(*) FOR UPDATE` 대신 대상 행을 잠근 뒤 Python에서 개수를 센다.
- 실행 선점은 PostgreSQL `INSERT ... ON CONFLICT DO NOTHING RETURNING`을 사용하고, 기존 실행은 `FOR UPDATE`로 조회한다.
- 같은 실행의 완료·진행 상태와 다른 사용자 또는 요청 해시 충돌을 `ClaimStatus`로 구분한다.
- `tests/unit/db/test_sqlalchemy_repositories.py`의 20개 테스트가 조회, 저장, 잠금, 선점과 완료 동작을 검증한다.

### 8. Unit of Work — 완료

- `app/core/unit_of_work.py`에 서비스가 의존할 Unit of Work Protocol을 정의했다.
- `app/db/unit_of_work.py`에 SQLAlchemy 세션과 일곱 Repository를 묶는 구현체를 추가했다.
- 모든 Repository가 하나의 세션을 공유해 잔액, 자산과 실행 결과를 같은 트랜잭션에서 변경할 수 있다.
- `commit()`과 `rollback()`은 공유 세션에 위임하며 Repository는 트랜잭션을 종료하지 않는다.
- 컨텍스트 종료 시 rollback과 close를 실행하고, 서비스에서 발생한 예외는 숨기지 않는다.
- `tests/unit/core/test_unit_of_work_contract.py`와 `tests/unit/db/test_unit_of_work.py`가 계약, 세션 공유, commit, rollback과 예외 경로를 검증한다.

### 9. 상점 아이템 구매 서비스 — 완료

- `app/modules/shop/service.py`가 공개 사용자·아이템 UUID와 구매 수량으로 멱등 구매를 수행한다.
- 공통 요청 해시로 실행을 claim하고 완료된 동일 요청은 저장된 결과를 그대로 반환한다.
- 같은 요청 ID의 사용자 또는 내용이 다르면 `IdempotencyConflictError`로 거부한다.
- DB의 아이템 가격으로 총비용을 계산하고 잠근 사용자 잔액에서 차감한다.
- 신규 아이템 자산을 생성하거나 기존 `UserCat` 자산 수량을 합산한다.
- 잔액 부족, 0 이하 수량과 존재하지 않는 리소스는 변경과 commit 전에 거부한다.
- 실행 완료, 잔액과 자산 변경을 하나의 UoW에서 처리하고 서비스가 한 번만 commit한다.
- `tests/unit/modules/shop/test_purchase_service.py`의 10개 테스트가 정상·재시도·충돌·오류·재구매 경로를 검증한다.

### 10. 계약 테스트

다음 검증은 추가됐다.

- Alembic 신규 설치, 전체 롤백 및 재설치
- 5개 트리거의 대표 허용/거부 사례
- 공개 UUID DTO 직렬화
- `balance_cost`의 ORM/DB 기본값 메타데이터
- PostgreSQL 16에서 비용을 생략한 실행 행의 DB 기본값 `0`
- 요청 해시 정규화 및 충돌 구분
- Repository 메서드 경계와 트랜잭션 책임 분리
- Fake Repository의 선점·충돌·자산·배치·기억 동작
- SQLAlchemy Repository의 공개 UUID 조회, 저장, 행 잠금과 멱등 실행 선점
- Unit of Work의 Repository 세션 공유, commit, rollback, 세션 종료와 예외 전파
- 상점 구매의 정상 처리, 완료 결과 재사용, 멱등 충돌, 잔액 부족, 입력 검증과 자산 합산

다음 Part 3 검증은 기능 구현과 함께 추가해야 한다.

- 동일 요청 재시도와 해시 충돌
- 다른 사용자의 동일 `request_id` 사용
- 동시 가구 배치 및 자산 행 잠금
- 잔액, 마일리지, 자산, 실행 결과의 원자적 롤백

## 권장 작업 순서

1. 고양이 가챠와 중복 마일리지 서비스
2. 하우징 배치와 표면 아이템 적용
3. 고양이 기억 API
4. FastAPI 라우터와 예외 매핑
5. PostgreSQL 동시성 통합 테스트

## 웹 작업 시작 프롬프트

Codex cloud에서 새 작업을 시작할 때 다음처럼 요청한다.

> 이 저장소의 `AGENTS.md`, `docs/architecture/part3-integration-contract.md`, `docs/architecture/part3-status.md`를 먼저 읽어라. Part 3 착수 전 공통 기반 문제 중 하나만 선택해 현재 코드와 계약을 대조하고, 테스트를 먼저 추가한 뒤 수정하라. 내부 INTEGER id를 API에 노출하지 말고 Repository에서 commit하지 마라. 완료 후 실행한 검사와 남은 위험을 보고하라.

한 대화에서 전체 Part 3를 한꺼번에 요청하지 말고 권장 작업 순서의 한 항목씩 진행한다.

# Part 3 착수 상태

이 문서는 로컬 Codex와 Codex cloud가 같은 기준으로 Part 3 작업을 이어가기 위한 현재 상태 기록이다.

2026-09-03 기준으로 `feature/part3`에서 Part 3 공통 기반, SQLAlchemy Repository, Unit of Work, 상점 구매, 고양이 가챠와 하우징 배치 서비스를 점검했다.

## 완료된 기반

- 16개 업무 테이블 마이그레이션
- 모든 PK의 `GENERATED ALWAYS AS IDENTITY`
- 모든 업무 테이블의 UUID `public_id`
- `uq_users_email_lower` 인덱스
- `request_id` 전역 UNIQUE
- `assets`의 고양이/아이템 XOR 및 수량 제약
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

- `AssetRead`는 `to_asset_read()`로 `cat_public_id`와 `item_public_id`를 명시적으로 변환한다.
- `PlacedObjectRead`는 `to_placed_object_read()`로 `item_public_id`를 명시적으로 변환한다.
- `CatMemoryRead`는 `to_cat_memory_read()`로 `cat_asset_public_id`를 명시적으로 변환한다.
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
- 신규 아이템 자산을 생성하거나 기존 `Asset` 수량을 합산한다.
- 잔액 부족, 0 이하 수량과 존재하지 않는 리소스는 변경과 commit 전에 거부한다.
- 실행 완료, 잔액과 자산 변경을 하나의 UoW에서 처리하고 서비스가 한 번만 commit한다.
- `tests/unit/modules/shop/test_purchase_service.py`의 10개 테스트가 정상·재시도·충돌·오류·재구매 경로를 검증한다.

### 10. 고양이 가챠 서비스 — 단위 구현 완료

- `app/schemas/gacha.py`에 양수 뽑기 횟수와 공개 UUID만 사용하는 요청·응답 스키마를 추가했다.
- `GachaPolicy`가 비용, 추첨 결과와 중복 마일리지를 주입하므로 미확정 정책값을 서비스에 하드코딩하지 않는다.
- 공통 요청 해시로 실행을 선점하고 완료된 동일 요청은 저장된 결과를 그대로 반환한다.
- 같은 요청 ID의 사용자 또는 뽑기 횟수가 다르면 `IdempotencyConflictError`로 거부한다.
- 사용자 행을 잠근 뒤 정책 비용과 잔액을 검증하고, 잔액이 충분할 때만 추첨한다.
- 신규 고양이는 `Asset`을 수량 1로 생성한다.
- 중복 고양이는 자산 행이나 수량을 늘리지 않고 정책의 보상만 사용자 mileage에 더한다.
- 비용·보상 개수·중복 마일리지 같은 정책 결과를 변경 전에 검증한다.
- 잔액, mileage, 자산과 실행 결과를 하나의 UoW에서 변경하고 서비스가 한 번만 commit한다.
- 스키마 테스트 4개와 서비스 테스트 14개를 포함한 전체 테스트가 `77 passed, 11 skipped, 1 warning`으로 통과했다.
- 중간 실패의 실제 rollback과 동시 가챠 요청은 최종 PostgreSQL 통합 검증에 남아 있다.

### 11. 하우징 가구 배치 서비스 — 단위 구현 완료

- `PositionData`가 3축 위치 좌표 `x`, `y`, `z`를 필수 유한 숫자로 검증하고 알 수 없는 필드를 거부한다.
- 이전 `rotation` 필드는 거부하며 기존 JSONB 데이터는 Alembic 마이그레이션으로 `z`에 옮긴다.
- 실제 방 크기에 따른 `x`, `y`, `z` 범위는 아직 확정되지 않아 임의의 최솟값·최댓값을 하드코딩하지 않았다.
- `place_furniture()`는 `FURNITURE` 카테고리와 사용자 소유 아이템 자산을 확인한다.
- 아이템 자산 행을 먼저 잠그고 현재 배치 행도 잠금 조회한 뒤 보유 수량과 비교한다.
- 보유 수량 이상이면 `PlacementLimitExceededError`로 새 배치를 거부한다.
- 수정과 해제는 배치 공개 UUID로 행을 잠그며 다른 사용자의 객체는 존재하지 않는 것처럼 처리한다.
- 해제는 `PlacedObject`만 삭제하고 기존 `Asset.quantity`는 변경하지 않는다.
- Repository 계약, Fake와 SQLAlchemy 구현에 내부 아이템 조회, 배치 공개 UUID 잠금 조회와 삭제를 추가했다.
- 전체 테스트는 `95 passed, 11 skipped, 1 warning`, Ruff와 `git diff --check`는 통과했다.
- 실제 HTTP 404 변환, 좌표 정책 범위와 PostgreSQL 동시 배치 검증은 후속 단계에 남아 있다.

### 12. 통합 보유 자산 명칭 정리 — 완료

- 고양이와 아이템을 함께 보관하는 테이블 이름을 `user_cats`에서 `assets`로 변경했다.
- Python ORM과 응답 DTO는 `UserCat`/`UserCatRead` 대신 `Asset`/`AssetRead`를 사용한다.
- 고양이 기억 FK는 범용 자산 중 고양이 자산만 참조한다는 뜻이 드러나도록 `user_cat_id`에서 `cat_asset_id`로 변경했다.
- 고양이 기억의 공개 응답 필드도 `user_cat_public_id`에서 `cat_asset_public_id`로 변경했다.
- Alembic 마이그레이션은 기존 데이터와 FK를 보존한 채 테이블 및 관련 제약·트리거 이름을 변경한다.
- 실제 PostgreSQL에서 upgrade와 관련 마이그레이션·트리거 통합 테스트 12개가 통과했다.

### 13. 하우징 좌표 계약 변경 — 완료

- `position_data`의 필수 좌표를 `x`, `y`, `rotation`에서 `x`, `y`, `z`로 변경했다.
- Pydantic 입력 검증과 배치 생성·수정·직렬화·Repository 테스트 데이터를 모두 새 계약으로 통일했다.
- `rotation` 키가 남은 기존 PostgreSQL JSONB 데이터는 값을 보존해 `z` 키로 변경하는 Alembic 마이그레이션을 추가했다.
- downgrade 시에는 `z` 값을 다시 `rotation`으로 복구한다.
- `docs/architecture/current-erd.md`와 팀 Notion ERD를 최신 16개 테이블 기준으로 갱신했다.

### 14. 고양이 자산 기억 참조 명칭 정리 — 완료

- `CAT_MEMORIES.user_cat_id`를 `cat_asset_id`로 변경하되 참조 대상은 계속 `ASSETS.id`를 사용한다.
- 공개 DTO 필드는 `cat_asset_public_id`, Repository 조회는 `list_by_cat_asset_id()`로 통일했다.
- Alembic 마이그레이션이 기존 FK 값은 그대로 보존하면서 컬럼과 FK 제약 이름을 변경한다.
- 자산 삭제 방지와 고양이 자산 검증 트리거 함수도 새 컬럼명을 사용하도록 갱신한다.

### 15. 계약 테스트

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
- 가챠의 신규·중복 획득, 완료 결과 재사용, 멱등 충돌, 잔액·입력·정책 검증과 다중 추첨
- 하우징의 좌표 입력, 카테고리·소유권·수량 제한과 배치 생성·수정·해제

다음 Part 3 검증은 기능 구현과 함께 추가해야 한다.

- 동일 요청 동시 재시도와 PostgreSQL 행 잠금
- PostgreSQL에서 다른 사용자의 동일 `request_id` 사용
- 동시 가구 배치 및 자산 행 잠금
- 잔액, 마일리지, 자산, 실행 결과의 원자적 롤백

## 권장 작업 순서

1. 고양이 기억 API
2. 벽지·바닥 적용 서비스
3. FastAPI 라우터와 예외 매핑
4. PostgreSQL 동시성 및 rollback 통합 테스트

## 프런트엔드 학습 연결 기반

- 로컬 브라우저 개발용 세션 발급과 `X-User-Public-ID` 사용자 조회를 추가했다.
- 운영 환경에서는 개발 세션을 404로 숨기고 임시 UUID 헤더를 인증으로 사용하지 않는다.
- `CORS_ORIGINS`로 PWA 개발 origin을 명시적으로 허용한다.
- 추천 과제 응답에 `concept_name`을 추가해 클라이언트가 내부 개념 ID 없이 필터를 구성할 수 있다.

## 웹 작업 시작 프롬프트

Codex cloud에서 새 작업을 시작할 때 다음처럼 요청한다.

> 이 저장소의 `AGENTS.md`, `docs/architecture/part3-integration-contract.md`, `docs/architecture/part3-status.md`를 먼저 읽어라. Part 3 착수 전 공통 기반 문제 중 하나만 선택해 현재 코드와 계약을 대조하고, 테스트를 먼저 추가한 뒤 수정하라. 내부 INTEGER id를 API에 노출하지 말고 Repository에서 commit하지 마라. 완료 후 실행한 검사와 남은 위험을 보고하라.

한 대화에서 전체 Part 3를 한꺼번에 요청하지 말고 권장 작업 순서의 한 항목씩 진행한다.

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
- 중간 실패의 실제 rollback과 동시 가챠 요청은 최종 PostgreSQL 통합 검증에서 통과했다.

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

### 15. 벽지·바닥 적용 서비스 — 단위 구현 완료

- `apply_surface_item()`은 공개 사용자·아이템 UUID로 대상을 조회한다.
- `WALLPAPER`와 `FLOOR` 카테고리만 허용하고 다른 카테고리는 `InvalidItemCategoryError`로 거부한다.
- 사용자가 실제로 보유한 아이템 자산 행을 잠금 조회한 뒤 사용자 행도 잠그고 선택 FK를 변경한다.
- 벽지를 적용할 때 기존 바닥 선택을 유지하고, 바닥을 적용할 때 기존 벽지 선택을 유지한다.
- 존재하지 않는 사용자·아이템과 소유하지 않은 표면 아이템은 `ResourceNotFoundError`로 거부한다.
- 응답은 `user_public_id`, `item_public_id`, `category`만 반환하며 내부 정수 ID를 노출하지 않는다.
- 성공 경로에서 서비스가 한 번만 commit하고 오류 경로에서는 commit하지 않는다.
- 표면 적용 단위 테스트 6개를 포함한 전체 테스트는 `126 passed, 13 skipped, 1 warning`으로 통과했다.
- 실제 HTTP 연결과 PostgreSQL 트리거 검증은 후속 API·통합 테스트 단계에 남아 있다.

### 16. 계약 테스트

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
- 벽지·바닥 적용의 정상 분기, 카테고리·소유권 및 리소스 오류 처리
- 고양이 페르소나와 기억 목록의 공개 UUID DTO 직렬화
- 보유 고양이별 기억 조회·누적·선택 삭제·전체 삭제, 소유권 차단과 시간순 정렬

### 17. 고양이 페르소나와 대화 기억 — FastAPI 연결 완료

- 고양이의 고정 성격은 `CATS.persona`에서 읽으며 기억 삭제의 대상이 아니다.
- `get_cat_conversation_context()`는 보유 고양이 자산 UUID로 이름, 페르소나와 누적 기억을 반환한다.
- 기억 목록은 `created_at`, `id` 오름차순으로 정렬하고 내부 정수 ID를 응답에 노출하지 않는다.
- `add_cat_memory()`는 기존 기억을 덮어쓰지 않고 새 `CAT_MEMORIES` 행을 추가하며 공백 요약을 거부한다.
- `delete_cat_memory()`는 선택한 기억 행만 잠금 조회 후 삭제한다.
- `delete_all_cat_memories()`는 지정한 고양이 자산의 기억 행만 일괄 삭제한다.
- 모든 경로에서 인증 사용자의 소유권과 고양이 자산 여부를 검사하며, 다른 사용자의 자산은 찾을 수 없는 것으로 처리한다.
- Repository는 조회·추가·삭제만 수행하고 서비스가 Unit of Work를 통해 commit한다.
- `GET /api/v1/cats/{cat_asset_public_id}/conversation-context`는 고양이 이름, 고정 페르소나와 누적 기억을 반환한다.
- `POST /api/v1/cats/{cat_asset_public_id}/memories`는 새 기억을 누적하고 `201 Created`를 반환한다.
- 선택 삭제와 전체 삭제는 각각 기억 공개 UUID 포함 경로와 고양이 자산의 memories 경로에서 빈 `204 No Content`를 반환한다.
- 모든 경로는 `CurrentUser`와 공개 UUID만 사용하며 소유권·리소스 오류는 `404`, 공백 요약과 요청 검증 오류는 `422`로 변환한다.
- `CatMemoryCreate`는 알 수 없는 필드를 거부하고 OpenAPI 응답 스키마는 내부 정수 ID를 포함하지 않는다.
- 요청 헤더, 경로 변수, JSON 본문, 성공 응답과 오류 형식의 예시는 `part3-integration-contract.md`의 고양이 페르소나·기억 FastAPI 계약에 기록했다.
- 브라우저 클라이언트가 기억 삭제를 호출할 수 있도록 CORS 허용 메서드에 `DELETE`를 추가했다.
- 관련 API·서비스·스키마·CORS 테스트는 `44 passed`, 전체 회귀 검사는 `171 passed, 13 skipped, 1 warning`이다.
- 전체 Ruff와 `git diff --check`도 통과했다. 남은 경고는 기존 TestClient/httpx deprecation 경고다.

### 18. 나머지 Part 3 API — FastAPI 연결 완료

- `POST /api/v1/shop/purchases`를 구매 서비스에 연결하고 성공 `201`, 리소스 `404`, 멱등 충돌·잔액 부족 `409`, 수량 검증 `422`를 적용했다.
- `PUT /api/v1/housing/surfaces/{item_public_id}`를 벽지·바닥 적용 서비스에 연결하고 성공 `200`, 리소스 `404`, 카테고리 검증 `422`를 적용했다.
- `POST /api/v1/housing/placed-objects`, `PATCH`·`DELETE /api/v1/housing/placed-objects/{placed_object_public_id}`를 배치·수정·해제 서비스에 연결했다. 생성은 `201`, 수정은 `200`, 삭제는 빈 `204`이며 리소스 `404`, 수량 초과 `409`, 입력·카테고리 오류 `422`를 사용한다.
- `POST /api/v1/gacha/draws`를 가챠 서비스에 연결하고 리소스 `404`, 멱등 충돌·잔액 부족 `409`, 수량 검증 `422`를 적용했다.
- 모든 새 API는 `CurrentUser`, 공개 UUID와 Unit of Work를 사용하고 응답 모델에 내부 정수 ID를 선언하지 않는다.
- 구매·가챠 요청과 가구 좌표 요청은 알 수 없는 필드를 거부한다.
- 브라우저 호출을 위해 CORS 허용 메서드에 `PUT`, `PATCH`, `DELETE`를 포함했다.
- 가챠 비용·확률·중복 마일리지는 아직 확정되지 않았다. 따라서 기본 `get_gacha_policy()`는 `503 Service Unavailable`을 반환하며, 확정 정책을 주입한 환경과 테스트에서만 추첨을 실행한다.
- 가챠 요청은 프런트의 별도 `1회 뽑기`, `10+1회 뽑기` 버튼에 맞춰 `draw_count`를 `1` 또는 `11`로 제한한다.
- `draw_count=11`은 10회 비용만 계산하고 `bonus_draw_count=1`, 결과 11개를 반환한다. `draw_count=1`은 보너스 없이 결과 한 개다.
- 중복된 `test_router.py` 모듈명 때문에 전체 Pytest 수집 충돌이 발생해 기능별 테스트 파일을 `test_cats_router.py`, `test_shop_router.py`, `test_housing_router.py`, `test_gacha_router.py`로 구분했다.
- `draw_count=1/11` 계약과 최신 `origin/main`을 포함한 최종 전체 검증 결과는 Ruff 통과, `277 passed, 5 skipped, 1 warning`이다. 5개 skip은 전체 검사 당시 별도 SQL grader PostgreSQL이 실행 중이지 않아 생겼으며, 같은 테스트를 전용 환경에서 별도로 모두 통과시켰다. 경고는 기존 TestClient/httpx deprecation이다.
- 인증 보조 API를 포함한 Frontend ↔ Backend 전체 요약표, 요청·응답 필드와 오류 상태는 `part3-integration-contract.md`에 기록했다.

### 19. 고양이 도감 API — 완료

- `GET /api/v1/cats/collection`이 전체 고양이 마스터와 인증 사용자의 보유 고양이 자산을 조합해 반환한다.
- 응답은 `total_count`, `owned_count`, `cats`를 포함하고 각 항목은 `cat_public_id`, nullable `cat_asset_public_id`, `name`, `persona`, `rarity`, `is_owned`만 노출한다.
- 보유한 고양이에만 `cat_asset_public_id`를 제공해 프런트엔드가 대화 컨텍스트 API로 연결할 수 있다.
- `CatRepository.list_all()`은 마스터 등록 순서를 보장하고 `AssetRepository.list_cat_assets_by_user_id()`는 인증 사용자의 고양이 자산만 조회한다.
- 도감은 읽기 전용이며 Repository는 조회만 수행하고 서비스는 commit하지 않는다.
- 인증되지 않은 요청은 `401`, 서비스의 사용자 부재는 `404`로 변환한다.
- 페이지네이션, 검색, 희귀도 필터와 이미지 URL은 현재 데이터·프런트 계약에 없어 임의로 추가하지 않았다.
- 도감 Repository·서비스·라우터 대상 검증은 `61 passed, 1 warning`으로 통과했다.

### 20. 최종 PostgreSQL 통합 검증 — 완료

- 빈 PostgreSQL 16 데이터베이스에서 전체 Alembic 마이그레이션의 downgrade와 `upgrade head`를 검증했다.
- 현재 Alembic revision은 `8a91c3d4e5f6 (head)`이다.
- 실제 PostgreSQL에서 구매 중간 실패 rollback, 동일 구매 요청의 동시 재시도, 서로 다른 구매·가챠 요청의 잔액 초과 방지를 검증했다.
- 서로 다른 사용자의 동일 `request_id` 사용이 충돌로 처리되고 두 번째 사용자의 잔액과 자산이 변경되지 않는 것을 검증했다.
- 구매·표면 적용의 공통 사용자 잠금 순서와 동시 가구 배치의 보유 수량 초과 방지를 검증했다.
- 중복 고양이 마일리지 처리 후 실행 결과 저장이 실패하면 마일리지, 자산과 실행 기록이 모두 rollback되는 것을 검증했다.
- 실제 HTTP 요청으로 구매 멱등성, 가챠 정책 미설정 `503`, 가구 배치·수정·해제, 벽지·바닥 적용, 고양이 도감·대화 컨텍스트·기억 추가·선택 삭제·전체 삭제를 검증했다.
- HTTP 응답에는 공개 UUID만 포함되며 내부 정수 ID가 노출되지 않는 것을 검증했다.
- Part 3 PostgreSQL 통합 테스트 결과는 `28 passed, 1 warning`이다.
- 별도 SQL grader PostgreSQL 환경의 SQL sandbox 검증은 `5 passed`이다.
- 최신 `origin/main`을 fast-forward로 반영한 뒤 전체 Ruff 검사가 통과했다.
- 최신 `main` 통합 후 전체 회귀 검사 결과는 `277 passed, 5 skipped, 1 warning`이다. 5개 skip은 전체 검사 당시 별도 SQL grader 데이터베이스가 실행 중이지 않아 생겼으며, 같은 테스트를 전용 환경에서 별도로 모두 통과시켰다.
- 남은 경고는 기존 FastAPI TestClient와 httpx 호환성 deprecation 경고다.

## 남은 정책 작업

1. 가챠 비용·확률·중복 마일리지 정책 확정 및 운영 `GachaPolicy` 주입
2. 생성형 AI 공급자·모델·프롬프트·요약·실패 처리·비용 정책 확정과 연동
3. 일일 보상액, 배틀 정답 점수와 Part 2 일반 학습 보상·직접 문제 선택의 MVP 포함 여부 확정

## 프런트엔드 학습 연결 기반

- 로컬 브라우저 개발용 세션 발급과 `X-User-Public-ID` 사용자 조회를 추가했다.
- 운영 환경에서는 개발 세션을 404로 숨기고 임시 UUID 헤더를 인증으로 사용하지 않는다.
- `CORS_ORIGINS`로 PWA 개발 origin을 명시적으로 허용한다.
- 추천 과제 응답에 `concept_name`을 추가해 클라이언트가 내부 개념 ID 없이 필터를 구성할 수 있다.

## 웹 작업 시작 프롬프트

Codex cloud에서 새 작업을 시작할 때 다음처럼 요청한다.

> 이 저장소의 `AGENTS.md`, `docs/architecture/part3-integration-contract.md`, `docs/architecture/part3-status.md`를 먼저 읽어라. Part 3 착수 전 공통 기반 문제 중 하나만 선택해 현재 코드와 계약을 대조하고, 테스트를 먼저 추가한 뒤 수정하라. 내부 INTEGER id를 API에 노출하지 말고 Repository에서 commit하지 마라. 완료 후 실행한 검사와 남은 위험을 보고하라.

한 대화에서 전체 Part 3를 한꺼번에 요청하지 말고 권장 작업 순서의 한 항목씩 진행한다.

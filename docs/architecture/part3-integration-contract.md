# Part 3 통합 계약

이 문서는 Part 3의 가챠·구매 멱등성, 상점·하우징, 고양이 및 AI 기억 기능을 DB 구현과 분리해서 개발한 뒤 안전하게 통합하기 위한 계약을 정의한다.

최종 ERD를 기준으로 하며, 이전 프로젝트의 모델과 스키마는 구현 기준으로 사용하지 않는다.

## 1. 공통 명명 규칙

- DB 테이블명과 컬럼명은 최종 ERD의 `snake_case` 이름을 그대로 사용한다.
- SQLAlchemy 모델 클래스는 단수형 `PascalCase`를 사용한다.
- 내부 관계에는 `INTEGER` PK/FK를 사용한다.
- 모든 업무 테이블은 API 공개용 `public_id UUIDv4`를 가진다.
- API 요청과 응답에는 내부 정수 `id`를 노출하지 않는다.
- API에서 자산을 지정할 때는 `cat_public_id`, `item_public_id`, `placed_object_public_id`처럼 공개 식별자임을 이름에 표시한다.

| DB 테이블 | Python 모델 | 책임 |
| --- | --- | --- |
| `users` | `User` | 잔액, 마일리지, 하우스 상태 |
| `items` | `Item` | 아이템 원본 및 가격 |
| `cats` | `Cat` | 고양이 원본, 페르소나 및 희귀도 |
| `assets` | `Asset` | 고양이와 일반 아이템을 함께 저장하는 통합 보유 자산 |
| `gacha_executions` | `GachaExecution` | 가챠와 구매 요청의 멱등성 및 결과 |
| `placed_objects` | `PlacedObject` | 하우징에 배치된 가구 인스턴스 |
| `cat_memories` | `CatMemory` | 보유 고양이별 대화 요약 기록 |

고양이와 아이템을 함께 저장하는 의미를 정확히 표현하도록 DB 테이블은 `assets`, Python 모델은 `Asset`으로 통일한다. 고양이 기억은 범용 자산 중 고양이 자산만 참조한다는 의미가 드러나도록 내부 FK는 `cat_asset_id`, 외부 공개 식별자는 `cat_asset_public_id`를 사용한다.

## 2. Repository 계약

Repository는 조회, 저장, 잠금만 담당한다. 가격 검증, 잔액 차감, 중복 고양이 보상 같은 업무 규칙과 트랜잭션 커밋은 담당하지 않는다.

```python
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class ClaimStatus(StrEnum):
    ACQUIRED = "ACQUIRED"
    COMPLETED = "COMPLETED"
    HASH_CONFLICT = "HASH_CONFLICT"


class ExecutionRepository(Protocol):
    def claim(
        self,
        *,
        user_id: int,
        request_id: UUID,
        request_hash: str,
        request_payload: dict,
        operation_type: str,
    ) -> "ExecutionClaim": ...

    def complete(
        self,
        execution: "GachaExecution",
        *,
        balance_cost: int,
        result_data: dict,
    ) -> None: ...


class UserRepository(Protocol):
    def get_by_public_id(self, public_id: UUID) -> "User | None": ...
    def get_for_update(self, user_id: int) -> "User | None": ...


class ItemRepository(Protocol):
    def get_by_public_id(self, public_id: UUID) -> "Item | None": ...
    def get_by_id(self, item_id: int) -> "Item | None": ...


class CatRepository(Protocol):
    def get_by_public_id(self, public_id: UUID) -> "Cat | None": ...


class AssetRepository(Protocol):
    def get_cat_asset(self, user_id: int, cat_id: int) -> "UserAsset | None": ...

    def get_item_asset_for_update(self, user_id: int, item_id: int) -> "UserAsset | None": ...

    def add_item_quantity(self, user_id: int, item_id: int, quantity: int) -> "UserAsset": ...

    def grant_cat(self, user_id: int, cat_id: int) -> "UserAsset": ...


class PlacedObjectRepository(Protocol):
    def get_by_public_id_for_update(
        self,
        public_id: UUID,
    ) -> "PlacedObject | None": ...

    def count_for_update(self, user_id: int, item_id: int) -> int: ...

    def add(self, user_id: int, item_id: int, position_data: dict) -> "PlacedObject": ...

    def remove(self, placed_object: "PlacedObject") -> None: ...


class CatMemoryRepository(Protocol):
    def get_by_public_id_for_update(self, public_id: UUID) -> "CatMemory | None": ...

    def list_by_cat_asset_id(self, cat_asset_id: int) -> "list[CatMemory]": ...

    def add(self, cat_asset_id: int, context_summary: str) -> "CatMemory": ...

    def remove(self, memory: "CatMemory") -> None: ...

    def remove_all_by_cat_asset_id(self, cat_asset_id: int) -> None: ...
```

`ExecutionRepository.claim()`의 결과는 다음 의미를 가진다.

| 상태 | 의미 |
| --- | --- |
| `ACQUIRED` | 신규 요청이며 현재 트랜잭션이 처리를 진행한다. |
| `COMPLETED` | 기존 요청이 완료됐으며 저장된 `result_data`를 반환한다. |
| `HASH_CONFLICT` | 같은 `request_id`가 다른 사용자 또는 다른 요청 내용으로 사용됐다. |

신규 `ACQUIRED` 실행은 실제 비용을 계산하기 전에 요청을 선점할 수 있도록 `balance_cost=0`으로 생성한다. `balance_cost`는 DB와 ORM 모두 기본값 `0`을 사용하며 `NOT NULL`과 음수 방지 제약을 유지한다. 업무 처리가 성공하면 `complete()`가 실제 `balance_cost`와 `result_data`를 저장하고 상태를 `COMPLETED`로 변경한다.

잠금이 필요한 Repository 메서드는 이름에 `for_update`를 포함한다. 구현체는 PostgreSQL 행 잠금이나 그와 동등한 동시성 제어를 제공해야 한다.

## 3. Unit of Work와 트랜잭션 책임

서비스가 업무 트랜잭션의 시작과 종료를 결정하고, Unit of Work가 실제 DB 트랜잭션을 제공한다.

```python
class UnitOfWork(Protocol):
    users: UserRepository
    items: ItemRepository
    cats: CatRepository
    assets: AssetRepository
    executions: ExecutionRepository
    placed_objects: PlacedObjectRepository
    cat_memories: CatMemoryRepository

    def __enter__(self) -> "UnitOfWork": ...
    def __exit__(self, exc_type, exc, traceback) -> None: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
```

Repository는 자체적으로 `commit()`하지 않는다. 가챠와 구매는 다음 순서로 처리한다.

1. 요청을 정규화하고 SHA-256 해시를 생성한다.
2. 트랜잭션을 시작한다.
3. `request_id`를 `claim()`한다.
4. 기존 완료 요청이면 저장된 결과를 반환한다.
5. 해시 또는 사용자가 충돌하면 `409 Conflict`로 거부한다.
6. 신규 요청이면 사용자 행과 필요한 자산 행을 잠근다.
7. 잔액을 검증하고 차감한다.
8. 자산을 생성하거나 수량을 갱신한다.
9. 실행의 `result_data`, 비용과 완료 상태를 저장한다.
10. 한 번만 커밋한다.

다음 변경은 반드시 동일한 트랜잭션에 포함한다.

- `USERS.balance` 차감
- `USERS.mileage` 변경
- `ASSETS` 자산 지급 또는 수량 변경
- `GACHA_EXECUTIONS.result_data` 및 완료 상태 저장

중간에 실패하면 모든 변경을 롤백한다.

단일 트랜잭션에서 실행 기록도 함께 생성하면 처리 도중 실패한 행은 롤백된다. MVP에서는 성공 실행을 `COMPLETED`로 저장하고 실패 요청은 실행 행까지 롤백한다. `FAILED` 기록 보존이 필요해지면 별도 감사 로그 정책으로 정의한다.

## 4. API 공개 식별자 계약

API는 UUID `public_id`만 입력받고 반환한다. 인증 사용자의 내부 정수 PK와 외부 UUID 변환은 API 또는 Repository 경계에서 수행한다.

아이템 구매 요청 예시:

```json
{
  "request_id": "a5f88e4e-78b7-4ce6-a925-79d20d1f85e9",
  "item_public_id": "fb8821d9-8cba-4648-9e95-8fbe175cd793",
  "quantity": 2
}
```

응답 예시:

```json
{
  "execution_public_id": "a17169ab-d732-4e42-a717-36733f6f9e59",
  "request_id": "a5f88e4e-78b7-4ce6-a925-79d20d1f85e9",
  "item_public_id": "fb8821d9-8cba-4648-9e95-8fbe175cd793",
  "purchased_quantity": 2,
  "total_quantity": 5,
  "balance": 700
}
```

`user_id`, `item_id`, `cat_id`, `cat_asset_id`와 같은 내부 정수 식별자는 API 응답 스키마에 포함하지 않는다. 공개 UUID는 인증과 소유권 검사를 대체하지 않는다.

권장 HTTP 상태 코드는 다음과 같다.

| 상황 | HTTP 상태 |
| --- | --- |
| 정상 처리 | `200 OK` 또는 `201 Created` |
| 동일 요청 재시도 | 최초 성공과 동일한 상태 및 결과 |
| 동일 키의 사용자 또는 해시 충돌 | `409 Conflict` |
| 잔액 부족 | `409 Conflict` |
| 아이템, 고양이 또는 자산 없음 | `404 Not Found` |
| 다른 사용자의 자산 접근 | `404 Not Found` |
| 요청 형식 오류 | `422 Unprocessable Entity` |

## 5. 요청 해시 정규화 계약

모든 실행 경로와 테스트는 동일한 정규화 규칙을 사용한다.

```python
import hashlib
import json


canonical_payload = {
    "operation_type": "ITEM_PURCHASE",
    "item_public_id": str(item_public_id),
    "quantity": quantity,
}

canonical_json = json.dumps(
    canonical_payload,
    sort_keys=True,
    separators=(",", ":"),
    ensure_ascii=False,
)
request_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
```

정규화 규칙은 다음과 같다.

- JSON 객체의 키를 정렬한다.
- 불필요한 공백을 제거한다.
- UUID는 소문자 표준 문자열로 변환한다.
- `operation_type`을 반드시 포함한다.
- `request_id`는 해시 대상에서 제외한다.
- 가격, 잔액, 마일리지처럼 서버가 결정하는 값은 해시 대상에서 제외한다.
- 인증 사용자는 실행 행의 `user_id`로 별도 검증한다.
- 전역 UNIQUE인 같은 `request_id`를 다른 사용자가 재사용하면 `409 Conflict`로 처리한다.

## 6. 기능별 불변 규칙

### 가챠와 고양이

- 가챠 비용, 확률과 중복 마일리지는 서비스에 하드코딩하지 않고 정책 객체로 주입한다.
- 멱등 요청 payload에는 클라이언트가 결정한 `draw_count`만 포함하고 서버 정책값은 요청 해시에서 제외한다.
- 처음 획득한 고양이는 `ASSETS.quantity = 1`로 생성한다.
- 이미 보유한 고양이는 새 자산 행을 만들거나 수량을 증가시키지 않는다.
- 중복 고양이 보상은 같은 트랜잭션에서 `USERS.mileage`로 전환한다.
- 가챠 결과에는 고양이 내부 정수 ID 대신 `cat_public_id`를 저장하고 반환한다.

### 상점

- 일반 아이템의 동일 `(user_id, item_id)` 자산은 하나만 존재한다.
- 재구매하면 새 행을 만들지 않고 `quantity`를 합산한다.
- 벽지와 바닥은 소유 여부와 카테고리를 확인한 뒤 `USERS`의 선택 FK를 변경한다.
- 표면 적용은 `WALLPAPER`와 `FLOOR`만 허용하고 보유 자산 행과 사용자 행을 잠근다.
- 벽지를 변경할 때 바닥 선택은 유지하고, 바닥을 변경할 때 벽지 선택은 유지한다.
- 표면 적용 응답에는 내부 정수 FK 대신 `user_public_id`, `item_public_id`와 카테고리만 포함한다.

### 하우징

- `PLACED_OBJECTS`에는 `FURNITURE` 카테고리만 배치한다.
- 동일 사용자의 아이템별 배치 행 수는 보유 `quantity`를 초과할 수 없다.
- 배치 수량 검증에는 동시 요청을 막을 수 있는 잠금을 사용한다.
- 배치 해제는 `PLACED_OBJECTS` 행만 삭제하며 보유 자산 수량은 줄이지 않는다.
- `position_data`는 3축 위치 좌표 `x`, `y`, `z`를 필수 유한 숫자로 검증하고 알 수 없는 필드를 거부한다.
- 이전 `rotation` 필드는 허용하지 않으며 기존 JSONB 데이터는 마이그레이션으로 같은 값을 `z`에 옮긴다.
- 실제 방 크기에 따른 `x`, `y`, `z` 최솟값과 최댓값은 정책 확정 전까지 임의로 하드코딩하지 않는다.
- 수정과 해제는 `placed_object_public_id`로 대상 행을 잠그고 인증 사용자 소유가 아니면 찾을 수 없는 것으로 처리한다.

### 고양이 기억

- `CAT_MEMORIES.cat_asset_id`는 `ASSETS` 중 고양이 자산에만 연결한다.
- 아이템 자산에는 기억을 연결할 수 없다.
- 인증 사용자가 소유한 고양이 자산에만 기억을 추가하거나 조회할 수 있다.
- 대화 요약은 새 `CAT_MEMORIES` 행으로 누적 기록한다.
- 공백뿐인 대화 요약은 저장하지 않는다.
- 기억 목록은 `created_at`, `id` 오름차순으로 반환한다.
- 선택 삭제는 `memory_public_id`로 대상 기억을 잠금 조회하고, 요청한 고양이 자산의 기억인지 다시 확인한다.
- 전체 삭제는 지정한 `cat_asset_id`에 연결된 `CAT_MEMORIES` 행만 삭제한다.
- 선택 삭제와 전체 삭제는 `CATS.persona`, `CATS` 행과 `ASSETS` 행을 삭제하거나 변경하지 않는다.
- 다른 사용자의 고양이 자산 또는 기억 접근은 리소스 존재 여부를 숨기기 위해 `404 Not Found`로 처리한다.

#### Frontend ↔ Backend 데이터 계약 빠른 참조

이 표는 프런트엔드 연결에 필요한 인증 보조 API 2개와 Part 3 기능 API 10개를 한곳에 정리한다. 각 기능의 상세 JSON과 오류 계약은 바로 아래 절을 따른다.

| 기능 | 메서드·경로 | Frontend → Backend | Backend → Frontend |
| --- | --- | --- | --- |
| 개발 사용자 준비 | `POST /api/v1/session/development` | 본문 없음 | 사용자 공개 프로필 |
| 현재 사용자 확인 | `GET /api/v1/session/me` | 인증 헤더 | 사용자 공개 프로필 |
| 고양이 대화 컨텍스트 | `GET /api/v1/cats/{cat_asset_public_id}/conversation-context` | 고양이 보유 자산 UUID | 고양이·persona·기억 목록 |
| 기억 추가 | `POST /api/v1/cats/{cat_asset_public_id}/memories` | `context_summary` | 생성된 기억 |
| 기억 선택 삭제 | `DELETE /api/v1/cats/{cat_asset_public_id}/memories/{memory_public_id}` | 고양이 자산·기억 UUID | 본문 없음 |
| 기억 전체 삭제 | `DELETE /api/v1/cats/{cat_asset_public_id}/memories` | 고양이 자산 UUID | 본문 없음 |
| 아이템 구매 | `POST /api/v1/shop/purchases` | 멱등 키·아이템 UUID·수량 | 구매 결과·보유 수량·잔액 |
| 벽지·바닥 적용 | `PUT /api/v1/housing/surfaces/{item_public_id}` | 아이템 UUID | 적용된 표면 종류 |
| 가구 배치 | `POST /api/v1/housing/placed-objects` | 아이템 UUID·좌표 | 생성된 배치 객체 |
| 가구 위치 수정 | `PATCH /api/v1/housing/placed-objects/{placed_object_public_id}` | 배치 UUID·새 좌표 | 수정된 배치 객체 |
| 가구 배치 해제 | `DELETE /api/v1/housing/placed-objects/{placed_object_public_id}` | 배치 UUID | 본문 없음 |
| 고양이 가챠 | `POST /api/v1/gacha/draws` | 멱등 키·추첨 횟수 | 비용·잔액·마일리지·추첨 결과 |

공통 클라이언트 규칙은 다음과 같다.

- 기본 URL prefix는 `/api/v1`이다.
- JSON 본문이 있는 요청은 `Content-Type: application/json`을 사용한다.
- 로컬·테스트 환경의 보호 API에는 `X-User-Public-ID: <사용자 UUID>`를 보낸다.
- 외부 식별자는 `public_id`, `*_public_id` 형식의 UUID만 사용하고 내부 INTEGER ID는 보내거나 받지 않는다.
- 가격, 잔액 차감액, 가챠 확률과 마일리지는 서버 계산값이므로 요청에 넣지 않는다.
- `204 No Content` 응답에는 본문이 없으므로 JSON 파싱을 시도하지 않는다.
- 구매와 가챠의 `request_id`는 동작마다 새 UUID를 생성하되, 같은 동작의 네트워크 재시도에는 같은 UUID를 재사용한다.

##### 인증 보조 API

로컬·테스트 환경에서 프런트엔드는 먼저 다음 요청으로 개발 사용자를 생성하거나 재사용할 수 있다.

```http
POST /api/v1/session/development
```

`200 OK` 응답:

```json
{
  "public_id": "8a4a9c2f-645f-4b94-9b5d-16bc7d563f42",
  "email": "player@local.nyang",
  "username": "{ 냥 } 플레이어",
  "role": "STUDENT",
  "balance": 1100000,
  "mileage": 0,
  "house_level": 1,
  "created_at": "2026-09-04T12:00:00Z"
}
```

프런트엔드는 받은 `public_id`를 이후 보호 API의 `X-User-Public-ID` 값으로 사용한다. 현재 사용자 확인은 다음 요청을 사용하며 같은 공개 사용자 DTO를 반환한다.

```http
GET /api/v1/session/me
X-User-Public-ID: 8a4a9c2f-645f-4b94-9b5d-16bc7d563f42
```

인증 헤더가 없거나 사용자를 찾지 못하면 `401 Unauthorized`다. 운영 환경에서는 개발 세션 endpoint가 `404`이며 임시 UUID 헤더 대신 호스트 인증 공급자가 `CurrentUser`를 제공해야 한다.

#### 고양이 페르소나·기억 FastAPI 계약

모든 경로는 로컬·테스트 환경에서 다음 인증 헤더를 요구한다.

```http
X-User-Public-ID: 8a4a9c2f-645f-4b94-9b5d-16bc7d563f42
```

운영 환경에서는 호스트 인증 공급자가 `CurrentUser`를 제공하며 임시 UUID 헤더를 사용하지 않는다.

##### 페르소나와 기억 전체 조회

```http
GET /api/v1/cats/39db1ddb-24c2-42dc-a28c-bc4d9dd5267e/conversation-context
```

`200 OK` 응답:

```json
{
  "cat_asset_public_id": "39db1ddb-24c2-42dc-a28c-bc4d9dd5267e",
  "cat_public_id": "063115f5-749f-43ff-9016-eb9dc4203d30",
  "name": "나비",
  "persona": "차분하고 다정한 고양이",
  "memories": [
    {
      "public_id": "5ad14e95-d2da-4628-9632-599390490abe",
      "cat_asset_public_id": "39db1ddb-24c2-42dc-a28c-bc4d9dd5267e",
      "context_summary": "사용자는 반복문을 공부했다.",
      "created_at": "2026-09-04T12:00:00Z"
    }
  ]
}
```

기억이 없으면 `memories`는 빈 배열이다. `persona`는 `CATS`의 고정 데이터이며 기억 삭제로 변경되지 않는다.

##### 기억 추가

```http
POST /api/v1/cats/39db1ddb-24c2-42dc-a28c-bc4d9dd5267e/memories
Content-Type: application/json
```

요청 본문:

```json
{
  "context_summary": "사용자는 함수 호출을 이해했다."
}
```

`201 Created` 응답:

```json
{
  "public_id": "a816c517-cc27-418b-b32b-277b40d37af2",
  "cat_asset_public_id": "39db1ddb-24c2-42dc-a28c-bc4d9dd5267e",
  "context_summary": "사용자는 함수 호출을 이해했다.",
  "created_at": "2026-09-04T13:00:00Z"
}
```

`context_summary`가 없거나 문자열이 아니거나 공백뿐이면 `422`다. 요청 스키마는 알 수 없는 필드를 거부한다.

##### 기억 선택 삭제

```http
DELETE /api/v1/cats/39db1ddb-24c2-42dc-a28c-bc4d9dd5267e/memories/5ad14e95-d2da-4628-9632-599390490abe
```

성공 시 `204 No Content`이며 응답 본문은 없다. 선택한 기억이 요청한 고양이 자산의 기억이 아니거나 접근 권한이 없으면 `404`다.

##### 기억 전체 삭제

```http
DELETE /api/v1/cats/39db1ddb-24c2-42dc-a28c-bc4d9dd5267e/memories
```

성공 시 `204 No Content`이며 응답 본문은 없다. 지정한 고양이 자산의 `CAT_MEMORIES`만 삭제하고 `CATS.persona`, 고양이 마스터와 보유 자산은 유지한다.

##### 공통 오류 응답

인증 및 도메인 오류는 다음 형태를 사용한다.

```json
{
  "detail": "cat asset not found"
}
```

| 상태 | 의미 |
| --- | --- |
| `401 Unauthorized` | 인증 헤더가 없거나 개발 사용자를 찾을 수 없음 |
| `404 Not Found` | 고양이 자산·기억이 없거나 인증 사용자가 소유하지 않음 |
| `422 Unprocessable Content` | UUID, 요청 본문 또는 기억 요약이 유효하지 않음 |

FastAPI/Pydantic의 경로·본문 검증 `422`는 `detail` 배열을 사용하고, 서비스의 공백 요약 `422`는 안전한 도메인 메시지를 `detail` 문자열로 반환한다.

#### 나머지 Part 3 FastAPI 계약

다음 경로도 고양이 API와 동일한 `CurrentUser` 인증을 요구하며 API 입력과 출력에는 공개 UUID만 사용한다.

##### 아이템 구매

```http
POST /api/v1/shop/purchases
Content-Type: application/json
```

```json
{
  "request_id": "01a996ae-c8f5-4388-bf1e-a911717fa2bd",
  "item_public_id": "ee50a4a7-f05d-44b2-ac84-9b0276eeedfe",
  "quantity": 2
}
```

성공 시 `201 Created`이며 `execution_public_id`, `request_id`, `item_public_id`, `purchased_quantity`, `total_quantity`, `balance`를 반환한다. 동일 사용자·동일 요청 내용의 `request_id` 재시도는 저장된 결과를 반환한다. 리소스 부재는 `404`, 멱등 충돌과 잔액 부족은 `409`, 0 이하 수량이나 잘못된 본문은 `422`다.

##### 벽지·바닥 적용

```http
PUT /api/v1/housing/surfaces/ee50a4a7-f05d-44b2-ac84-9b0276eeedfe
```

요청 본문은 없다. 성공 시 `200 OK`로 다음 공개 응답을 반환한다.

```json
{
  "user_public_id": "8a4a9c2f-645f-4b94-9b5d-16bc7d563f42",
  "item_public_id": "ee50a4a7-f05d-44b2-ac84-9b0276eeedfe",
  "category": "WALLPAPER"
}
```

사용자·아이템·보유 자산 부재는 `404`, `WALLPAPER` 또는 `FLOOR`가 아닌 카테고리는 `422`다.

##### 가구 배치·수정·해제

배치는 다음 요청으로 생성한다.

```http
POST /api/v1/housing/placed-objects
Content-Type: application/json
```

```json
{
  "item_public_id": "ee50a4a7-f05d-44b2-ac84-9b0276eeedfe",
  "position_data": {"x": 1.0, "y": 2.0, "z": 0.0}
}
```

성공 시 `201 Created`로 `public_id`, `item_public_id`, `position_data`를 반환한다. 배치 수정은 `PATCH /api/v1/housing/placed-objects/{placed_object_public_id}`에 `position_data`만 보내고 같은 응답을 `200 OK`로 받는다. 해제는 같은 경로에 `DELETE`를 보내며 성공 시 본문 없는 `204 No Content`다. 리소스·소유권 오류는 `404`, 가구가 아닌 카테고리나 잘못된 좌표는 `422`, 보유 수량을 초과한 배치는 `409`다. 좌표 객체는 `x`, `y`, `z`를 모두 요구하고 알 수 없는 필드와 무한값을 거부한다.

##### 고양이 가챠

```http
POST /api/v1/gacha/draws
Content-Type: application/json
```

```json
{
  "request_id": "01a996ae-c8f5-4388-bf1e-a911717fa2bd",
  "draw_count": 10
}
```

정책이 주입된 환경에서는 성공 시 `200 OK`로 다음 형태를 반환한다.

```json
{
  "execution_public_id": "3cded9b5-2655-471e-90c8-3a63a9c43018",
  "request_id": "01a996ae-c8f5-4388-bf1e-a911717fa2bd",
  "draw_count": 10,
  "balance_cost": 1000,
  "balance": 4200,
  "mileage": 30,
  "results": [
    {
      "cat_public_id": "063115f5-749f-43ff-9016-eb9dc4203d30",
      "name": "나비",
      "rarity": "RARE",
      "is_duplicate": false,
      "mileage_awarded": 0
    }
  ]
}
```

위 숫자는 응답 형태 설명용 예시이며 실제 비용·확률·중복 마일리지 정책값이 아니다. 현재 기본 `get_gacha_policy()`는 정책 미확정 상태를 숨기지 않고 `503 Service Unavailable`을 반환한다. 테스트와 배포 환경은 확정된 `GachaPolicy`를 의존성으로 주입해야 한다. 리소스 부재는 `404`, 멱등 충돌과 잔액 부족은 `409`, 0 이하 추첨 수나 잘못된 본문은 `422`다.

## 7. 통합 완료 체크리스트

- [x] 보유 자산 테이블과 Python 모델명을 `assets`와 `Asset`으로 확정했다.
- [x] 모든 Repository 메서드와 반환형이 이 문서와 일치한다.
- [x] Repository 구현체가 자체적으로 커밋하지 않는다.
- [x] 서비스 하나가 가챠 또는 구매 트랜잭션 전체를 소유한다.
- [x] 잠금이 필요한 Repository 메서드에 `for_update`가 명시돼 있다.
- [x] API 요청과 응답에는 UUID `public_id`만 사용한다.
- [x] 내부 정수 PK가 응답 스키마에서 제외돼 있다.
- [x] 정규 JSON과 SHA-256 생성 규칙이 단일 함수로 구현돼 있다.
- [x] 동일 키의 다른 사용자 또는 다른 내용은 `409 Conflict`로 처리한다.
- [x] DB 구현 전 단위 테스트는 동일 Repository 계약의 Fake를 사용한다.
- [ ] PostgreSQL 통합 테스트에서 동시 멱등 요청과 자산 잠금을 검증한다.

## 8. 브라우저 클라이언트 연결

- 브라우저 허용 origin은 `CORS_ORIGINS`의 쉼표 구분 목록으로 설정한다.
- `APP_ENV=local` 또는 `test`일 때만 `POST /api/v1/session/development`가 개발 사용자를 생성하거나 재사용한다.
- 로컬·테스트 환경의 보호 API는 `X-User-Public-ID`에서 공개 UUID를 받아 사용자를 조회한다.
- 운영 환경에서는 개발 세션과 UUID 헤더 인증을 사용하지 않으며 호스트 인증 공급자가 `get_current_user`를 대체해야 한다.
- 학습 추천 응답은 화면 분류에 사용할 `concept_name`을 포함하되 채점 답과 내부 정수 ID는 계속 제외한다.
- 저장소 루트 `Dockerfile`은 로컬 통합 환경에서 API가 호스트 Docker 데몬에 격리 채점 컨테이너를 요청할 수
  있도록 Docker CLI를 포함한다. Docker 소켓은 운영 배포의 기본 계약이 아니며 신뢰할 수 있는 로컬 환경에서만
  마운트한다.
- Alembic은 고정 예제 URL 대신 `DATABASE_URL`을 사용하므로 컨테이너와 호스트에서 동일한 설정 계약을 따른다.

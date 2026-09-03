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
| `user_cats` | `UserAsset` | 고양이와 일반 아이템을 함께 저장하는 통합 보유 자산 |
| `gacha_executions` | `GachaExecution` | 가챠와 구매 요청의 멱등성 및 결과 |
| `placed_objects` | `PlacedObject` | 하우징에 배치된 가구 인스턴스 |
| `cat_memories` | `CatMemory` | 보유 고양이별 대화 요약 기록 |

`user_cats`는 아이템도 저장하므로 Python 모델명은 `UserAsset`을 사용한다. 다른 모듈과의 기존 합의로 `UserCat`이 먼저 확정된 경우에는 중복 모델을 만들지 않고 기존 이름을 따른다.

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
    def list_by_user_cat_id(self, user_cat_id: int) -> "list[CatMemory]": ...

    def add(self, user_cat_id: int, context_summary: str) -> "CatMemory": ...
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
- `USER_CATS` 자산 지급 또는 수량 변경
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

`user_id`, `item_id`, `cat_id`, `user_cat_id`와 같은 내부 정수 식별자는 API 응답 스키마에 포함하지 않는다. 공개 UUID는 인증과 소유권 검사를 대체하지 않는다.

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
- 처음 획득한 고양이는 `USER_CATS.quantity = 1`로 생성한다.
- 이미 보유한 고양이는 새 자산 행을 만들거나 수량을 증가시키지 않는다.
- 중복 고양이 보상은 같은 트랜잭션에서 `USERS.mileage`로 전환한다.
- 가챠 결과에는 고양이 내부 정수 ID 대신 `cat_public_id`를 저장하고 반환한다.

### 상점

- 일반 아이템의 동일 `(user_id, item_id)` 자산은 하나만 존재한다.
- 재구매하면 새 행을 만들지 않고 `quantity`를 합산한다.
- 벽지와 바닥은 소유 여부와 카테고리를 확인한 뒤 `USERS`의 선택 FK를 변경한다.

### 하우징

- `PLACED_OBJECTS`에는 `FURNITURE` 카테고리만 배치한다.
- 동일 사용자의 아이템별 배치 행 수는 보유 `quantity`를 초과할 수 없다.
- 배치 수량 검증에는 동시 요청을 막을 수 있는 잠금을 사용한다.
- 배치 해제는 `PLACED_OBJECTS` 행만 삭제하며 보유 자산 수량은 줄이지 않는다.
- `position_data`는 `x`, `y`, `rotation`을 필수 유한 숫자로 검증하고 알 수 없는 필드를 거부한다.
- 실제 방 크기에 따른 좌표·회전 최솟값과 최댓값은 정책 확정 전까지 임의로 하드코딩하지 않는다.
- 수정과 해제는 `placed_object_public_id`로 대상 행을 잠그고 인증 사용자 소유가 아니면 찾을 수 없는 것으로 처리한다.

### 고양이 기억

- `CAT_MEMORIES.user_cat_id`는 고양이 자산에만 연결한다.
- 아이템 자산에는 기억을 연결할 수 없다.
- 인증 사용자가 소유한 고양이 자산에만 기억을 추가하거나 조회할 수 있다.
- 대화 요약은 새 `CAT_MEMORIES` 행으로 누적 기록한다.

## 7. 통합 완료 체크리스트

- [ ] `USER_CATS`의 Python 모델명을 팀에서 확정했다.
- [x] 모든 Repository 메서드와 반환형이 이 문서와 일치한다.
- [x] Repository 구현체가 자체적으로 커밋하지 않는다.
- [x] 서비스 하나가 가챠 또는 구매 트랜잭션 전체를 소유한다.
- [x] 잠금이 필요한 Repository 메서드에 `for_update`가 명시돼 있다.
- [ ] API 요청과 응답에는 UUID `public_id`만 사용한다.
- [ ] 내부 정수 PK가 응답 스키마에서 제외돼 있다.
- [x] 정규 JSON과 SHA-256 생성 규칙이 단일 함수로 구현돼 있다.
- [ ] 동일 키의 다른 사용자 또는 다른 내용은 `409 Conflict`로 처리한다.
- [x] DB 구현 전 단위 테스트는 동일 Repository 계약의 Fake를 사용한다.
- [ ] PostgreSQL 통합 테스트에서 동시 멱등 요청과 자산 잠금을 검증한다.

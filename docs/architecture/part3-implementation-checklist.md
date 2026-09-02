# Part 3 구현 체크리스트

이 문서는 Part 3의 가챠·상점·하우징·고양이 AI 기억 기능을 순서대로 구현하기 위한 작업 체크리스트다.

현재 진행 상태(2026-09-02): 1~4단계를 완료했다. 다음 작업은 **5. Unit of Work와 SQLAlchemy Repository**다.

구현 기준은 다음 문서다.

- `docs/architecture/part3-integration-contract.md`
- `docs/architecture/part3-status.md`
- `docs/architecture/overview.md`
- `docs/adr/0001-modular-monolith.md`

## 공통 원칙

- [ ] API 요청과 응답에 내부 INTEGER `id`를 노출하지 않는다.
- [ ] 외부 식별자는 UUID `public_id`, `*_public_id`를 사용한다.
- [ ] 내부 FK에는 INTEGER PK를 사용한다.
- [ ] 기존 `UserCat` 모델을 재사용한다.
- [ ] Repository는 `commit()`하지 않는다.
- [ ] 서비스와 Unit of Work가 전체 트랜잭션을 소유한다.
- [ ] 잠금 메서드는 이름에 `for_update`를 포함한다.
- [ ] 미확정 가격, 확률, 보상값을 임의로 하드코딩하지 않는다.

## 0. 작업 브랜치 준비

- [x] 최신 `main`을 가져온다.
- [x] Part 3 구현 브랜치 `feature/part3`를 준비한다.
- [x] 작업 폴더에 의도하지 않은 미처리 변경이 없는지 확인한다.

```bash
git switch main
git pull origin main
git switch -c feature/part3-implementation
git status
```

완료 기준:

- 새 브랜치가 최신 `origin/main`에서 시작한다.
- `git status`에 의도하지 않은 변경이 없다.

## 1. 공개 UUID DTO 변환

- [x] `UserCat` 응답에 `cat_public_id`, `item_public_id`를 변환한다.
- [x] `PlacedObject` 응답에 `item_public_id`를 변환한다.
- [x] `CatMemory` 응답에 `user_cat_public_id`를 변환한다.
- [x] 명시적인 DTO 변환 함수 또는 Repository 조회 projection을 사용한다.
- [x] 내부 `id`, `user_id`, `cat_id`, `item_id`, `user_cat_id`가 응답에 없는지 검사한다.
- [x] 공개 UUID 직렬화 테스트를 작성한다.

완료 기준:

- ORM의 내부 FK가 연결된 테이블의 `public_id`로 정확하게 변환된다.
- Part 3 응답 스키마에 내부 정수 ID가 나타나지 않는다.

커밋 확인:

- [x] UUID DTO 변환과 테스트를 한 커밋으로 정리했다.

## 2. `balance_cost`와 `claim()` 계약 정리

- [x] 신규 실행을 먼저 저장할 수 있도록 `balance_cost` 초기값을 정한다.
- [x] 권장안인 DB/ORM 기본값 `0` 적용 여부를 확정한다.
- [x] `claim()`에서 신규 실행 행을 생성할 수 있게 한다.
- [x] `complete()`에서 실제 비용으로 갱신하도록 계약을 맞춘다.
- [x] 모델과 마이그레이션을 수정한다.
- [x] 선택한 방향을 `part3-integration-contract.md`에 반영한다.
- [x] 초기 실행 생성과 음수 비용 거부 테스트를 작성한다.

현재 검증 결과:

- 모델 기본값 단위 테스트: `1 passed`
- PostgreSQL 16 마이그레이션 테스트: `6 passed`
- Ruff 대상 파일 검사: 통과
- Alembic head: `be8999b8f41e`

완료 기준:

- 비용을 아직 계산하지 않은 상태에서도 `claim()`이 실행 행을 만들 수 있다.
- 완료 시 실제 비용이 저장된다.

커밋 확인:

- [x] 계약 문서, 모델, 마이그레이션과 테스트를 커밋했다.

## 3. 요청 해시 공통 함수

- [x] 요청 payload를 정규 JSON으로 만드는 단일 함수를 구현한다.
- [x] JSON 객체 키를 정렬한다.
- [x] 불필요한 공백을 제거한다.
- [x] UUID를 소문자 표준 문자열로 변환한다.
- [x] `operation_type`을 포함한다.
- [x] `request_id`를 해시 대상에서 제외한다.
- [x] 가격, 잔액, 마일리지 등 서버 결정값을 제외한다.
- [x] SHA-256 해시를 생성한다.
- [x] 키 순서가 달라도 같은 해시가 생성되는지 테스트한다.
- [x] 요청 내용이 다르면 다른 해시가 생성되는지 테스트한다.

완료 기준:

- 구매와 가챠가 동일한 정규화 함수를 사용한다.
- 테스트 코드가 별도의 해시 규칙을 중복 구현하지 않는다.

커밋 확인:

- [x] 요청 정규화 및 해시 함수와 단위 테스트를 커밋했다.

## 4. Repository 계약과 Fake 구현

- [x] `ExecutionRepository` Protocol을 작성한다.
- [x] `UserRepository` Protocol을 작성한다.
- [x] `ItemRepository` Protocol을 작성한다.
- [x] `CatRepository` Protocol을 작성한다.
- [x] `AssetRepository` Protocol을 작성한다.
- [x] `PlacedObjectRepository` Protocol을 작성한다.
- [x] `CatMemoryRepository` Protocol을 작성한다.
- [x] 테스트용 Fake Repository를 작성한다.
- [x] 잠금 조회 메서드 이름에 `for_update`를 사용한다.
- [x] Repository에 `commit()`이 없는지 확인한다.

완료 기준:

- DB 없이 Fake Repository로 서비스 단위 테스트를 작성할 수 있다.
- Protocol이 Part 3 통합 계약과 일치한다.

커밋 확인:

- [x] Repository 계약, Fake 및 계약 테스트를 커밋했다.

## 5. Unit of Work와 SQLAlchemy Repository

- [ ] SQLAlchemy Repository 구현체를 작성한다.
- [ ] 사용자 행 잠금에 `SELECT ... FOR UPDATE`를 사용한다.
- [ ] 아이템 자산 행 잠금에 `SELECT ... FOR UPDATE`를 사용한다.
- [ ] 멱등 실행 요청을 안전하게 `claim()`한다.
- [ ] Unit of Work를 구현한다.
- [ ] 서비스만 한 번 `commit()`하도록 구성한다.
- [ ] 예외 발생 시 전체 rollback을 검증한다.

완료 기준:

- Repository는 조회, 저장, 잠금만 담당한다.
- 트랜잭션의 시작과 종료는 Unit of Work와 서비스가 담당한다.

커밋 확인:

- [ ] SQLAlchemy Repository와 Unit of Work 및 테스트를 커밋했다.

## 6. 멱등성 실행 엔진

- [ ] 신규 `request_id`를 `ACQUIRED`로 확보한다.
- [ ] 완료된 동일 요청이면 기존 `result_data`를 반환한다.
- [ ] 동일 키의 요청 해시가 다르면 `409 Conflict`로 처리한다.
- [ ] 동일 키의 사용자가 다르면 `409 Conflict`로 처리한다.
- [ ] 성공 시 상태를 `COMPLETED`로 변경한다.
- [ ] 실제 비용과 결과 데이터를 저장한다.
- [ ] 동시에 같은 요청을 보내도 한 번만 처리되는지 검증한다.

완료 기준:

- 최초 요청과 재시도 요청이 같은 상태 코드와 결과를 반환한다.
- 충돌 요청은 자산이나 잔액을 변경하지 않는다.

커밋 확인:

- [ ] 멱등성 실행 엔진과 단위·PostgreSQL 통합 테스트를 커밋했다.

## 7. 아이템 구매 및 벽지·바닥 적용

- [ ] `item_public_id`로 아이템을 조회한다.
- [ ] 요청 가격이 아닌 DB의 `ITEMS.price`로 비용을 계산한다.
- [ ] 사용자 행을 잠그고 잔액을 확인한다.
- [ ] 기존 아이템 자산의 `quantity`를 합산한다.
- [ ] 신규 아이템 자산을 생성한다.
- [ ] 벽지 소유권과 `WALLPAPER` 카테고리를 확인한다.
- [ ] 바닥 소유권과 `FLOOR` 카테고리를 확인한다.
- [ ] 구매 및 적용 API를 멱등성 트랜잭션으로 처리한다.
- [ ] 잔액 부족과 잘못된 카테고리 테스트를 작성한다.

완료 기준:

- 잔액 차감, 자산 변경, 실행 결과 저장이 하나의 트랜잭션이다.
- 재구매 시 중복 자산 행이 생성되지 않는다.

커밋 확인:

- [ ] 구매 및 표면 아이템 적용 기능과 테스트를 커밋했다.

## 8. 고양이 가챠

- [ ] 가챠 요청 및 응답 스키마를 작성한다.
- [ ] 비용, 확률과 중복 보상을 설정 또는 정책 객체로 주입한다.
- [ ] 미확정 정책값을 임의로 하드코딩하지 않는다.
- [ ] 신규 고양이는 `UserCat.quantity = 1`로 생성한다.
- [ ] 중복 고양이는 새 자산을 만들지 않는다.
- [ ] 중복 보상을 사용자 mileage로 전환한다.
- [ ] 잔액, mileage, 자산, 실행 결과를 한 트랜잭션으로 처리한다.
- [ ] 동일 요청 재시도 시 동일 결과를 반환한다.
- [ ] 중간 실패 시 전체 rollback을 검증한다.

완료 기준:

- 동일 사용자의 동일 고양이 자산은 하나만 존재한다.
- 중복 획득 시 자산 수량은 증가하지 않고 mileage만 증가한다.

커밋 확인:

- [ ] 고양이 가챠 기능과 테스트를 커밋했다.

## 9. 하우징 가구 배치

- [ ] `position_data`의 필수 필드와 범위를 Pydantic으로 검증한다.
- [ ] `FURNITURE` 카테고리만 배치한다.
- [ ] 인증 사용자의 보유 자산 행을 잠근다.
- [ ] 현재 배치 수량과 보유 수량을 비교한다.
- [ ] 보유 수량 초과 배치를 차단한다.
- [ ] 배치 생성 API를 작성한다.
- [ ] 배치 수정 API를 작성한다.
- [ ] 배치 해제 API를 작성한다.
- [ ] 다른 사용자의 배치 객체 접근은 `404 Not Found`로 처리한다.
- [ ] 동시에 배치해도 보유 수량을 초과하지 않는지 PostgreSQL에서 검증한다.

완료 기준:

- 배치 해제 시 보유 자산 수량은 감소하지 않는다.
- 동시 요청에서도 배치 수량이 보유 수량을 초과하지 않는다.

커밋 확인:

- [ ] 하우징 배치 기능과 동시성 테스트를 커밋했다.

## 10. 고양이 AI 기억

- [ ] `user_cat_public_id`로 보유 고양이 자산을 조회한다.
- [ ] 인증 사용자의 소유권을 검사한다.
- [ ] 아이템 자산에는 기억을 생성하지 못하게 한다.
- [ ] `context_summary`를 새 `CatMemory` 행으로 누적한다.
- [ ] 고양이별 기억 목록을 조회한다.
- [ ] 다른 사용자의 자산 접근은 `404 Not Found`로 처리한다.
- [ ] 응답에 내부 `user_cat_id`가 없는지 테스트한다.

완료 기준:

- 기존 기억을 덮어쓰지 않고 대화 요약이 순서대로 누적된다.
- 인증 사용자가 소유한 고양이 자산만 조회하고 기록할 수 있다.

커밋 확인:

- [ ] 고양이 기억 기능과 테스트를 커밋했다.

## 11. FastAPI 라우터 연결

- [ ] 구매 API를 라우터에 연결한다.
- [ ] 벽지·바닥 적용 API를 라우터에 연결한다.
- [ ] 가챠 API를 라우터에 연결한다.
- [ ] 가구 배치·수정·해제 API를 라우터에 연결한다.
- [ ] 고양이 기억 생성·조회 API를 라우터에 연결한다.
- [ ] 인증 사용자의 `public_id`를 내부 `id`로 변환한다.
- [ ] 도메인 예외를 `404`, `409`, `422`로 변환한다.
- [ ] OpenAPI 스키마에 내부 정수 ID가 없는지 확인한다.

완료 기준:

- 모든 Part 3 기능이 인증과 소유권 검사를 통과해야 실행된다.
- API 입력과 출력은 공개 UUID 계약을 준수한다.

커밋 확인:

- [ ] Part 3 라우터와 API 테스트를 커밋했다.

## 12. 최종 PostgreSQL 통합 검증

- [ ] 빈 PostgreSQL DB에서 `alembic upgrade head`를 실행한다.
- [ ] 전체 Pytest를 실행한다.
- [ ] Ruff 검사를 실행한다.
- [ ] 동일 멱등 요청의 동시 실행을 검증한다.
- [ ] 다른 사용자의 동일 `request_id` 사용을 검증한다.
- [ ] 가구 동시 배치를 검증한다.
- [ ] 잔액 부족 시 전체 rollback을 검증한다.
- [ ] 중복 고양이 mileage 처리 실패 시 전체 rollback을 검증한다.
- [ ] 실행 결과 저장 실패 시 전체 rollback을 검증한다.
- [ ] API 응답에 내부 정수 ID가 없는지 최종 검사한다.
- [ ] `docs/architecture/part3-status.md`를 갱신한다.

```bash
python -m pytest -q
python -m ruff check .
```

완료 기준:

- 실제 PostgreSQL에서 마이그레이션, 트리거, 잠금과 동시성 테스트가 통과한다.
- 실행한 테스트와 남은 위험이 문서와 PR 설명에 기록돼 있다.

커밋 확인:

- [ ] 최종 테스트와 상태 문서 갱신을 커밋했다.

## 전체 진행 상태

- [x] 0. 작업 브랜치 준비
- [x] 1. 공개 UUID DTO 변환
- [x] 2. `balance_cost`와 `claim()` 계약 정리
- [x] 3. 요청 해시 공통 함수
- [x] 4. Repository 계약과 Fake 구현
- [ ] 5. Unit of Work와 SQLAlchemy Repository
- [ ] 6. 멱등성 실행 엔진
- [ ] 7. 아이템 구매 및 벽지·바닥 적용
- [ ] 8. 고양이 가챠
- [ ] 9. 하우징 가구 배치
- [ ] 10. 고양이 AI 기억
- [ ] 11. FastAPI 라우터 연결
- [ ] 12. 최종 PostgreSQL 통합 검증

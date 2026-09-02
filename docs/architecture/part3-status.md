# Part 3 착수 상태

이 문서는 로컬 Codex와 Codex cloud가 같은 기준으로 Part 3 작업을 이어가기 위한 현재 상태 기록이다.

2026-09-02 기준으로 `origin/main`의 Part 1 안정화 변경을 `feature/part3`에 병합한 뒤 다시 점검했다.

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

### 4. 멱등성 claim과 비용 컬럼 — 구현 진행 중

통합 계약처럼 실행을 먼저 `claim()`한 뒤 비용을 계산할 수 있도록 `GachaExecution.balance_cost`에 ORM 기본값과 DB 서버 기본값 `0`을 적용했다. `NOT NULL`과 `balance_cost >= 0` 제약은 그대로 유지한다.

- `app/models/gacha_execution.py`에 `default=0`, `server_default=text("0")`을 추가했다.
- `be8999b8f41e_add_balance_cost_default.py` 마이그레이션으로 기존 PostgreSQL 스키마에도 서버 기본값을 추가한다.
- `tests/unit/models/test_gacha_execution.py`가 ORM 및 서버 기본값 메타데이터를 검증한다.
- `tests/integration/db/test_migrations.py`가 비용을 생략한 실행 행의 값이 `0`인지 검증한다.
- 새 마이그레이션은 `6e7f8a9b0c1d`를 잇는 유일한 Alembic head다.

로컬에서는 모델 단위 테스트가 통과했지만 PostgreSQL 연결이 없어 DB 통합 테스트는 건너뛰었다. 실제 DB 마이그레이션 검증과 `complete()`의 실제 비용 갱신은 남아 있다.

### 5. 계약 테스트

다음 검증은 추가됐다.

- Alembic 신규 설치, 전체 롤백 및 재설치
- 5개 트리거의 대표 허용/거부 사례
- 공개 UUID DTO 직렬화
- `balance_cost`의 ORM/DB 기본값 메타데이터

다음 Part 3 검증은 기능 구현과 함께 추가해야 한다.

- 동일 요청 재시도와 해시 충돌
- 비용을 생략한 `claim()` 실행 행의 DB 기본값 `0`
- 다른 사용자의 동일 `request_id` 사용
- 동시 가구 배치 및 자산 행 잠금
- 잔액, 마일리지, 자산, 실행 결과의 원자적 롤백

## 권장 작업 순서

1. `balance_cost`와 `claim()` 계약 정리
2. Repository Protocol과 Fake 기반 단위 테스트
3. SQLAlchemy Repository와 Unit of Work
4. 구매 및 가챠 멱등성 서비스
5. 하우징 배치와 표면 아이템 적용
6. 고양이 기억 API
7. PostgreSQL 동시성 통합 테스트

## 웹 작업 시작 프롬프트

Codex cloud에서 새 작업을 시작할 때 다음처럼 요청한다.

> 이 저장소의 `AGENTS.md`, `docs/architecture/part3-integration-contract.md`, `docs/architecture/part3-status.md`를 먼저 읽어라. Part 3 착수 전 공통 기반 문제 중 하나만 선택해 현재 코드와 계약을 대조하고, 테스트를 먼저 추가한 뒤 수정하라. 내부 INTEGER id를 API에 노출하지 말고 Repository에서 commit하지 마라. 완료 후 실행한 검사와 남은 위험을 보고하라.

한 대화에서 전체 Part 3를 한꺼번에 요청하지 말고 권장 작업 순서의 한 항목씩 진행한다.

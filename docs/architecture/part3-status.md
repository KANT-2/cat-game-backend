# Part 3 착수 상태

이 문서는 로컬 Codex와 Codex cloud가 같은 기준으로 Part 3 작업을 이어가기 위한 현재 상태 기록이다.

기준 커밋은 `e5f7b44`이며, `feature/part3`에 Part 1의 DB 모델, 마이그레이션, 응답 스키마와 트리거가 병합된 직후를 점검했다.

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

## Part 3 전에 해결할 공통 기반 문제

### 1. PostgreSQL 마이그레이션 실행 환경

- `pyproject.toml`에 `alembic`과 `psycopg`가 없다.
- 최초 마이그레이션에 `CREATE EXTENSION IF NOT EXISTS pgcrypto`가 없다.
- 실제 `alembic.ini`, 로컬 `.env`, PostgreSQL 실행 구성은 개발 환경에서 별도로 준비해야 한다.

### 2. SQLAlchemy Base와 Alembic 메타데이터

- `app/models/base.py`와 `app/db/base.py`에 서로 다른 Base가 있다.
- `migrations/env.py`가 실제 모델 모듈을 import하지 않아 Base만 불러오면 메타데이터 테이블 수가 0이다.
- Base를 하나로 통일하고 Alembic이 16개 모델을 모두 등록하도록 수정해야 한다.

### 3. 공개 UUID 응답 직렬화

다음 응답 스키마는 `*_public_id`를 요구하지만 현재 ORM 모델에는 내부 FK만 있고 관계 또는 변환 속성이 없다.

- `UserCatRead.cat_public_id`, `item_public_id`
- `PlacedObjectRead.item_public_id`
- `CatMemoryRead.user_cat_public_id`

Repository 조회 결과를 명시적인 DTO로 변환하거나 필요한 관계/투영을 구현해야 한다.

### 4. 멱등성 claim과 비용 컬럼

통합 계약은 실행을 먼저 `claim()`한 뒤 비용을 계산하도록 정의한다. 현재 `GachaExecution.balance_cost`는 NOT NULL이고 기본값이 없으며 `claim()` 계약에는 비용 인자가 없다.

권장 방향은 신규 실행에 DB/ORM 기본값 `0`을 적용하고 `complete()`에서 실제 비용으로 갱신하는 것이다. 다른 방향을 선택하면 통합 계약도 함께 수정한다.

### 5. 계약 테스트

현재 자동 테스트는 `/health` 한 건뿐이다. 다음 검증을 추가해야 한다.

- Alembic 신규 설치 및 롤백
- 5개 트리거의 허용/거부 사례
- 공개 UUID 직렬화
- 동일 요청 재시도와 해시 충돌
- 다른 사용자의 동일 `request_id` 사용
- 동시 가구 배치 및 자산 행 잠금
- 잔액, 마일리지, 자산, 실행 결과의 원자적 롤백

## 권장 작업 순서

1. PostgreSQL/Alembic 의존성과 실행 환경 정리
2. SQLAlchemy Base 및 메타데이터 등록 통일
3. 공개 UUID DTO 변환 방식 확정
4. `balance_cost`와 `claim()` 계약 정리
5. Repository Protocol과 Fake 기반 단위 테스트
6. SQLAlchemy Repository와 Unit of Work
7. 구매 및 가챠 멱등성 서비스
8. 하우징 배치와 표면 아이템 적용
9. 고양이 기억 API
10. PostgreSQL 동시성 통합 테스트

## 웹 작업 시작 프롬프트

Codex cloud에서 새 작업을 시작할 때 다음처럼 요청한다.

> 이 저장소의 `AGENTS.md`, `docs/architecture/part3-integration-contract.md`, `docs/architecture/part3-status.md`를 먼저 읽어라. Part 3 착수 전 공통 기반 문제 중 하나만 선택해 현재 코드와 계약을 대조하고, 테스트를 먼저 추가한 뒤 수정하라. 내부 INTEGER id를 API에 노출하지 말고 Repository에서 commit하지 마라. 완료 후 실행한 검사와 남은 위험을 보고하라.

한 대화에서 전체 Part 3를 한꺼번에 요청하지 말고 권장 작업 순서의 한 항목씩 진행한다.

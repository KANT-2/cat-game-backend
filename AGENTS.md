# Cat Game Backend 작업 지침

## 프로젝트 목표

이 저장소는 코딩 학습, 일일 출석, 배틀, 경제, 상점, 가챠, 고양이 AI와 하우징을 제공하는 FastAPI 기반 모듈형 모놀리스다.

현재 이 브랜치의 담당 범위는 Part 3이다.

- 가챠 및 구매 멱등성 트랜잭션
- 상점과 하우징
- 고양이 보유 자산과 중복 마일리지 전환
- 고양이 AI 대화 기억 누적

## 작업 전 필독 문서

1. `docs/architecture/part3-integration-contract.md`
2. `docs/architecture/part3-status.md`
3. `docs/architecture/overview.md`
4. `docs/adr/0001-modular-monolith.md`

최종 ERD와 Part 3 통합 계약을 구현 기준으로 사용한다. 이전 프로젝트의 모델이나 스키마를 복사해 기준으로 삼지 않는다.

## 필수 구현 규칙

- API 요청과 응답에 내부 INTEGER `id`를 노출하지 않는다.
- 외부 식별자는 UUID `public_id`와 `*_public_id` 이름을 사용한다.
- 내부 FK에는 INTEGER PK를 사용한다.
- `user_cats`의 Python 모델은 기존 `UserCat`을 재사용한다. 별도의 중복 모델을 만들지 않는다.
- Repository는 조회, 저장, 잠금만 담당하며 `commit()`하지 않는다.
- 서비스와 Unit of Work가 전체 업무 트랜잭션을 소유한다.
- 잔액·마일리지 변경, 자산 지급, 실행 결과 저장은 하나의 트랜잭션으로 처리한다.
- 잠금 메서드는 이름에 `for_update`를 포함하고 PostgreSQL 행 잠금을 사용한다.
- 요청 해시는 통합 계약의 정규 JSON 및 SHA-256 규칙을 단일 함수로 구현한다.
- 동일한 `request_id`의 사용자 또는 요청 해시가 다르면 `409 Conflict`로 처리한다.
- 정책 문서에서 미확정인 가격, 확률, 보상값을 임의로 하드코딩하지 않는다.

## 현재 통합 상태

Part 1의 16개 테이블, ORM 모델, 응답 스키마와 5개 트리거가 병합되어 있다. 하지만 Part 3 구현 전에 `docs/architecture/part3-status.md`에 기록된 공통 기반 문제를 먼저 해결해야 한다.

특히 다음 항목을 미해결 상태로 가정하지 말고 실제 코드와 테스트로 확인한다.

- Alembic 및 PostgreSQL 드라이버 의존성
- 단일 SQLAlchemy Base와 Alembic 모델 메타데이터 등록
- `gen_random_uuid()` 확장 활성화
- ORM 객체에서 공개 UUID 응답 DTO로의 변환
- `GachaExecution.balance_cost`와 멱등성 `claim()` 계약의 호환성

## 설치 및 검사

Python 3.12를 기준으로 한다.

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest -q
python -m ruff check .
```

PostgreSQL 관련 변경은 단위 테스트만으로 완료 처리하지 않는다. 마이그레이션과 트리거를 실제 PostgreSQL에서 검증하고, 동시 멱등 요청과 자산 잠금 통합 테스트를 추가한다.

## 변경 원칙

- 기존 팀원의 변경과 관련 없는 파일은 수정하지 않는다.
- 계약 변경이 필요하면 코드보다 계약 문서를 먼저 또는 같은 커밋에서 갱신한다.
- 기능별 모듈 경계를 유지한다.
- 작업 완료 시 실행한 테스트와 남은 위험을 명시한다.

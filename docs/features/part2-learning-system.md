# Part 2 학습 문제·채점·추천 MVP

Python 학습 문제 150개를 로컬 DB에 중복 없이 넣는 시드와 코드형/객관식 공통 제출, 개념별 숙련도 및 추천 기능을 추가했다. 로그인과 프로필 기능은 변경하지 않았다.

## 문제 구성

| 난이도 | 개수 | 성격 |
|---|---:|---|
| BRONZE | 50 | 변수, 문자열, 조건문, 반복문, 리스트, 튜플, 집합, 딕셔너리 등 단일 기초 개념 |
| SILVER | 50 | 정렬·파싱·컬렉션·반복 등 여러 개념을 섞은 응용 |
| GOLD | 50 | 함수 작성, 탐색, 동적 계획법, 그래프 기초 등 종합 문제 |

각 문제는 대표 개념 하나만 `concept_id`로 가진다. 개념 이름은 `PYTHON:variables`처럼 domain 접두사를 써서 향후 `SQL:DISTINCT`와 충돌하지 않는다. `tasks.domain`은 `PYTHON`과 `SQL`, 난이도는 `BRONZE`, `SILVER`, `GOLD`만 허용한다.

시드는 `scripts/seed_learning_tasks.py`로 실행한다. 안정적인 `[SAMPLE:PYTHON:...]` 제목을 기준으로 새 행은 만들고 기존 행은 갱신해 재실행해도 150개를 유지한다. `[BENCHMARK]`, `BENCHMARK:`, `LOAD TEST:`, `PERF TEST:`로 시작하는 문제와 그 시도만 정리한다. `scripts/benchmark_grader_load.py`는 DB 데이터를 만들지 않는 개발 도구라 유지한다.

## 객관식 저장과 채점

`Task.type`은 `CODE` 또는 `MULTIPLE_CHOICE`다. 객관식 보기는 `options` JSON, 정답 키는 `correct_option`에 저장한다. 공개 `TaskRead`에는 보기만 들어가며 `correct_option`과 코드형 `test_cases`는 들어가지 않는다.

기존 `POST /api/v1/attempts`에 코드형은 `submitted_code`, 객관식은 `selected_option` 하나만 보낸다. 서버는 실제 보기 키인지 확인한다. 객관식 runner는 키를 직접 비교해 Docker를 실행하지 않는다. 시도 저장, 상태 변경, 결과 조회, DAILY 완료는 코드형과 같은 흐름이다.

## 숙련도와 추천 정책

정상 채점이 끝나면 대표 개념의 최근 완료 시도 최대 10개를 읽는다. `proficiency_level`은 정답률을 반올림한 0~100 정수다. 최소 3회 시도하고 숙련도가 50 이하일 때만 취약 개념이다. 상수는 `app/modules/learning/proficiency.py`에 모아 두었다.

- `GET /api/v1/learning/weak-concepts`: 취약 개념 목록
- `GET /api/v1/learning/recommendations?limit=10`: 추천 문제 목록

추천은 숙련도가 낮은 취약 개념과 쉬운 난이도를 우선하며 최근 문제 20개를 먼저 제외한다. 후보가 없으면 전체 개념으로 넓히고, 마지막 fallback에서만 최근 문제 제외를 푼다.

## 실행 계층

공통 서비스는 `RunnerDispatcher`에 문제를 넘긴다. 객관식은 서버 비교, `PYTHON/CODE`는 기존 `DockerSandbox`, `SQL/CODE`는 비활성 placeholder다. SQL runner를 활성화할 때는 별도 격리, 읽기 전용 DB 사용자·트랜잭션, statement timeout, DDL/DML 차단을 먼저 구현해야 한다. 현재 SQL 코드 제출은 안전하게 `SYSTEM_ERROR`로 종료된다.

## 로컬 적용

```powershell
python -m alembic upgrade head
python scripts/seed_learning_tasks.py
```

`--dry-run`은 결과를 롤백하고 `--cleanup-only`는 명시적인 벤치마크 표식 데이터만 정리한다.

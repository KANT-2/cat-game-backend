# 검증된 채점 체크리스트 (5-1~5-16)

최종 검증일: 2026-09-06

최초 기준 원본: `cat-game-backend-main.zip` (SHA-256 `EF85716C50F8F3E6BB06745EF2FDBC4458BCA908F7868DB614FE9B4695DDFFE4`)

최신 DB 통합 원본: `cat-game-backend-main (1).zip` (SHA-256 `FB5E0F4D9538DDD4996BB00BA9479AA80DF37AE6A91D81F054DF074077BFD248`)
판정 원칙: 코드 존재만으로 완료 처리하지 않고 관련 테스트 또는 실제 실행 근거가 있어야 `[x]`로 판정한다.

환경 메모: 로컬 단위 테스트와 Docker Compose의 PostgreSQL 16, FastAPI API, 전용 채점 워커,
실제 Docker 샌드박스 환경에서 검증했다.

## 항목별 재판정

- [x] **5-1 코드 제출 요청 스키마**
  - 근거: `app/schemas/task_attempt.py`
  - 테스트: `tests/unit/test_grading_schema.py`
  - 결과: `user_id`/추가 필드, 공백 코드, RANKING, 잘못된 context-public_id 조합 차단. 내부 ID 비노출.
  - TBD: 최대 코드 크기.

- [x] **5-2 TaskAttempt 생성 API**
  - 근거: `app/modules/grading/router.py`, `service.py`, `app/api/dependencies.py`
  - 구현: 활성 Task, DAILY 소유권/연결, BATTLE 참가/연결 검증과 rollback 경계.
  - 검증: 폐기 가능한 브라우저 세션과 개발용 명시적 사용자 헤더로 실제 PostgreSQL API 제출을 확인했다.

- [x] **5-3 PENDING 저장 및 202**
  - 근거: `create_attempt`, POST `/api/v1/attempts`.
  - 검증: API가 `202 PENDING`을 반환하고 워커가 같은 행을 완료 상태로 전이하는 통합 스모크를 통과했다.

- [x] **5-4 PostgreSQL 큐 기반 비동기 채점**
  - 근거: 제출 API는 `PENDING`만 커밋하고 별도 `app.modules.grading.worker` 프로세스가 채점을 수행한다.
  - 복구: `RUNNING` 행에는 불투명 임대 토큰과 시작 시각을 저장하며, 제한 시간을 넘긴 임대는 다른 워커가
    `FOR UPDATE SKIP LOCKED`로 회수한다. 이전 워커는 토큰이 바뀐 결과를 커밋할 수 없다.

- [x] **5-5 Docker Python 3.12 slim 이미지**
  - 근거: `infra/docker/grader/Dockerfile`; 백엔드 소스 미포함, uid 10001 `sandbox` 사용자.
  - 검증: `cat-game-python-grader:3.12` 이미지 실제 build 성공.

- [ ] **5-6 Docker Sandbox 보안**
  - 근거: `app/modules/grading/sandbox/runner.py`의 network none, read-only, tmpfs, memory/CPU/PID, cap-drop ALL, no-new-privileges, non-root, timeout/output/concurrency 제한.
  - 테스트: `tests/security/test_sandbox_options.py`에서 명령 옵션과 호스트 timeout 검증.
  - 검증: 제한 옵션을 적용한 실제 컨테이너에서 정답·오답·시간 초과 실행 성공.
  - 미완료: 네트워크 탈출, 쓰기 시도, OOM, PID 고갈과 동시성 공격 시나리오의 개별 검증. 제한 수치는 운영 정책 TBD이며 환경변수로 설정 가능.

- [x] **5-7 test_cases TEXT JSON 파싱/검증/비노출**
  - 근거: `app/modules/grading/test_cases.py`; API 응답 스키마에는 test_cases 없음.
  - 테스트: `tests/unit/test_test_cases.py`에서 정상/비정상 JSON, 빈 목록, 필드 누락/타입 오류 검증.
  - 현재 명세: `[{"input": "...", "expected_output": "..."}]`.

- [x] **5-8 Docker 테스트 케이스 실행**
  - 근거: 컨테이너 runner가 여러 케이스를 순차 실행하고 결과를 비교.
  - 테스트: `tests/integration/test_grader_runtime.py`에서 runner 자체는 실제 subprocess로 검증.
  - 검증: 실제 Docker 컨테이너에서 ACCEPTED와 WRONG_ANSWER 판정 확인.

- [x] **5-9 정답/오답 및 학생 오류 판정**
  - 근거: `infra/docker/grader/runner.py`, `GradeResult`.
  - 테스트: 정답, 오답, SyntaxError, RuntimeError를 실제 Python subprocess로 검증.
  - 결과: 학생 오류는 COMPLETED+false로 매핑되고 SYSTEM_ERROR만 FAILED+null로 분리.

- [ ] **5-10 무한 루프/비정상 코드**
  - 테스트: runner 내부 timeout과 호스트 Docker timeout 단위 테스트 통과.
  - 검증: 실제 Docker 컨테이너에서 무한 루프가 TIMEOUT으로 종료되는 것 확인.
  - 미완료: OOM, 과도 출력, Docker 비정상 종료 통합 검증 없음.
  - 정책: 탐지된 학생 timeout/output-limit은 현재 COMPLETED+false. 팀 최종 정책 TBD.

- [x] **5-11 결과 DB 저장**
  - 근거: PENDING→RUNNING→COMPLETED/FAILED 상태와 임대를 별도 워커 DB 세션에서 커밋한다.
    `result_detail`에는 verdict와 통과 개수만 저장하고 Docker 오류·stderr·테스트 명세 같은 내부 상세는
    사용자 응답에 넣지 않는다. PostgreSQL API·Docker 통합 스모크가 상태 전이를 검증한다.

- [ ] **5-12 DAILY 완료 연동**
  - 근거: DAILY 정답일 때만 `AttendanceTask.is_completed = true`; false로 되돌리는 경로 없음.
  - 미완료: DB 통합 테스트 미작성. 일일 보상은 의도적으로 채점기 범위 밖(TBD).

- [ ] **5-13 BATTLE 결과 연동**
  - 근거: Attempt에 검증된 `room_task_id`, `is_correct`, 상태, 결과 상세 저장.
  - 미완료: 배틀 서비스 소비 계약/통합 테스트 없음. 점수·보너스·감점 정책 TBD.

- [ ] **5-14 결과 조회 API**
  - 근거: GET `/api/v1/attempts/{public_id}`; 소유자 조건으로 조회하여 타 사용자도 404. 내부 ID/코드/test_cases 비노출.
  - 미완료: 인증+DB API 통합 테스트 미작성.

- [ ] **5-15 채점 기능 테스트**
  - 실행 결과: 로컬 `230 passed, 17 skipped`, PostgreSQL `247 passed`; Ruff 검사 통과.
  - 포함: 스키마/context, JSON 명세, 보안 옵션, 정답/오답/문법/런타임/timeout.
  - 추가 검증: PostgreSQL 마이그레이션과 만료 임대 회수, FastAPI API, 실제 Docker 정답 판정,
    브라우저 등록·세션·재연결·로그아웃 통합 흐름.
  - 미완료: DAILY/BATTLE, Docker 공격·OOM·출력·동시성 테스트.

- [ ] **5-16 문제 생성 측 test_cases 연동**
  - 구현된 소비 명세: `input`과 `expected_output` 문자열만 허용하며 추가 필드 차단.
  - 미완료/TBD: AI 생성 측 계약·기준 정답 자동 검증·사람 검수·검증 실패 시 게시 차단 정책.

## 실행 증거

```text
local pytest: 230 passed, 17 skipped
PostgreSQL pytest: 247 passed
ruff: All checks passed
docker build: cat-game-python-grader:3.12 성공
integration smoke: API 퀴즈와 Docker 코드 채점, 브라우저 세션 수명주기 확인
runtime boundary: API Docker 접근 없음, grading-worker만 Docker 접근 가능
```

Docker 보안 제한의 남은 공격 시나리오와 인증 포함 API 통합 테스트를 추가한 뒤 5-6, 5-10, 5-15를 다시 판정해야 한다.

```powershell
pytest -q
```

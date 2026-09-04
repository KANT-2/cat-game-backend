# Part 2 통합 계약

이 문서는 학습 문제, Python/SQL/객관식 채점, 숙련도, 추천, 일일 미션, 배틀 제출 흐름을 프런트엔드와 FastAPI 백엔드가 안전하게 통합하기 위한 계약을 정의한다.

현재 `feature/part2-learning` 구현을 기준으로 작성하며, DB 내부 식별자와 API 공개 식별자를 분리하고 모든 보호 API는 공통 `CurrentUser` 인증 의존성을 사용한다.

---

## 1. 공통 명명 및 식별자 규칙

- DB 내부 관계에는 `INTEGER` PK/FK를 사용한다.
- 외부 API에는 `public_id UUID`만 노출한다.
- 요청에서 문제를 지정할 때는 `task_public_id`를 사용한다.
- 일일 미션 연결은 `attendance_task_public_id`를 사용한다.
- 배틀 문제 연결은 `room_task_public_id`를 사용한다.
- 사용자 식별자는 요청 본문에서 직접 받지 않는다. 인증 결과로 결정된 `CurrentUser`를 사용한다.
- `task_id`, `user_id`, `concept_id`, `attendance_task_id`, `room_task_id` 같은 내부 정수 식별자는 API 응답 스키마에 포함하지 않는다.

```text
Frontend
   │ public UUID
   ▼
FastAPI / DTO
   │ public_id 조회
   ▼
SQLAlchemy ORM
   │ INTEGER PK/FK
   ▼
Database
```

---

## 2. 인증 계약

### 2.1 운영/통합 환경

통합 홈페이지는 Django DB Session을 사용하며 브라우저의 세션 쿠키를 게임 백엔드가 직접 해석하지 않는다.

게임 백엔드는 세션 쿠키를 홈페이지 Auth Bridge API로 전달하여 사용자를 확인한다.

```text
브라우저
  │ sessionid cookie
  ▼
FastAPI
  │ GET {AX_AUTH_BASE_URL}/{AX_AUTH_ME_PATH}
  │ Cookie: sessionid=...
  ▼
Django Auth Bridge
  │ id / display_name / role / optional email
  ▼
게임 User 조회 또는 생성
```

환경변수 기본값:

```text
AX_AUTH_ME_PATH=/api/auth/me/
AX_AUTH_SESSION_COOKIE_NAME=sessionid
AX_AUTH_TIMEOUT_SECONDS=3.0
```

게임 DB에는 홈페이지 사용자의 내부 ID를 `homepage_user_id`로 매핑한다.

- 최초 인증: 게임 `User` 자동 생성
- 이후 인증: `display_name`, `role`, 선택적 `email` 동기화
- 홈페이지 비밀번호, 세션키, 홈페이지 DB 자격증명은 게임 DB에 저장하지 않는다.

오류 계약:

| 상황 | HTTP 상태 |
| --- | --- |
| 세션 쿠키 없음 | `401 Unauthorized` |
| 홈페이지 Auth Bridge가 401/403 반환 | 동일한 `401` 또는 `403` |
| Auth Bridge URL 미설정 | `503 Service Unavailable` |
| Auth Bridge 네트워크/응답 계약 오류 | `503 Service Unavailable` |

### 2.2 로컬/테스트 환경

로컬과 테스트에서는 개발용 `X-User-Public-ID` 헤더를 사용할 수 있다.

```http
POST /api/v1/session/development
GET  /api/v1/session/me
```

운영 환경에서는 개발 사용자 생성 endpoint를 사용하지 않는다.

### 2.3 공통 HTTP 오류 계약

FastAPI 기본 오류 본문은 `{"detail": ...}` 형태를 사용한다. Pydantic 요청 검증 실패는 FastAPI 기본 `422 Unprocessable Entity` 응답을 사용한다.

| HTTP | Part 2에서의 의미 | 대표 상황 |
| --- | --- | --- |
| `401 Unauthorized` | 인증 정보가 없거나 개발 인증을 사용할 수 없음 | 세션 쿠키 없음, 운영 환경에서 개발 헤더 사용, 개발 사용자 없음 |
| `403 Forbidden` | 홈페이지 계정이 인증됐지만 사용이 허용되지 않음 | Django Auth Bridge가 `403` 반환 |
| `404 Not Found` | 공개 식별자로 제출/결과 리소스를 찾지 못했거나 현재 사용자에게 보이지 않음 | attempt 없음/타인 소유, 제출 대상 task·DAILY·BATTLE 연결 검증 실패 |
| `409 Conflict` | 현재 리소스 상태와 요청이 충돌함 | DAILY 미완료, 배틀 방 상태/인원/ready/start 조건 불충족 |
| `422 Unprocessable Entity` | 요청 DTO 자체가 계약을 위반함 | UUID/enum/길이/범위 오류, code·option 동시 제출, context 연결 UUID 조합 오류 |
| `503 Service Unavailable` | 외부 인증 또는 필수 서버 정책이 준비되지 않음 | Auth Bridge 미설정/장애, DAILY 보상 정책 미설정 |

현재 `POST /attempts`의 서비스 계층 `SubmissionError`는 모두 `404`로 매핑된다. 따라서 존재하는 문제에 대해 문제 유형과 제출 필드가 맞지 않거나 객관식 option이 허용값에 없을 때도 현재 구현은 `404`를 반환한다. 프런트엔드는 이 동작을 현재 계약으로 처리하되, 향후 `422`로 세분화하려면 API 계약 변경과 함께 수정한다.

배틀 서비스의 `BattleError`는 현재 모두 `409`로 매핑된다. 따라서 방 미존재/비참가자 조회와 `BATTLE_CORRECT_SCORE` 미설정도 현재 구현에서는 `409`다.

---

## 3. 학습 문제 공개 DTO 계약

문제 응답은 `TaskRead`를 사용한다.

```json
{
  "public_id": "task-uuid",
  "concept_public_id": "concept-uuid",
  "concept_name": "PYTHON:loops",
  "title": "문제 제목",
  "type": "CODE",
  "domain": "PYTHON",
  "difficulty": "SILVER",
  "description": "문제 설명",
  "template_code": "# 여기에 풀이를 작성하세요.",
  "options": null,
  "hint_text": null,
  "is_active": true,
  "completed": false
}
```

다음 값은 채점 전용이므로 문제 조회 응답에 노출하지 않는다.

```text
test_cases
correct_option
내부 INTEGER id / FK
```

문제 분류:

```text
type
├─ CODE
└─ MULTIPLE_CHOICE

domain
├─ PYTHON
└─ SQL

difficulty
├─ BRONZE
├─ SILVER
└─ GOLD
```

---

## 4. 문제 제출 API 계약

### 4.1 제출 생성

```http
POST /api/v1/attempts
Content-Type: application/json
```

CODE 문제:

```json
{
  "task_public_id": "93235fd9-5afc-42ec-8e19-4512e1173964",
  "submitted_code": "a, b = map(int, input().split())\nprint(a + b)",
  "context_type": "LEARNING",
  "used_hint": false
}
```

객관식:

```json
{
  "task_public_id": "task-uuid",
  "selected_option": "B",
  "context_type": "LEARNING",
  "used_hint": false
}
```

성공:

```http
202 Accepted
```

```json
{
  "public_id": "attempt-uuid",
  "status": "PENDING"
}
```

### 4.2 제출 입력 규칙

- `submitted_code`와 `selected_option` 중 정확히 하나만 전달한다.
- `CODE` 문제는 `submitted_code`를 요구한다.
- `MULTIPLE_CHOICE` 문제는 `selected_option`을 요구한다.
- 객관식 선택값은 반드시 `TASKS.options`에 존재해야 한다.
- 사용자 ID는 요청 본문에서 받지 않는다.

```text
LEARNING
├─ attendance_task_public_id = null
└─ room_task_public_id = null

DAILY
├─ attendance_task_public_id = required
└─ room_task_public_id = null

BATTLE
├─ attendance_task_public_id = null
└─ room_task_public_id = required
```

잘못된 조합은 `422`로 거부한다.

---

## 5. 채점 상태 전이 계약

제출 생성 후 채점은 FastAPI `BackgroundTasks`를 통해 실행한다.

```text
POST /attempts
     │
     ▼
PENDING
     │
     ▼
RUNNING
     │
     ├──────────── 정상 판정 ────────────┐
     │                                  │
     ▼                                  ▼
COMPLETED                         SYSTEM_ERROR
is_correct true/false                  │
                                      ▼
                                   FAILED
                              is_correct = null
```

학생 코드/쿼리의 오답, 문법 오류, 런타임 오류, 시간 초과, 출력 초과는 시스템 장애가 아니므로 정상적인 채점 결과로 취급한다.

시스템 자체 오류만 `FAILED` 상태로 저장한다.

---

## 6. 채점 결과 조회 API 계약

```http
GET /api/v1/attempts/{attempt_public_id}
```

응답 예시:

```json
{
  "public_id": "attempt-uuid",
  "task_public_id": "task-uuid",
  "context_type": "LEARNING",
  "status": "COMPLETED",
  "is_correct": true,
  "used_hint": false,
  "attempted_at": "2026-09-04T12:00:00Z",
  "result_detail": {
    "verdict": "ACCEPTED",
    "detail": null,
    "passed": 3,
    "total": 3
  }
}
```

- 인증 사용자 자신의 attempt만 조회할 수 있다.
- 다른 사용자의 attempt 또는 존재하지 않는 attempt는 `404`로 처리한다.
- `result_detail`은 API에서는 구조화된 JSON 객체로 반환한다. DB의 기존 JSON 문자열 저장 형식은 유지하며, 과거 `verdict`/`detail`만 저장된 데이터도 읽을 수 있다.

### 6.1 프론트엔드 polling 규칙

`POST /api/v1/attempts`는 채점 완료를 기다리지 않고 `202 Accepted`와 `PENDING`을 반환한다. 프론트엔드는 반환받은 `attempt_public_id`를 기준으로 결과 조회 API를 polling한다.

권장 흐름:

```text
POST /attempts
  -> 202 PENDING + attempt_public_id
  -> 1초 후 GET /attempts/{attempt_public_id}
       ├─ PENDING/RUNNING -> 다시 조회
       ├─ COMPLETED       -> polling 종료, 결과 표시
       └─ FAILED          -> polling 종료, 시스템 오류 표시
```

- 기본 polling 간격은 **1초**를 권장한다. 동일 attempt를 1초보다 짧은 간격으로 반복 조회하지 않는다.
- `PENDING`과 `RUNNING`은 진행 중 상태다. 두 상태에서는 `is_correct`나 최종 `result_detail`이 아직 확정되었다고 가정하지 않는다.
- `COMPLETED`와 `FAILED`는 terminal 상태다. 이 상태를 받으면 polling을 즉시 종료한다.
- 프론트엔드는 **30초 동안 terminal 상태를 받지 못하면 자동 polling을 중단**하고 "채점이 지연되고 있습니다"와 재조회 버튼을 표시하는 것을 권장한다. 이는 서버 채점을 취소하거나 attempt를 실패 처리한다는 뜻이 아니다.
- 자동 polling을 중단한 뒤에도 같은 `attempt_public_id`로 다시 `GET`하면 최종 결과를 복구할 수 있다. 새 attempt를 자동 생성하지 않는다.
- 페이지 새로고침/화면 이동을 고려해, 제출 직후 받은 `attempt_public_id`를 화면 상태 또는 클라이언트 저장소에 보존한다. 복귀 시 같은 ID로 결과 조회를 재개한다.
- polling 중 `401`/`403`은 인증 문제로 보고 중단한다. `404`는 잘못된/접근 불가 attempt로 보고 중단한다. 일시적 `503` 또는 네트워크 오류는 동일 attempt ID로 재시도할 수 있으며, 중복 제출을 만들지 않는다.
- 서버는 현재 FastAPI `BackgroundTasks` 기반이므로 위 30초는 **클라이언트 UX 기준**이지 채점 완료 SLA가 아니다. 큐 대기나 실행 환경에 따라 더 오래 걸릴 수 있다.
- 내부 `task_id`, `user_id`는 응답하지 않는다.

---

## 7. Runner Dispatcher 계약

```text
MULTIPLE_CHOICE
        ↓
MultipleChoiceRunner

CODE + PYTHON
        ↓
PythonSandboxRunner

CODE + SQL
        ↓
SQLSandboxRunner
```

객관식은 Docker를 실행하지 않고 서버가 `selected_option == correct_option`을 비교한다.

---

## 8. Python Sandbox 계약

Python CODE 문제는 전용 Docker 이미지에서 실행한다.

```text
network = none
filesystem = read-only
/tmp = tmpfs + noexec + nosuid
memory limit
CPU limit
PID limit
capabilities = drop ALL
no-new-privileges
non-root sandbox user
host timeout
output byte limit
bounded concurrency
```

주요 verdict:

```text
ACCEPTED
WRONG_ANSWER
SYNTAX_ERROR
RUNTIME_ERROR
TIMEOUT
OUTPUT_LIMIT
SYSTEM_ERROR
```

Python grader는 앱 서버 프로세스에서 사용자 코드를 직접 실행하지 않는다.

---

## 9. SQL Sandbox 계약

SQL CODE 문제는 Python grader와 분리된 `SQLSandboxRunner`를 사용한다.

각 테스트케이스마다 임시 schema를 생성하고, 문제의 seed SQL을 해당 schema에 구성한 후 제출 쿼리를 실행한다.

```text
Test Case
   │
   ├─ isolated schema 생성
   ├─ seed SQL 실행
   ├─ submission 실행
   ├─ 결과/검증 query 비교
   └─ schema DROP CASCADE
```

### 9.1 SQL 실행 모드

```text
QUERY
├─ SELECT
├─ TABLE
├─ VALUES
└─ WITH

MUTATION
├─ INSERT
├─ UPDATE
└─ DELETE

SCHEMA
├─ CREATE TABLE / INDEX / VIEW
├─ ALTER TABLE
└─ DROP TABLE / INDEX / VIEW
```

위험 동작은 별도 금지 목록으로 차단하고, 여러 SQL statement를 한 제출에 넣는 것도 허용하지 않는다.

### 9.2 QUERY 모드 보호

- `SET TRANSACTION READ ONLY`
- `statement_timeout`
- row count limit
- output byte limit
- 전용 grading DB URL

SQL 드라이버나 DSN 세부 정보는 사용자에게 그대로 노출하지 않는다.

### 9.3 테스트케이스 포맷

QUERY:

```json
[[1, "Alice"], [2, "Bob"]]
```

또는:

```json
{
  "mode": "QUERY",
  "reference_query": "SELECT id, name FROM users ORDER BY id"
}
```

MUTATION/SCHEMA:

```json
{
  "mode": "MUTATION",
  "verification_query": "SELECT name FROM users ORDER BY id",
  "expected_rows": [["Alice"], ["Bob"]]
}
```

---

## 10. 숙련도 갱신 계약

채점이 정상 종료되어 `is_correct` 값이 결정되면 해당 문제의 대표 `concept_id` 숙련도를 다시 계산한다.

```text
최근 COMPLETED attempt 최대 10개
        ↓
정답률 계산
        ↓
0 ~ 100 proficiency_level
```

- 한 문제는 현재 대표 `concept_id` 하나만 가진다.
- SILVER/GOLD 문제가 여러 개념을 함께 사용하더라도 현재 숙련도 반영은 대표 개념 하나에만 적용한다.
- 다중 개념 가중치(예: A 70%, B 30%)는 현재 구현 범위가 아니다.

취약 개념:

```text
최소 시도 3회 이상
AND
proficiency_level <= 50
```

---

## 11. 학습 조회·추천 API 계약

직접 문제 조회:

```http
GET /api/v1/learning/tasks?type=CODE&domain=PYTHON&difficulty=SILVER&limit=20
```

선택 필터는 `type`, `domain`, `concept_public_id`, `difficulty`, `limit(1~50)`이다. 조건에 맞는 활성 문제만 반환하고, 존재하지 않는 `concept_public_id`는 오류 대신 빈 목록 `[]`을 반환한다. 이미 정답 처리한 문제는 `completed=true`다. 잘못된 enum, UUID 형식, limit 범위는 `422`다.

추천/취약 개념 조회:

```http
GET /api/v1/learning/weak-concepts
GET /api/v1/learning/recommendations?limit=10
```

추천 우선순위:

1. 숙련도가 낮은 취약 개념 우선
2. 최근 20개 문제 우선 제외
3. 난이도 `BRONZE → SILVER → GOLD` 우선
4. 후보 부족 시 최근 문제 제외/취약 개념 조건을 순차 완화

추천 응답은 `TaskRead`를 사용하며 `test_cases`, `correct_option`은 노출하지 않는다.

---

## 12. 일일 미션 API 계약

### 12.1 오늘의 미션 조회

```http
GET /api/v1/daily/today
```

요청 본문은 없다. 인증된 사용자의 게임 타임존 기준 당일 `Attendance`를 조회하며, 없으면 생성하고 추천 알고리즘으로 문제를 배정한다.

성공 응답은 `200 OK`와 `DailyMissionRead`다.

```json
{
  "public_id": "attendance-uuid",
  "check_in_date": "2026-09-04",
  "streak_count": 3,
  "reward_claimed": false,
  "tasks": [
    {
      "attendance_task_public_id": "attendance-task-uuid",
      "task_order": 1,
      "is_completed": false,
      "task": {
        "public_id": "task-uuid",
        "concept_public_id": "concept-uuid",
        "concept_name": "PYTHON:loops",
        "title": "반복문 문제",
        "type": "CODE",
        "domain": "PYTHON",
        "difficulty": "BRONZE",
        "description": "문제 설명",
        "template_code": "",
        "options": null,
        "hint_text": null,
        "is_active": true,
        "completed": false
      }
    }
  ]
}
```

`tasks[].attendance_task_public_id`는 DAILY 제출 시 그대로 사용한다.

```json
{
  "task_public_id": "task-uuid",
  "submitted_code": "...",
  "context_type": "DAILY",
  "attendance_task_public_id": "attendance-task-uuid",
  "used_hint": false
}
```

정답으로 채점되면 대응하는 `ATTENDANCE_TASKS.is_completed = true`로 갱신한다.

현재 구현에서 오늘의 미션 생성 시 활성 문제 수가 설정된 일일 문제 수보다 부족하면 다음 응답을 반환한다.

| 상황 | HTTP | `detail` |
| --- | --- | --- |
| 배정 가능한 활성 문제가 부족함 | `409 Conflict` | `not enough active tasks to assign the daily mission` |

### 12.2 일일 보상 수령

```http
POST /api/v1/daily/{attendance_public_id}/reward
```

요청 본문은 없다. 해당 사용자의 일일 미션에 포함된 모든 `AttendanceTask`가 완료된 경우에만 보상을 지급한다.

성공 시 `200 OK`와 갱신된 `DailyMissionRead`를 반환한다. 보상을 이미 받은 상태에서 같은 API를 다시 호출하면 추가 지급 없이 동일한 성공 응답을 반환하므로, 현재 구현은 보상 중복 수령에 대해 멱등적으로 동작한다.

| 상황 | HTTP | `detail` |
| --- | --- | --- |
| 보상 정책값 미설정 | `503 Service Unavailable` | `daily reward policy is not configured` |
| 사용자의 일일 미션을 찾을 수 없음 | `409 Conflict` | `daily mission not found` |
| 아직 모든 문제가 완료되지 않음 | `409 Conflict` | `daily mission is not complete` |
| 이미 보상 수령 완료 | `200 OK` | 추가 보상 없이 현재 상태 반환 |

보상액 자체는 서버 정책값 `DAILY_REWARD_BALANCE`에서 결정되며 클라이언트가 금액을 전달하지 않는다.

---

## 13. 배틀 API 계약

배틀 방의 공개 상태 응답은 모든 배틀 endpoint에서 공통으로 `BattleRoomRead`를 사용한다.

```json
{
  "public_id": "room-uuid",
  "host_user_public_id": "host-user-uuid",
  "title": "알고리즘 대결",
  "status": "WAITING",
  "max_participants": 4,
  "participants": [
    {
      "user_public_id": "user-uuid",
      "username": "player1",
      "team_name": null,
      "current_score": 0,
      "is_ready": true
    }
  ],
  "tasks": [],
  "winner_user_public_ids": []
}
```

애플리케이션 흐름에서 방 상태는 `WAITING → RUNNING → FINISHED` 순으로 사용한다.

### 13.1 방 생성

```http
POST /api/v1/battle/rooms
```

```json
{
  "title": "알고리즘 대결",
  "max_participants": 4
}
```

입력 규칙:

- `title`: 1~100자
- `max_participants`: 2~20

성공은 `201 Created`다. 방을 만든 사용자는 host 참가자로 자동 등록되며 현재 구현에서는 `is_ready=true`로 시작한다.

Pydantic 입력 검증 실패는 `422 Unprocessable Entity`다.

### 13.2 방 조회

```http
GET /api/v1/battle/rooms/{room_public_id}
```

현재 로그인 사용자가 해당 방 참가자인 경우 `200 OK`와 `BattleRoomRead`를 반환한다.

| 상황 | HTTP | `detail` |
| --- | --- | --- |
| 방이 없거나 현재 사용자가 참가자가 아님 | `409 Conflict` | `room not found` |

현재 구현은 이 경우 `404`가 아니라 `409`를 반환한다. 프런트엔드는 실제 서버 계약에 맞춰 처리한다.

### 13.3 방 참가

```http
POST /api/v1/battle/rooms/{room_public_id}/join
```

```json
{
  "team_name": "blue"
}
```

`team_name`은 선택값이며 최대 50자다. 성공은 `200 OK`다. 이미 참가한 사용자가 다시 호출하면 중복 참가자를 추가하지 않고 현재 방 상태를 반환한다.

| 상황 | HTTP | `detail` |
| --- | --- | --- |
| 방이 없거나 WAITING 상태가 아님 | `409 Conflict` | `joinable room not found` |
| 최대 인원 도달 | `409 Conflict` | `room is full` |

### 13.4 준비 상태 변경

```http
PATCH /api/v1/battle/rooms/{room_public_id}/ready
```

```json
{
  "is_ready": true
}
```

성공은 `200 OK`다.

| 상황 | HTTP | `detail` |
| --- | --- | --- |
| WAITING 상태의 참가 정보를 찾을 수 없음 | `409 Conflict` | `waiting room participation not found` |

### 13.5 배틀 시작

```http
POST /api/v1/battle/rooms/{room_public_id}/start
```

```json
{
  "task_public_ids": [
    "task-uuid-1",
    "task-uuid-2",
    "task-uuid-3"
  ]
}
```

입력 스키마는 1~20개의 UUID를 허용하고, 서비스 계층에서 중복 UUID를 추가로 거부한다. 모든 참가자가 준비된 2명 이상의 WAITING 방에서 host만 시작할 수 있다. 지정한 문제는 모두 활성 상태여야 한다.

성공 시 `200 OK`와 `status="RUNNING"`인 `BattleRoomRead`를 반환하며 `tasks[]`에 `room_task_public_id`, `task_order`, 공개 `TaskRead`가 포함된다.

| 상황 | HTTP | `detail` |
| --- | --- | --- |
| 배틀 점수 정책값 미설정 | `409 Conflict` | `battle scoring policy is not configured` |
| 방이 없거나 host가 아니거나 WAITING 상태가 아님 | `409 Conflict` | `host waiting room not found` |
| 참가자 2명 미만 또는 준비하지 않은 참가자 존재 | `409 Conflict` | `at least two ready participants are required` |
| 빈 목록 또는 중복 문제 UUID | `409 Conflict` | `provide one or more unique task public IDs` |
| 지정한 UUID 중 활성 문제를 찾을 수 없음 | `409 Conflict` | `active battle task not found` |

`BATTLE_CORRECT_SCORE` 미설정도 현재 router 구현상 `409`로 매핑된다. 향후 정책 미설정을 `503`으로 통일하려면 API 계약 변경으로 별도 처리해야 한다.

### 13.6 배틀 답안 제출과 종료

배틀 답안도 공통 제출 endpoint를 사용한다.

```http
POST /api/v1/attempts
```

```json
{
  "task_public_id": "task-uuid",
  "submitted_code": "...",
  "context_type": "BATTLE",
  "room_task_public_id": "room-task-uuid",
  "used_hint": false
}
```

- 동일 사용자·동일 `RoomTask`의 최초 정답만 `BATTLE_CORRECT_SCORE`를 더한다.
- 이후 같은 문제를 다시 맞혀도 점수를 중복 지급하지 않는다.
- 모든 참가자가 모든 `RoomTask`에 대해 `COMPLETED` 제출을 남기면 방을 `FINISHED`로 전환한다.
- `FINISHED` 상태에서는 가장 높은 `current_score`를 가진 모든 참가자의 UUID를 `winner_user_public_ids`에 반환하므로 공동 우승이 가능하다.

현재 배틀 API에는 방 목록 검색, 초대, 매치메이킹 endpoint가 구현돼 있지 않다. 이 문서에는 실제 구현된 생성·조회·참가·준비·시작 흐름만 계약으로 고정한다.

---

## 14. Frontend ↔ Backend 빠른 참조

| 기능 | 메서드·경로 | Frontend → Backend | Backend → Frontend |
| --- | --- | --- | --- |
| 현재 사용자 | `GET /api/v1/session/me` | session cookie 또는 local header | 공개 사용자 DTO |
| 개발 사용자 준비 | `POST /api/v1/session/development` | 본문 없음 | 공개 사용자 DTO |
| 문제 조회 | `GET /api/v1/learning/tasks` | type/domain/concept/difficulty/limit | 공개 Task 목록 |
| 문제 추천 | `GET /api/v1/learning/recommendations` | `limit` | 공개 Task 목록 |
| 취약 개념 | `GET /api/v1/learning/weak-concepts` | 없음 | 개념 UUID·숙련도 |
| 문제 제출 | `POST /api/v1/attempts` | task UUID + code/option + context | attempt UUID + PENDING |
| 채점 결과 | `GET /api/v1/attempts/{attempt_public_id}` | attempt UUID | 상태·정오답·verdict |
| 오늘 미션 | `GET /api/v1/daily/today` | 인증 | Attendance + 문제 목록 |
| 일일 보상 | `POST /api/v1/daily/{attendance_public_id}/reward` | Attendance UUID | 갱신 상태 |
| 배틀 방 생성 | `POST /api/v1/battle/rooms` | title, max participants | 방 상태 |
| 배틀 참가 | `POST /api/v1/battle/rooms/{id}/join` | team name | 방 상태 |
| 배틀 준비 | `PATCH /api/v1/battle/rooms/{id}/ready` | is_ready | 방 상태 |
| 배틀 시작 | `POST /api/v1/battle/rooms/{id}/start` | task UUID 목록 | RUNNING 방 상태 |
| 배틀 조회 | `GET /api/v1/battle/rooms/{id}` | room UUID | 참가자·점수·문제·우승자 |

---

## 15. 통합 API 검증 시나리오

### Python CODE

- 정답 → `ACCEPTED`
- 오답 → `WRONG_ANSWER`
- 문법 오류 → `SYNTAX_ERROR`
- 무한 루프 → `TIMEOUT`
- 출력 제한 초과 → `OUTPUT_LIMIT`

### MULTIPLE_CHOICE

- 정답 option → `COMPLETED + true`
- 오답 option → `COMPLETED + false`
- options에 없는 option → 제출 거부
- Docker 실행 없이 처리

### SQL

- QUERY 정답 → `ACCEPTED`
- 결과 불일치 → `WRONG_ANSWER`
- SQL 문법 오류 → `SYNTAX_ERROR`
- statement timeout → `TIMEOUT`
- row/output limit 초과 → `OUTPUT_LIMIT`
- 금지 SQL → `RUNTIME_ERROR`
- multi-statement → 차단
- 테스트케이스 종료 후 임시 schema 제거
- DSN/driver 상세 오류 비노출

### 숙련도/추천

```text
문제 제출 완료
   ↓
USER_PROFICIENCY 재계산
   ↓
GET /learning/weak-concepts
   ↓
GET /learning/recommendations
```

### DAILY

```text
GET /daily/today
   ↓
Attendance + AttendanceTasks
   ↓
POST /attempts context=DAILY
   ↓
정답
   ↓
is_completed=true
   ↓
POST /daily/{attendance}/reward
```

### BATTLE

```text
방 생성
  ↓
2명 이상 참가/ready
  ↓
방장 start
  ↓
RoomTasks
  ↓
POST /attempts context=BATTLE
  ↓
최초 정답 점수
  ↓
전체 제출 완료
  ↓
FINISHED + winner UUID
```

### 실제 Django 로그인

```text
Django 로그인
   ↓
sessionid 발급
   ↓
브라우저가 게임 API 호출
   ↓
FastAPI → Auth Bridge /api/auth/me/
   ↓
homepage_user_id로 User 생성/조회
   ↓
Part 2 보호 API 정상 호출
```

실제 홈페이지 Auth Bridge 구현과 테스트 계정이 준비된 뒤 종단간 검증한다.

---

## 16. 통합 완료 체크리스트

- [x] 학습/채점 API에서 내부 정수 사용자 ID를 요청받지 않는다.
- [x] Task, Attempt, Concept, AttendanceTask, RoomTask는 공개 UUID로 API 경계를 통과한다.
- [x] 문제 응답에서 `test_cases`와 `correct_option`을 제외한다.
- [x] `POST /attempts`가 `PENDING` 저장 후 BackgroundTasks로 채점을 실행한다.
- [x] Python CODE가 격리 Docker grader로 분기된다.
- [x] SQL CODE가 별도 SQL sandbox로 분기된다.
- [x] 객관식은 서버에서 직접 비교한다.
- [x] 채점 완료 후 대표 concept 숙련도를 갱신한다.
- [x] 취약 개념 API와 추천 API가 공개 DTO를 사용한다.
- [x] DAILY가 오늘의 Attendance/문제를 자동 생성한다.
- [x] DAILY 정답이 AttendanceTask 완료 상태에 반영된다.
- [x] DAILY 보상이 완료 여부와 중복 수령을 검증한다.
- [x] BATTLE 방 생성/참가/ready/start API가 존재한다.
- [x] BATTLE 정답이 최초 정답 기준 점수에 반영된다.
- [x] BATTLE 전체 제출 완료 시 `FINISHED` 상태를 계산한다.
- [x] Django session Auth Bridge 수신부가 구현돼 있다.
- [x] `homepage_user_id` 기준 최초 User 생성 및 프로필 동기화 흐름이 구현돼 있다.
- [ ] Integration 환경 실제 Django `/api/auth/me/`와 로그인 → 게임 API 종단간 검증
- [ ] Production reverse proxy/cookie 전달 설정을 포함한 배포 환경 검증

---

## 17. 현재 구현상 주의사항

- 숙련도는 문제당 대표 `concept_id` 하나에만 반영한다. 다중 개념 가중치는 아직 사용하지 않는다.
- `daily_reward_balance`, `battle_correct_score` 같은 정책값은 환경/정책 확정 전 임의 하드코딩하지 않는다.
- SQL grading DB는 일반 애플리케이션 DB와 자격증명을 분리해 운영하는 것을 전제로 한다.
- SQL grading의 MUTATION/SCHEMA 모드는 문제 테스트 스펙에서 명시한 경우에만 사용한다.
- 실제 로그인 E2E는 홈페이지 팀의 최종 Auth Bridge 경로, 응답 필드, 쿠키 이름, Integration/Production 주소와 reverse proxy 설정 확정 후 완료한다.

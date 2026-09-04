# Part 2 API 통합 계약 검토

검토일: 2026-09-04  
검토 대상: `part2-integration-contract.md`  
대조 기준: 현재 FastAPI 라우터와 응답 스키마, 현재 ERD, 프런트엔드 PDR 사용자 시나리오

## 결론

현재 계약서는 백엔드 구현 설명서로는 잘 작성되어 있지만, 프런트엔드와 백엔드가 그대로 사용하여 연동을 완료할 수 있는 최종 API 계약서로는 아직 부족하다.

- 현재 구현된 인증, 추천, 채점, 일일 미션, 배틀 API 경로는 모두 기록되어 있다.
- 공개 UUID 사용과 내부 INTEGER ID 비노출 원칙이 명확하다.
- `TaskRead`, 문제 제출, 채점 결과의 기본 계약은 실제 구현과 대체로 일치한다.
- Python, SQL, 객관식 채점 분기와 샌드박스 정책은 충분히 설명되어 있다.
- 반면 조건별 문제 직접 선택, 일반 학습 보상, DAILY/BATTLE의 정확한 DTO, 오류 응답과 비동기 폴링 규칙은 보완이 필요하다.

따라서 현재 문서를 Part 2 최종 통합 계약으로 확정하기 전에 아래 필수 항목을 먼저 결정해야 한다.

## 보완 항목 요약

| 중요도 | 항목 | 현재 상태 |
| --- | --- | --- |
| 높음 | 조건별 문제 직접 선택 API | 제품 시나리오에는 있지만 API가 없다. |
| 높음 | 일반 학습 문제 재화 보상 | 계약, 구현, 데이터 모델이 부족하다. |
| 높음 | DAILY/BATTLE 요청·응답 DTO | 일부 제출 예시만 있고 전체 필드 계약이 없다. |
| 높음 | API별 오류 응답 | 실제 상태 코드와 문서의 구분이 불명확하다. |
| 중간 | 비동기 채점 폴링 | 간격, 제한 시간, 실패 및 복구 방식이 없다. |
| 중간 | 현재 사용자 응답 DTO | 실제 공개 필드가 계약서에 명시되지 않았다. |
| 중간 | ERD의 `homepage_user_id` | 실제 모델에는 있지만 현재 ERD에는 없다. |
| 중간 | 단계적 힌트와 함수 작성형 문제 | 제품 시나리오보다 현재 DTO가 단순하다. |
| 중간 | 배틀방 발견 또는 초대 방식 | 참가자가 `room_public_id`를 얻는 흐름이 없다. |

## 충분히 작성된 부분

### 공개 식별자와 소유권

- API 경계에서는 `public_id`와 `*_public_id`를 사용한다.
- `task_id`, `user_id`, `attendance_task_id`, `room_task_id` 같은 내부 INTEGER 식별자를 응답하지 않는다.
- 사용자 식별자를 요청 본문에서 받지 않고 인증된 `CurrentUser`를 사용한다.
- 다른 사용자의 attempt는 존재 여부를 구분하지 않고 `404`로 처리한다.

### 문제와 채점

- `TaskRead` 공개 필드가 실제 응답 스키마와 일치한다.
- `test_cases`와 `correct_option`을 공개하지 않는 원칙이 명확하다.
- `submitted_code`와 `selected_option` 중 하나만 보내는 규칙이 명시되어 있다.
- `LEARNING`, `DAILY`, `BATTLE`별 연결 UUID 조합이 ERD 관계와 일치한다.
- `PENDING → RUNNING → COMPLETED/FAILED` 상태 흐름과 runner 분기가 설명되어 있다.

### DAILY와 BATTLE의 핵심 업무 규칙

- DAILY 정답이 `ATTENDANCE_TASKS.is_completed`에 반영되는 흐름이 적혀 있다.
- 전체 일일 문제 완료 후 한 번만 보상하는 규칙이 있다.
- BATTLE의 최초 정답 점수 반영과 전체 제출 완료 후 `FINISHED` 전환 규칙이 있다.

## 필수 보완 사항

### 1. 조건별 문제 직접 선택 API

PDR에서는 사용자가 추천 문제뿐 아니라 과제 유형, 개념, 난이도를 직접 선택할 수 있어야 한다. 현재 구현과 계약에는 다음 추천 API만 있다.

```http
GET /api/v1/learning/recommendations?limit=10
```

현재 API는 `limit`만 지원하므로 직접 선택 시나리오를 충족하지 못한다. 별도 조회 API를 추가하거나 추천 API에 필터를 추가해야 한다.

계약 예시:

```http
GET /api/v1/learning/tasks
    ?type=CODE
    &domain=PYTHON
    &concept_public_id={concept_public_id}
    &difficulty=BRONZE
    &limit=20
    &cursor={cursor}
```

확정할 내용:

- `type`, `domain`, `concept_public_id`, `difficulty`의 선택 및 조합 규칙
- 기본 정렬과 페이지네이션
- 활성 문제만 반환할지 여부
- 이미 완료한 문제를 포함할지 여부
- 결과가 없을 때 빈 배열을 반환할지 여부

### 2. 일반 학습 문제 재화 보상

PDR에는 최초 완료와 정답에 따라 재화를 지급하고, 반복 풀이로 무한 보상을 얻지 못하게 하는 규칙이 있다. 현재 채점 서비스는 숙련도, DAILY 완료, BATTLE 점수만 갱신하며 일반 `LEARNING` 정답에 대한 `USERS.balance` 변경은 수행하지 않는다.

계약과 구현에서 다음을 결정해야 한다.

- 최초 완료 기본 보상
- 정답 또는 테스트 통과 추가 보상
- 힌트 사용 시 보상 계산
- 이미 보상받은 문제를 다시 제출했을 때의 처리
- attempt 완료와 잔액 변경의 단일 트랜잭션 처리
- 프런트엔드에 `reward_amount`, `balance_after`, `first_completion`을 반환할지 여부
- 지급 이력을 별도 테이블로 저장할지, `TASK_ATTEMPTS`로 판정할지 여부

현재 ERD에는 `USERS.balance`만 있고 학습 보상 지급 이력이나 지급 금액 필드가 없다. 반복 지급 방지와 운영 감사까지 고려하여 데이터 모델을 확정해야 한다.

### 3. DAILY 전체 응답 계약

`GET /api/v1/daily/today`와 `POST /api/v1/daily/{attendance_public_id}/reward`는 실제로 동일한 `DailyMissionRead` 구조를 반환한다. 계약서에 아래와 같은 전체 예시가 필요하다.

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
        "title": "문제 제목",
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

추가로 명시할 내용:

- 게임 날짜는 `GAME_TIMEZONE` 기준이라는 점
- 같은 날짜에 다시 조회하면 기존 Attendance를 반환한다는 점
- 보상 중복 호출은 추가 지급 없이 `200`과 현재 상태를 반환한다는 점
- 활성 문제 부족은 `409`, 보상 정책 미설정은 `503`이라는 점

### 4. BATTLE 전체 요청·응답 계약

각 API의 요청 본문을 명시해야 한다.

```json
// POST /api/v1/battle/rooms
{
  "title": "반복문 연습방",
  "max_participants": 4
}
```

```json
// POST /api/v1/battle/rooms/{room_public_id}/join
{
  "team_name": "고양이 팀"
}
```

```json
// PATCH /api/v1/battle/rooms/{room_public_id}/ready
{
  "is_ready": true
}
```

```json
// POST /api/v1/battle/rooms/{room_public_id}/start
{
  "task_public_ids": ["task-uuid-1", "task-uuid-2"]
}
```

모든 배틀 API는 다음 형태의 `BattleRoomRead` 전체 응답을 반환한다.

```json
{
  "public_id": "room-uuid",
  "host_user_public_id": "user-uuid",
  "title": "반복문 연습방",
  "status": "WAITING",
  "max_participants": 4,
  "participants": [
    {
      "user_public_id": "user-uuid",
      "username": "플레이어",
      "team_name": null,
      "current_score": 0,
      "is_ready": true
    }
  ],
  "tasks": [
    {
      "room_task_public_id": "room-task-uuid",
      "task_order": 1,
      "task": {}
    }
  ],
  "winner_user_public_ids": []
}
```

추가로 확정할 내용:

- 방 상태 값은 `WAITING`, `RUNNING`, `FINISHED`다.
- 방 생성자는 자동 참가하고 준비 상태가 `true`다.
- 시작은 방장만 가능하며 최소 2명 모두 준비해야 한다.
- 방 생성은 `201`, 나머지 성공 응답은 `200`이다.
- 참가, 준비, 시작, 조회의 도메인 오류는 현재 모두 `409`다.
- 다른 사용자가 참가할 방의 `room_public_id`를 얻는 초대 또는 방 목록 흐름이 필요하다.

### 5. 오류 응답 행렬

계약서의 “잘못된 조합은 `422`”라는 설명만으로는 실제 동작을 구분하기 어렵다.

#### 문제 제출

| 상황 | 현재 HTTP 상태 |
| --- | --- |
| 요청 필드 누락 또는 타입 오류 | `422` |
| 잘못된 UUID 형식 | `422` |
| code와 option을 둘 다 전달하거나 모두 생략 | `422` |
| context와 연결 UUID 조합 오류 | `422` |
| 문제 없음 또는 비활성 문제 | `404` |
| 문제 유형과 답안 유형 불일치 | `404` |
| 객관식 보기에 없는 선택값 | `404` |
| 소유하지 않은 DAILY 연결 | `404` |
| 참가하지 않은 BATTLE 연결 | `404` |

#### DAILY

| 상황 | 현재 HTTP 상태 |
| --- | --- |
| 활성 문제 부족 | `409` |
| 미션 없음 또는 다른 사용자 미션 | `409` |
| 일일 문제 미완료 | `409` |
| 보상 정책 미설정 | `503` |

#### BATTLE

방 없음, 비참가자 조회, 정원 초과, 준비 조건 미충족, 방장 권한 없음, 잘못된 문제 지정 등 현재 `BattleError`는 모두 `409`로 변환된다. 최종 계약에서도 이를 유지할지, 존재하지 않거나 접근할 수 없는 방을 `404`로 분리할지 결정해야 한다.

공통 오류 본문도 아래 형태로 명시해야 한다.

```json
{
  "detail": "error message"
}
```

### 6. 비동기 채점 폴링 규칙

`POST /attempts`는 `202 PENDING`을 반환하고 프런트엔드는 결과 API를 반복 조회한다. 다음 항목이 계약에 필요하다.

- 권장 최초 조회 시점과 폴링 간격
- 지수 백오프 사용 여부
- 최대 대기 시간
- `PENDING` 또는 `RUNNING`이 장시간 유지될 때의 UI 처리
- 네트워크 오류 시 재조회 가능 여부
- 서버 재시작 등으로 채점 작업이 유실됐을 때의 복구 정책
- `FAILED` 상태에서 재제출할 때 새 attempt를 생성하는지 여부

### 7. 현재 사용자 DTO와 `homepage_user_id`

현재 `GET /api/v1/session/me`의 실제 응답 필드는 다음과 같다.

```json
{
  "public_id": "user-uuid",
  "homepage_user_id": 123,
  "email": "player@example.com",
  "username": "플레이어",
  "role": "STUDENT",
  "balance": 1000,
  "mileage": 0,
  "house_level": 1,
  "created_at": "2026-09-04T12:00:00Z"
}
```

인증 계약에는 `homepage_user_id` 연결이 설명되어 있지만 현재 ERD의 `USERS` 필드에는 빠져 있다. 실제 모델과 일치하도록 ERD에 다음 필드를 추가해야 한다.

```text
homepage_user_id BIGINT UNIQUE nullable
```

또한 `homepage_user_id`는 홈페이지 시스템의 내부 식별자이므로 프런트엔드에서 필요하지 않다면 `UserRead`에서 제외하는 편이 공개 UUID 원칙에 더 잘 맞는다.

### 8. 문제 표현과 힌트

PDR은 고정된 함수의 본문 작성, 예시 입출력, 짧은 설명, 단계적 힌트를 요구한다. 현재 공개 DTO에는 `template_code`와 단일 `hint_text`만 있다.

다음 중 하나를 선택해야 한다.

- 현재 단일 힌트와 자유 코드 제출을 MVP 범위로 명시한다.
- 함수 서명, 예시 입출력, 단계별 힌트 배열을 공개 DTO에 추가한다.

`result_detail`은 현재 JSON 객체가 아니라 JSON 문자열이다. 프런트엔드가 문자열을 다시 파싱해야 하는 현재 계약을 유지할지, 구조화된 응답 객체로 변경할지도 확정하는 것이 좋다.

## ERD 대조 결과

### 일치하는 관계

- `TASKS → TASK_ATTEMPTS`
- `ATTENDANCES → ATTENDANCE_TASKS → TASK_ATTEMPTS`
- `ROOMS → ROOM_TASKS → TASK_ATTEMPTS`
- `ROOMS → ROOM_PARTICIPANTS`
- `CONCEPTS → TASKS → USER_PROFICIENCY`

위 관계는 API에서 사용하는 `task_public_id`, `attendance_task_public_id`, `room_task_public_id`와 자연스럽게 대응한다.

### 보완할 ERD 내용

- `USERS.homepage_user_id`를 추가한다.
- `ROOMS.status`의 허용 값을 `WAITING`, `RUNNING`, `FINISHED`로 명시한다.
- `TASK_ATTEMPTS.context_type`의 허용 값과 연결 FK 조합 제약을 주요 제약에 기록한다.
- 일반 학습 재화 지급을 구현한다면 지급 이력 또는 중복 지급 방지 기준을 ERD에 반영한다.
- `ATTENDANCES(user_id, check_in_date)`, `ROOM_PARTICIPANTS(room_id, user_id)` 등 시나리오의 중복 방지를 담당하는 UNIQUE 제약을 문서에 명시한다.

## 최종 확정 전 체크리스트

- [ ] 조건별 문제 직접 선택 API를 확정한다.
- [ ] 일반 학습 보상 정책과 중복 지급 방지를 확정한다.
- [ ] 현재 사용자 DTO의 전체 필드를 기록한다.
- [ ] DAILY 요청·응답·오류 예시를 기록한다.
- [ ] BATTLE 요청·응답·오류 예시를 기록한다.
- [ ] 비동기 채점 폴링과 복구 규칙을 기록한다.
- [ ] `homepage_user_id`의 ERD 반영과 API 노출 여부를 결정한다.
- [ ] 함수 작성형 문제와 단계적 힌트의 MVP 범위를 결정한다.
- [ ] 배틀방 발견 또는 초대 흐름을 결정한다.
- [ ] 실제 Django 로그인과 BackgroundTasks를 포함한 종단간 검증을 수행한다.

## 최종 판단

현재 문서는 채점 엔진과 보안 원칙을 이해하기에는 충분하고, 현재 구현된 API 경로도 빠짐없이 포함한다. 그러나 전체 사용자 시나리오와 프런트엔드 구현을 보장하는 최종 통합 계약으로 사용하려면 아래 네 항목을 우선 보완해야 한다.

1. 조건별 문제 직접 선택 API
2. 일반 학습 재화 보상과 중복 지급 방지
3. DAILY/BATTLE 전체 요청·응답·오류 계약
4. `homepage_user_id`의 ERD 반영 및 API 노출 여부


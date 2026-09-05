# Part 2·Part 3 통합 API 계약

이 문서는 현재 FastAPI 코드에 등록된 Part 2와 Part 3 API를 프런트엔드 관점에서 한곳에 모은 통합 진입점이다. 상세한 업무 규칙은 하단의 기능별 계약 문서를 따르며, 실행 중인 서버의 요청 필드·타입 최종 기준은 `/docs` OpenAPI다.

## 1. 공통 계약

- API 기본 prefix: `/api/v1`
- 상태 확인만 예외적으로 `/health`를 사용한다.
- JSON 요청은 `Content-Type: application/json`을 사용한다.
- 외부 식별자는 UUID `public_id`와 `*_public_id`만 사용한다.
- 내부 INTEGER `id`와 `*_id`는 요청·응답에 노출하지 않는다.
- 보호 API의 사용자 정보는 요청 본문이 아니라 `CurrentUser` 인증 결과로 결정한다.
- `204 No Content` 응답은 JSON 본문이 없다.
- FastAPI 오류 본문은 기본적으로 `{"detail": ...}` 형태다.
- Pydantic 경로·쿼리·본문 검증 실패는 `422`와 `detail` 배열을 반환한다.

### 인증

| 환경 | Frontend → Backend |
| --- | --- |
| `local`, `test` | `X-User-Public-ID: <user public UUID>` |
| integration, production | 브라우저 `sessionid` 쿠키를 Django Auth Bridge로 검증 |

로컬 프런트엔드는 `POST /api/v1/session/development`로 개발 사용자를 준비하고, 반환된 `public_id`를 보호 API의 `X-User-Public-ID`에 사용한다. 운영 환경에서는 개발 세션 API와 UUID 헤더 인증을 사용하지 않는다.

### 공통 상태 코드

| HTTP | 의미 |
| --- | --- |
| `200` | 조회·수정·멱등 재시도 성공 |
| `201` | 구매·기억·배치 객체 생성 성공 |
| `202` | 제출 접수 성공, 비동기 채점 진행 |
| `204` | 삭제 성공, 응답 본문 없음 |
| `401` | 인증 정보 없음 또는 유효하지 않음 |
| `403` | 호스트 인증 공급자가 접근 거부 |
| `404` | 리소스 없음, 타인 소유 리소스 또는 현재 제출 서비스 검증 실패 |
| `409` | 상태 충돌, 잔액 부족, 멱등 키 충돌 또는 배치 수량 초과 |
| `422` | UUID·enum·범위·요청 DTO 또는 도메인 입력 오류 |
| `503` | Auth Bridge·Gemini 장애, AI 키·가챠·일일 보상 정책 미설정 또는 Gemini 무료 할당량 초과 |

## 2. 전체 Endpoint 목록

### 공통·인증

| Method | Path | 인증 | 성공 | 용도 |
| --- | --- | --- | --- | --- |
| `GET` | `/health` | 없음 | `200` | 서버 상태 확인 |
| `POST` | `/api/v1/session/development` | 없음 | `200` | 로컬·테스트 개발 사용자 생성 또는 재사용 |
| `GET` | `/api/v1/session/me` | 필요 | `200` | 현재 사용자 공개 프로필 |

### Part 2 — 학습·채점·일일 미션·배틀

| Method | Path | 성공 | 용도 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/learning/tasks` | `200` | 조건별 활성 문제 조회 |
| `GET` | `/api/v1/learning/recommendations` | `200` | 취약 개념 우선 추천 문제 조회 |
| `GET` | `/api/v1/learning/weak-concepts` | `200` | 현재 사용자의 취약 개념 조회 |
| `POST` | `/api/v1/attempts` | `202` | 코드 또는 객관식 답안 제출 |
| `GET` | `/api/v1/attempts/{attempt_public_id}` | `200` | 채점 상태·결과 조회 |
| `GET` | `/api/v1/daily/today` | `200` | 오늘 출석과 일일 문제 조회·생성 |
| `POST` | `/api/v1/daily/{attendance_public_id}/reward` | `200` | 일일 미션 보상 1회 수령 |
| `POST` | `/api/v1/battle/rooms` | `201` | 배틀 방 생성 |
| `GET` | `/api/v1/battle/rooms/{room_public_id}` | `200` | 배틀 방 상태 조회 |
| `POST` | `/api/v1/battle/rooms/{room_public_id}/join` | `200` | 배틀 방 참가 |
| `PATCH` | `/api/v1/battle/rooms/{room_public_id}/ready` | `200` | 참가자 준비 상태 변경 |
| `POST` | `/api/v1/battle/rooms/{room_public_id}/start` | `200` | 호스트가 문제를 확정하고 배틀 시작 |

### Part 3 — 구매·가챠·하우징·고양이·생성형 AI

| Method | Path | 성공 | 용도 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/shop/purchases` | `201` | 아이템 멱등 구매 |
| `POST` | `/api/v1/gacha/draws` | `200` | 고양이 1회 또는 10+1회 멱등 가챠 |
| `PUT` | `/api/v1/housing/surfaces/{item_public_id}` | `200` | 보유 벽지·바닥 적용 |
| `POST` | `/api/v1/housing/placed-objects` | `201` | 보유 가구 배치 |
| `PATCH` | `/api/v1/housing/placed-objects/{placed_object_public_id}` | `200` | 배치 가구 좌표 수정 |
| `DELETE` | `/api/v1/housing/placed-objects/{placed_object_public_id}` | `204` | 가구 배치 해제 |
| `GET` | `/api/v1/cats/collection` | `200` | 전체 고양이 도감과 보유 상태 조회 |
| `GET` | `/api/v1/cats/{cat_asset_public_id}/conversation-context` | `200` | 고양이 persona와 기억 전체 조회 |
| `POST` | `/api/v1/cats/{cat_asset_public_id}/chat` | `200` | persona·기억 기반 Gemini 대화 |
| `POST` | `/api/v1/cats/{cat_asset_public_id}/memories` | `201` | 고양이 기억 추가 |
| `DELETE` | `/api/v1/cats/{cat_asset_public_id}/memories/{memory_public_id}` | `204` | 기억 선택 삭제 |
| `DELETE` | `/api/v1/cats/{cat_asset_public_id}/memories` | `204` | 해당 고양이 기억 전체 삭제 |

위 표에서 `/health`와 개발 사용자 준비를 제외한 기능 API는 모두 인증이 필요하다.

## 3. 공통·인증 API

### `GET /health`

응답 `200`:

```json
{"status": "ok"}
```

### `POST /api/v1/session/development`

요청 본문은 없다. `local`·`test`에서만 사용할 수 있으며 운영에서는 `404`다.

### `GET /api/v1/session/me`

개발 사용자 준비와 현재 사용자 조회는 같은 공개 프로필을 반환한다.

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

## 4. Part 2 API

### 4.1 문제 조회

#### `GET /api/v1/learning/tasks`

지원 query:

| 이름 | 타입·허용값 | 기본값 |
| --- | --- | --- |
| `type` | `CODE`, `MULTIPLE_CHOICE` | 전체 |
| `domain` | `PYTHON`, `SQL` | 전체 |
| `concept_public_id` | UUID | 전체 |
| `difficulty` | `BRONZE`, `SILVER`, `GOLD` | 전체 |
| `limit` | `1..50` | `20` |

개념 UUID가 존재하지 않으면 `404`가 아니라 빈 배열을 반환한다.

#### `GET /api/v1/learning/recommendations`

`limit=1..50`, 기본값 `10`을 지원한다. 취약 개념을 우선하고 부족한 수는 아직 정답 처리하지 않은 활성 문제로 채운다.

두 API는 `TaskRead[]`를 반환한다.

```json
[
  {
    "public_id": "93235fd9-5afc-42ec-8e19-4512e1173964",
    "concept_public_id": "0ccdf2d3-53df-4a11-a265-9eaf252280cc",
    "concept_name": "PYTHON:loops",
    "title": "반복문 문제",
    "type": "CODE",
    "domain": "PYTHON",
    "difficulty": "BRONZE",
    "description": "문제 설명",
    "template_code": "# 여기에 풀이를 작성하세요.",
    "options": null,
    "hint_text": null,
    "is_active": true,
    "completed": false
  }
]
```

`test_cases`와 `correct_option`은 채점 전용이므로 응답하지 않는다.

#### `GET /api/v1/learning/weak-concepts`

```json
[
  {
    "concept_public_id": "0ccdf2d3-53df-4a11-a265-9eaf252280cc",
    "proficiency_level": 40,
    "name": "PYTHON:loops",
    "attempts": 5
  }
]
```

취약 개념은 최근 완료 시도 기준 최소 3회이면서 숙련도 50 이하인 개념이다.

### 4.2 답안 제출과 polling

#### `POST /api/v1/attempts`

CODE 문제 요청:

```json
{
  "task_public_id": "93235fd9-5afc-42ec-8e19-4512e1173964",
  "submitted_code": "print('hello')",
  "context_type": "LEARNING",
  "used_hint": false
}
```

객관식 요청:

```json
{
  "task_public_id": "93235fd9-5afc-42ec-8e19-4512e1173964",
  "selected_option": "B",
  "context_type": "LEARNING",
  "used_hint": false
}
```

문맥별 공개 연결 UUID 조합:

| `context_type` | `attendance_task_public_id` | `room_task_public_id` |
| --- | --- | --- |
| `LEARNING` | 보내지 않음 | 보내지 않음 |
| `DAILY` | 필수 | 보내지 않음 |
| `BATTLE` | 보내지 않음 | 필수 |

`submitted_code`와 `selected_option` 중 정확히 하나만 보낸다. 알 수 없는 필드는 거부한다.

응답 `202`:

```json
{
  "public_id": "91969ce0-6a6b-4a5a-9fdd-acde8dedf79f",
  "status": "PENDING"
}
```

#### `GET /api/v1/attempts/{attempt_public_id}`

```json
{
  "public_id": "91969ce0-6a6b-4a5a-9fdd-acde8dedf79f",
  "task_public_id": "93235fd9-5afc-42ec-8e19-4512e1173964",
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

프런트엔드는 제출 후 같은 `public_id`로 1초 간격 polling한다. `PENDING`·`RUNNING`이면 계속 조회하고 `COMPLETED`·`FAILED`면 종료한다. 30초가 지나면 자동 polling만 중단하고 동일 UUID로 수동 재조회한다. 새 제출을 자동 생성하지 않는다.

현재 제출 서비스의 문제·제출 필드·DAILY/BATTLE 연결 검증 오류는 모두 `404`로 매핑된다. DTO 조합 자체의 오류는 `422`다.

### 4.3 일일 미션

#### `GET /api/v1/daily/today`

요청 본문은 없다. 오늘 출석이 없으면 만들고 문제를 자동 배정하며, 있으면 같은 출석을 반환한다.

#### `POST /api/v1/daily/{attendance_public_id}/reward`

요청 본문은 없다. 모든 문제가 완료된 뒤 한 번만 보상을 지급한다. 재호출은 추가 지급 없이 현재 상태를 반환한다. 미완료 등 상태 충돌은 `409`, `DAILY_REWARD_BALANCE` 미설정은 `503`이다.

두 API는 `DailyMissionRead`를 반환한다.

```json
{
  "public_id": "a7457524-4034-49e8-8510-40052d53d44c",
  "check_in_date": "2026-09-04",
  "streak_count": 3,
  "reward_claimed": false,
  "tasks": [
    {
      "attendance_task_public_id": "479ecbe8-90f1-4133-b020-f017d6982697",
      "task_order": 1,
      "is_completed": false,
      "task": {
        "public_id": "93235fd9-5afc-42ec-8e19-4512e1173964",
        "concept_public_id": "0ccdf2d3-53df-4a11-a265-9eaf252280cc",
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

### 4.4 배틀

#### 방 생성

`POST /api/v1/battle/rooms`

```json
{"title": "초급 배틀", "max_participants": 2}
```

`title`은 1~100자, `max_participants`는 2~20이다.

#### 방 참가

`POST /api/v1/battle/rooms/{room_public_id}/join`

```json
{"team_name": "파랑팀"}
```

`team_name`은 선택이며 최대 50자다.

#### 준비 상태

`PATCH /api/v1/battle/rooms/{room_public_id}/ready`

```json
{"is_ready": true}
```

#### 배틀 시작

`POST /api/v1/battle/rooms/{room_public_id}/start`

```json
{
  "task_public_ids": ["93235fd9-5afc-42ec-8e19-4512e1173964"]
}
```

문제 UUID는 1~20개다. 호스트만 시작할 수 있다.

#### 방 조회와 공통 응답

`GET /api/v1/battle/rooms/{room_public_id}`를 포함한 모든 배틀 API는 `BattleRoomRead`를 반환한다.

```json
{
  "public_id": "5ecffb83-1404-46e7-82b2-f91fc351385e",
  "host_user_public_id": "8a4a9c2f-645f-4b94-9b5d-16bc7d563f42",
  "title": "초급 배틀",
  "status": "WAITING",
  "max_participants": 2,
  "participants": [
    {
      "user_public_id": "8a4a9c2f-645f-4b94-9b5d-16bc7d563f42",
      "username": "{ 냥 } 플레이어",
      "team_name": null,
      "current_score": 0,
      "is_ready": false
    }
  ],
  "tasks": [],
  "winner_user_public_ids": []
}
```

배틀 답안은 별도 endpoint가 아니라 `POST /api/v1/attempts`에 `context_type=BATTLE`과 `room_task_public_id`를 넣어 제출한다. 현재 모든 `BattleError`는 `409`이며 방 미존재·비참가자·`BATTLE_CORRECT_SCORE` 미설정도 여기에 포함된다.

## 5. Part 3 API

### 5.1 아이템 구매

`POST /api/v1/shop/purchases`

```json
{
  "request_id": "01a996ae-c8f5-4388-bf1e-a911717fa2bd",
  "item_public_id": "ee50a4a7-f05d-44b2-ac84-9b0276eeedfe",
  "quantity": 2
}
```

응답 `201`:

```json
{
  "execution_public_id": "a17169ab-d732-4e42-a717-36733f6f9e59",
  "request_id": "01a996ae-c8f5-4388-bf1e-a911717fa2bd",
  "item_public_id": "ee50a4a7-f05d-44b2-ac84-9b0276eeedfe",
  "purchased_quantity": 2,
  "total_quantity": 5,
  "balance": 700
}
```

`quantity`는 양수다. 같은 동작의 네트워크 재시도에는 같은 `request_id`를 사용한다. 동일 사용자·동일 내용이면 최초 결과를 반환하고 사용자 또는 내용이 다르면 `409`다. 아이템 없음은 `404`, 잔액 부족은 `409`다.

### 5.2 고양이 가챠

`POST /api/v1/gacha/draws`

```json
{
  "request_id": "01a996ae-c8f5-4388-bf1e-a911717fa2bd",
  "draw_count": 11
}
```

`draw_count`는 `1` 또는 `11`만 허용한다. `11`은 10회 비용으로 11개 결과를 반환하는 10+1회 뽑기다.

```json
{
  "execution_public_id": "3cded9b5-2655-471e-90c8-3a63a9c43018",
  "request_id": "01a996ae-c8f5-4388-bf1e-a911717fa2bd",
  "draw_count": 11,
  "bonus_draw_count": 1,
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

위 숫자는 응답 형식 예시이며 운영 정책값이 아니다. `draw_count=11`의 실제 `results` 길이는 11이다. 현재 운영 `GachaPolicy`가 없으므로 기본 API는 DB를 변경하지 않고 `503 Gacha policy is not configured`를 반환한다.

### 5.3 벽지·바닥 적용

`PUT /api/v1/housing/surfaces/{item_public_id}`

요청 본문은 없다.

```json
{
  "user_public_id": "8a4a9c2f-645f-4b94-9b5d-16bc7d563f42",
  "item_public_id": "ee50a4a7-f05d-44b2-ac84-9b0276eeedfe",
  "category": "WALLPAPER"
}
```

사용자·아이템·보유 자산 없음은 `404`, `WALLPAPER`·`FLOOR`가 아닌 카테고리는 `422`다.

### 5.4 가구 배치·수정·해제

배치 생성 `POST /api/v1/housing/placed-objects`:

```json
{
  "item_public_id": "ee50a4a7-f05d-44b2-ac84-9b0276eeedfe",
  "position_data": {"x": 1.0, "y": 2.0, "z": 0.0}
}
```

위치 수정 `PATCH /api/v1/housing/placed-objects/{placed_object_public_id}`:

```json
{
  "position_data": {"x": 4.0, "y": 2.0, "z": 1.0}
}
```

생성 `201`과 수정 `200` 응답:

```json
{
  "public_id": "c72314ae-13cc-44b8-aa70-56c39d5ba289",
  "item_public_id": "ee50a4a7-f05d-44b2-ac84-9b0276eeedfe",
  "position_data": {"x": 4.0, "y": 2.0, "z": 1.0}
}
```

삭제는 같은 공개 배치 UUID에 `DELETE`를 보내며 `204`다. 좌표는 유한한 `x`, `y`, `z`를 모두 요구하고 알 수 없는 필드를 거부한다. 리소스·소유권 오류는 `404`, 가구가 아닌 카테고리는 `422`, 보유 수량 초과 배치는 `409`다. 배치 해제는 자산 수량을 줄이지 않는다.

### 5.5 고양이 도감

`GET /api/v1/cats/collection`

```json
{
  "total_count": 2,
  "owned_count": 1,
  "cats": [
    {
      "cat_public_id": "063115f5-749f-43ff-9016-eb9dc4203d30",
      "cat_asset_public_id": "39db1ddb-24c2-42dc-a28c-bc4d9dd5267e",
      "name": "나비",
      "persona": "차분하고 다정한 고양이",
      "rarity": "COMMON",
      "is_owned": true
    },
    {
      "cat_public_id": "6877a193-c416-43d3-8c15-9333520c22c1",
      "cat_asset_public_id": null,
      "name": "별이",
      "persona": "호기심 많은 고양이",
      "rarity": "RARE",
      "is_owned": false
    }
  ]
}
```

보유 고양이만 `cat_asset_public_id`를 가진다. 이를 대화 컨텍스트와 기억 API의 경로에 사용한다.

### 5.6 고양이 persona와 기억

#### 전체 조회

`GET /api/v1/cats/{cat_asset_public_id}/conversation-context`

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

#### 기억 추가

`POST /api/v1/cats/{cat_asset_public_id}/memories`

```json
{"context_summary": "사용자는 함수 호출을 이해했다."}
```

응답 `201`은 생성된 기억의 `public_id`, `cat_asset_public_id`, `context_summary`, `created_at`을 반환한다. 공백 요약은 `422`다.

#### 기억 삭제

- 선택 삭제: `DELETE /api/v1/cats/{cat_asset_public_id}/memories/{memory_public_id}`
- 전체 삭제: `DELETE /api/v1/cats/{cat_asset_public_id}/memories`

둘 다 `204`다. 전체 삭제도 기억 행만 제거하며 `CATS.persona`, 고양이 마스터와 보유 자산은 유지한다. 다른 사용자의 고양이 자산·기억 접근은 `404`로 숨긴다.

### 5.7 생성형 AI 고양이 대화

`POST /api/v1/cats/{cat_asset_public_id}/chat`

프런트엔드는 현재 메시지와 화면에 남아 있는 최근 대화만 전송한다. 최근 대화는 최대 10개이며 각 텍스트와 현재 메시지는 최대 2,000자다.

```json
{
  "message": "파이썬 for 반복문을 예제로 설명해 줘.",
  "recent_messages": [
    {"role": "user", "text": "오늘 반복문을 공부하고 있어."},
    {"role": "assistant", "text": "어떤 부분이 어려운지 말해 달라냥!"}
  ]
}
```

`200 OK` 응답:

```json
{
  "cat_asset_public_id": "39db1ddb-24c2-42dc-a28c-bc4d9dd5267e",
  "reply": "좋아, range를 사용한 짧은 예제부터 보자냥!",
  "memory": {
    "public_id": "a816c517-cc27-418b-b32b-277b40d37af2",
    "cat_asset_public_id": "39db1ddb-24c2-42dc-a28c-bc4d9dd5267e",
    "context_summary": "사용자는 파이썬 반복문을 공부하고 있다.",
    "created_at": "2026-09-05T00:00:00Z"
  },
  "input_tokens": 217,
  "output_tokens": 134
}
```

`memory`는 이번 대화에서 새 장기 기억이 생성됐을 때만 객체이며, 기억할 내용이 없거나 동일한 요약이 이미 있으면 `null`이다. token 값은 공급자가 usage metadata를 제공하지 않으면 `null`일 수 있다.

백엔드는 프런트가 persona를 보내도록 신뢰하지 않는다. 경로의 `cat_asset_public_id`로 현재 사용자의 보유 자산을 확인한 뒤 `ASSETS.cat_id`로 `CATS.persona`를 직접 조회한다. 해당 고양이의 최신 `CAT_MEMORIES` 최대 20개와 persona를 system instruction에 넣고, Gemini 한 번의 구조화 호출에서 답변과 선택적 기억 요약을 함께 생성한다.

대화 원문은 DB에 저장하지 않는다. 프런트가 화면에 필요한 최근 대화를 임시 보관해 다음 요청에 다시 보내고, 장기적으로 유용한 사용자 선호·목표·학습 진도만 `CAT_MEMORIES.context_summary`에 누적한다. 비밀번호, API 키, 연락처 등 민감 정보는 기억 대상으로 지정하지 않는다.

- 인증 실패: `401`
- 고양이 자산이 없거나 현재 사용자 소유가 아님: `404`
- 공백, 너무 긴 메시지, 10개 초과 최근 대화, 잘못된 role·추가 필드: `422`
- Gemini 키 미설정, 무료 할당량 초과, timeout, 공급자 장애 또는 잘못된 구조화 응답: `503`

`503`일 때 다른 유료 모델이나 크레딧으로 자동 전환하지 않는다. 클라이언트는 잠시 후 재시도를 안내하되 무한 자동 재시도를 하지 않는다.

## 6. 멱등성과 클라이언트 재시도

구매와 가챠는 `request_id`를 사용한다.

1. 새로운 사용자 동작에는 새로운 UUID를 생성한다.
2. 응답을 받지 못한 같은 동작의 네트워크 재시도에는 같은 UUID와 같은 payload를 사용한다.
3. 같은 UUID의 사용자 또는 payload가 달라지면 `409 Conflict`다.
4. 성공한 동일 요청은 저장된 최초 결과를 반환하므로 잔액·자산을 다시 변경하지 않는다.

답안 제출은 멱등 `request_id`를 받지 않는다. `202`에서 받은 attempt `public_id`로 결과를 재조회하며 네트워크 오류 때문에 제출을 자동으로 새로 만들지 않는다.

## 7. 현재 공개되지 않은 조회 API

다음 기능은 문서 누락이 아니라 현재 FastAPI 라우터 자체에 없다.

| 필요한 화면 데이터 | 현재 상태 |
| --- | --- |
| 상점 아이템 전체 목록·가격 조회 | 공개 API 없음 |
| 현재 사용자의 전체 보유 자산·수량 조회 | 공개 API 없음 |
| 현재 적용된 벽지·바닥과 배치 가구 전체 조회 | 공개 API 없음 |
| 배틀 방 목록·검색·매칭 | 공개 API 없음 |
| 사용자의 과거 제출 목록 | 공개 API 없음 |

프런트가 이 데이터를 정적 파일이나 다른 서버에서 받지 않는다면 별도의 읽기 API 계약과 구현이 필요하다.

## 8. 정책 미확정 항목

- 가챠 비용·확률·중복 마일리지: 운영 `GachaPolicy` 미설정, 기본 API `503`
- 일일 미션 보상액: `DAILY_REWARD_BALANCE` 미설정 시 보상 API `503`
- 배틀 정답 점수: `BATTLE_CORRECT_SCORE` 미설정 시 현재 배틀 오류 계약에 따라 `409`
- 일반 학습 보상과 직접 문제 선택의 MVP 포함 여부

값이 확정되기 전에는 임의 숫자를 클라이언트나 서버에 하드코딩하지 않는다.

## 9. 상세 계약과 구현 근거

- [Part 2 상세 통합 계약](../features/part2-integration-contract.md)
- [Part 2 구현 현황](../features/part2-status.md)
- [문제·숙련도·추천 정책](../features/part2-learning-system.md)
- [Django Auth Bridge](../features/host-auth-integration.md)
- [Part 3 상세 통합 계약](../architecture/part3-integration-contract.md)
- [Part 3 구현 현황](../architecture/part3-status.md)
- [고양이 생성형 AI 설계](../architecture/cat-ai-integration.md)
- [현재 ERD](../architecture/current-erd.md)

코드 기준 라우터 등록 위치는 `app/api/router.py`이며 FastAPI 애플리케이션은 이를 `/api/v1` prefix로 등록한다.

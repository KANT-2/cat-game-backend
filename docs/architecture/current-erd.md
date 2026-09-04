# Cat Game Backend 현재 ERD

2026-09-04 기준 ORM 모델과 Alembic head를 반영한 16개 업무 테이블의 현재 구조다.

팀 기준 문서는 [Notion ERD 추가수정버전](https://app.notion.com/p/3d1db49922e580e79ba1e7d318230025)이다.

## 최근 변경 사항

- 통합 보유 자산 테이블을 `user_cats`에서 `assets`로 변경했다.
- Python ORM 모델과 응답 DTO는 `Asset`, `AssetRead`를 사용한다.
- `CAT_MEMORIES.cat_asset_id`는 `ASSETS.id` 중 고양이 자산 행을 참조한다.
- `PLACED_OBJECTS.position_data`의 필수 좌표는 `x`, `y`, `z`다. 이전 `rotation` 값은 마이그레이션에서 `z`로 옮긴다.
- `TASKS`는 `CODE`와 `MULTIPLE_CHOICE`, `PYTHON`과 `SQL`을 함께 지원하며 객관식 메타데이터를 JSONB로 저장한다.
- `TASK_ATTEMPTS.result_detail`은 채점 결과 상세를 저장하고 상태는 `PENDING`, `RUNNING`, `COMPLETED`, `FAILED` 흐름을 사용한다.
- API에는 내부 INTEGER PK/FK를 노출하지 않고 UUID `public_id`와 `*_public_id`만 사용한다.

## Mermaid ERD

```mermaid
erDiagram
    USERS {
        int id PK
        uuid public_id UK "UUIDv4"
        string email UK "lower(email) unique"
        string username
        string role
        int balance
        int mileage
        int house_level
        int wallpaper_item_id FK "nullable"
        int floor_item_id FK "nullable"
        datetime created_at
    }

    ATTENDANCES {
        int id PK
        uuid public_id UK "UUIDv4"
        int user_id FK
        date check_in_date
        int streak_count
        datetime daily_reward_claimed_at "nullable"
    }

    ATTENDANCE_TASKS {
        int id PK
        uuid public_id UK "UUIDv4"
        int attendance_id FK
        int task_id FK
        int task_order
        boolean is_completed
    }

    CONCEPTS {
        int id PK
        uuid public_id UK "UUIDv4"
        string name UK
    }

    TASKS {
        int id PK
        uuid public_id UK "UUIDv4"
        int concept_id FK
        string title
        string type "CODE, MULTIPLE_CHOICE"
        string domain "PYTHON, SQL"
        string difficulty "BRONZE, SILVER, GOLD"
        text description
        text template_code
        text test_cases "채점용 테스트 데이터"
        jsonb options "객관식 보기, nullable"
        string correct_option "객관식 정답, nullable"
        text hint_text "nullable"
        boolean is_active
    }

    USER_PROFICIENCY {
        int id PK
        uuid public_id UK "UUIDv4"
        int user_id FK
        int concept_id FK
        int proficiency_level
    }

    TASK_ATTEMPTS {
        int id PK
        uuid public_id UK "UUIDv4"
        int user_id FK
        int task_id FK
        int attendance_task_id FK "nullable"
        int room_task_id FK "nullable"
        string context_type
        text submitted_code
        string status "PENDING, RUNNING, COMPLETED, FAILED"
        boolean is_correct "nullable"
        boolean used_hint
        datetime attempted_at
        text result_detail "채점 결과 상세, nullable"
    }

    ROOMS {
        int id PK
        uuid public_id UK "UUIDv4"
        int host_user_id FK
        string title
        string status
        int max_participants
    }

    ROOM_PARTICIPANTS {
        int id PK
        uuid public_id UK "UUIDv4"
        int room_id FK
        int user_id FK
        string team_name "nullable"
        int current_score
        boolean is_ready
    }

    ROOM_TASKS {
        int id PK
        uuid public_id UK "UUIDv4"
        int room_id FK
        int task_id FK
        int task_order
    }

    ITEMS {
        int id PK
        uuid public_id UK "UUIDv4"
        string category
        string name
        int price
    }

    PLACED_OBJECTS {
        int id PK
        uuid public_id UK "UUIDv4"
        int user_id FK
        int item_id FK
        jsonb position_data "x, y, z"
    }

    CATS {
        int id PK
        uuid public_id UK "UUIDv4"
        string name
        string persona
        string rarity
    }

    ASSETS {
        int id PK
        uuid public_id UK "UUIDv4"
        int user_id FK
        int cat_id FK "nullable"
        int item_id FK "nullable"
        int quantity
    }

    GACHA_EXECUTIONS {
        int id PK
        uuid public_id UK "UUIDv4"
        int user_id FK
        uuid request_id UK
        jsonb request_payload
        string request_hash "SHA-256"
        string operation_type
        string status "ACQUIRED, COMPLETED, HASH_CONFLICT"
        int draw_count "nullable"
        int balance_cost "default 0"
        jsonb result_data "nullable"
        datetime created_at
        datetime completed_at "nullable"
    }

    CAT_MEMORIES {
        int id PK
        uuid public_id UK "UUIDv4"
        int cat_asset_id FK "references assets.id"
        text context_summary
        datetime created_at
    }

    USERS ||--o{ ATTENDANCES : checks_in
    ATTENDANCES ||--o{ ATTENDANCE_TASKS : assigns
    TASKS ||--o{ ATTENDANCE_TASKS : scheduled_as

    USERS ||--o{ USER_PROFICIENCY : has
    CONCEPTS ||--o{ USER_PROFICIENCY : measured_by
    CONCEPTS ||--o{ TASKS : categorizes

    USERS ||--o{ TASK_ATTEMPTS : submits
    TASKS ||--o{ TASK_ATTEMPTS : attempted_as
    ATTENDANCE_TASKS o|--o{ TASK_ATTEMPTS : daily_context
    ROOM_TASKS o|--o{ TASK_ATTEMPTS : battle_context

    USERS ||--o{ ROOMS : hosts
    ROOMS ||--o{ ROOM_PARTICIPANTS : contains
    USERS ||--o{ ROOM_PARTICIPANTS : joins
    ROOMS ||--o{ ROOM_TASKS : assigns
    TASKS ||--o{ ROOM_TASKS : assigned_to

    USERS ||--o{ ASSETS : owns
    CATS o|--o{ ASSETS : held_as
    ITEMS o|--o{ ASSETS : held_as

    USERS ||--o{ PLACED_OBJECTS : places
    ITEMS ||--o{ PLACED_OBJECTS : placed_as
    ITEMS o|--o{ USERS : selected_wallpaper
    ITEMS o|--o{ USERS : selected_floor

    USERS ||--o{ GACHA_EXECUTIONS : executes
    ASSETS ||--o{ CAT_MEMORIES : remembers
```

## 주요 제약

- `ASSETS`는 `cat_id`와 `item_id` 중 정확히 하나만 가진다.
- 고양이 자산은 `quantity = 1`이며 중복 획득은 마일리지로 전환한다.
- `CAT_MEMORIES.cat_asset_id`는 `ASSETS` 중 `cat_id`가 있는 행만 참조할 수 있다.
- 가구 배치 수는 사용자가 보유한 해당 아이템의 `ASSETS.quantity`를 초과할 수 없다.
- `GACHA_EXECUTIONS.request_id`는 전역 UNIQUE이고 다른 사용자나 다른 요청 내용의 재사용은 충돌이다.
- `TASKS.type = CODE`는 `domain`에 따라 Python 또는 격리된 PostgreSQL 채점기로 분기한다.
- `TASKS.type = MULTIPLE_CHOICE`는 `options`와 `correct_option`을 사용하며 채점 전용 값은 API에 노출하지 않는다.
- `TASK_ATTEMPTS.result_detail`에는 verdict와 공개 가능한 오류 요약만 저장한다.

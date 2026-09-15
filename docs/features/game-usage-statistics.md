# 게임 사용 통계

게임 통계는 원본 업무 데이터를 계속 보존하고 SQL VIEW에서 파생 지표를 계산한다. 일반 HTTP 요청
로그는 사용자 식별자를 포함하지 않으며 통계 원본으로 사용하지 않는다.

## 원본 데이터와 보존 정책

- 문제 제출·정오답·힌트·보상은 `task_attempts`를 원본으로 사용한다.
- 게임 대시보드의 정상 진입은 `game_activity_events`에 `GAME_ENTERED`로 추가 기록한다.
- 통계 원본에는 제출 코드, 이메일, 쿠키, 세션 토큰과 요청 본문을 복제하지 않는다.
- 원본 행을 기간 경과로 자동 삭제하는 작업은 두지 않는다. 운영 DB 백업·개인정보 정책에 따른 별도
  결정이 생기기 전까지 계속 보존한다.

## 지표 정의

- `daily_active_users`: 해당 게임 날짜에 게임 스냅샷을 정상 조회했거나 문제를 제출한 고유 사용자 수
- `game_entries`: 게임 스냅샷 정상 조회 횟수. 로그인 세션 수나 정확한 체류 시간과 같지 않다.
- `active_learners`: 문제를 한 번 이상 제출한 고유 사용자 수
- `attempts_submitted`: 채점 상태와 관계없는 전체 제출 수
- `attempts_completed`: 채점이 완료된 제출 수
- `correct_attempts`, `incorrect_attempts`: 완료된 제출 중 정답·오답 수
- `grading_failed_attempts`: 채점 실행에 실패한 제출 수
- `hints_used`: 힌트를 사용한 제출 수
- `coins_awarded`: 제출을 통해 실제 지급된 코인 합계

모든 날짜 경계는 현재 게임 운영 시간대인 `Asia/Seoul`을 사용한다.
장기 보존 중에도 날짜·사용자 범위 조회가 가능하도록 `task_attempts`와 활동 이벤트에 시간 인덱스를
유지한다.

## 조회 VIEW

- `analytics_daily_game_statistics`: 날짜별 전체 게임·학습 지표
- `analytics_user_daily_learning_statistics`: 날짜·사용자별 문제 풀이 지표

## 팀 전용 API

두 API 모두 `X-API-Key` 헤더가 필요하며 최대 조회 범위는 366일이다. 응답에는 내부 INTEGER ID와
이메일을 노출하지 않는다.

```http
GET /api/v1/statistics/daily?date_from=2026-09-01&date_to=2026-09-30
GET /api/v1/statistics/users/daily?date_from=2026-09-01&date_to=2026-09-30
```

현재 구조는 접속 종료나 heartbeat를 저장하지 않으므로 정확한 체류 시간은 제공하지 않는다.

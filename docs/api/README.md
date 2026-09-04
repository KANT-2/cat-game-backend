# API 명세 요약

기본 경로는 `/api/v1`이다. 이 문서는 빠른 탐색용이며 요청 필드, 타입, 필수 여부의 최종 기준은 실행 중인 서버의 `/docs` OpenAPI다. 외부 응답은 내부 정수 PK/FK 대신 UUID `public_id`와 `*_public_id`를 사용한다.

## 인증

| Method | Path | 설명 |
|---|---|---|
| GET | `/session/me` | 현재 사용자 공개 프로필 |
| POST | `/session/development` | `local`·`test` 전용 개발 사용자 생성 또는 조회 |

- 로컬·테스트 환경은 `X-User-Public-ID` 헤더를 지원한다.
- Integration·Production은 브라우저의 `sessionid`를 Django Auth Bridge로 검증한다.
- 홈페이지 사용자 ID는 `homepage_user_id BIGINT UNIQUE`로 연결하고 최초 접속 시 생성한다.
- 인증 거절은 `401/403`, Auth Bridge 장애와 응답 계약 오류는 `503`이다.

## 학습·채점

| Method | Path | 설명 |
|---|---|---|
| GET | `/learning/tasks` | type/domain/concept/difficulty 조건별 활성 문제 조회 |
| GET | `/learning/recommendations` | 취약 개념 우선 추천 및 완료 여부 |
| GET | `/learning/weak-concepts` | 최근 완료 시도 기반 취약 개념 |
| POST | `/attempts` | Python·SQL CODE 또는 객관식 제출 |
| GET | `/attempts/{attempt_public_id}` | 비동기 채점 상태와 결과 조회 |

제출 문맥은 `LEARNING`, `DAILY`, `BATTLE`이며 DAILY/BATTLE 제출은 대응하는 공개 연결 ID가 필요하다. 정답과 테스트 케이스는 문제 조회 응답에 노출하지 않는다. `/learning/tasks`는 `type`, `domain`, `concept_public_id`, `difficulty`, `limit` 필터를 지원하며 잘못된 쿼리 타입/범위는 `422`다.

`POST /attempts`는 `202 PENDING`을 반환하므로 프론트엔드는 반환된 attempt UUID로 `GET /attempts/{attempt_public_id}`를 polling한다. 기본 간격은 1초를 권장하며 `COMPLETED` 또는 `FAILED`에서 종료한다. 30초 동안 terminal 상태가 없으면 자동 polling만 중단하고 같은 attempt UUID로 나중에 재조회한다. 새 제출을 자동 생성하지 않는다. 상세 복구 규칙은 Part 2 통합 계약을 따른다.

## Part 2 오류 요약

| HTTP | 의미 |
|---|---|
| `401` | 세션 없음 또는 개발 인증 사용 불가 |
| `403` | Django Auth Bridge가 계정 접근을 거부 |
| `404` | attempt 미존재/타인 소유 또는 현재 제출 서비스의 task·DAILY·BATTLE 연결 검증 실패 |
| `409` | DAILY/BATTLE 상태 충돌 |
| `422` | 요청 DTO/쿼리 검증 실패 |
| `503` | Auth Bridge 장애/미설정 또는 DAILY 보상 정책 미설정 |

`POST /attempts`의 서비스 계층 검증 오류는 현재 모두 `404`로 매핑되고, 배틀 서비스 오류는 현재 모두 `409`로 매핑된다. 세부 `detail` 문자열은 Part 2 통합 계약을 따른다.

## 일일 미션

| Method | Path | 설명 |
|---|---|---|
| GET | `/daily/today` | 당일 출석 생성 또는 재사용 및 문제 자동 배정 |
| POST | `/daily/{attendance_public_id}/reward` | 전체 완료 후 보상 1회 지급 |

`GET /daily/today`는 `DailyMissionRead(public_id, check_in_date, streak_count, reward_claimed, tasks[])`를 반환한다. 각 `tasks[]`에는 DAILY 제출에 사용하는 `attendance_task_public_id`가 포함된다. 보상은 요청 본문 없이 호출하며, 전체 문제 완료 전에는 `409`, `DAILY_REWARD_BALANCE` 미설정 시에는 `503`이다. 이미 수령한 보상은 추가 지급 없이 `200`으로 현재 상태를 반환한다.

## 배틀

| Method | Path | 설명 |
|---|---|---|
| POST | `/battle/rooms` | 방 생성 |
| GET | `/battle/rooms/{room_public_id}` | 참가자·문제·점수·승자 조회 |
| POST | `/battle/rooms/{room_public_id}/join` | 대기 중인 방 참가 |
| PATCH | `/battle/rooms/{room_public_id}/ready` | 준비 상태 변경 |
| POST | `/battle/rooms/{room_public_id}/start` | 호스트가 문제를 확정하고 시작 |

배틀 응답은 `BattleRoomRead`를 공통으로 사용하며 참가자, 공개 문제 연결 UUID, 점수, 준비 상태, 종료 후 승자 UUID를 포함한다. 배틀 답안은 `/attempts`에 `context_type=BATTLE`과 `room_task_public_id`를 넣어 제출한다. 현재 구현에서 방 관련 서비스 오류는 `409`로 매핑되며 `BATTLE_CORRECT_SCORE` 미설정도 `409`다. 상세 요청/응답 DTO와 정확한 오류 문자열은 Part 2 통합 계약을 따른다.

## 상점·가챠

| Method | Path | 설명 |
|---|---|---|
| POST | `/shop/purchases` | 요청 ID 기반 멱등성 아이템 구매 |
| POST | `/gacha/draws` | 요청 ID 기반 멱등성 고양이 뽑기 |

가챠 정책이 주입되지 않은 환경에서는 가챠 호출이 `503`을 반환한다.

## 하우징·고양이

| Method | Path | 설명 |
|---|---|---|
| PUT | `/housing/surfaces/{item_public_id}` | 보유 벽지 또는 바닥 적용 |
| POST | `/housing/placed-objects` | 보유 가구 배치 |
| PATCH | `/housing/placed-objects/{placed_object_public_id}` | 가구 위치 수정 |
| DELETE | `/housing/placed-objects/{placed_object_public_id}` | 가구 배치 해제 |
| GET | `/cats/{cat_asset_public_id}/conversation-context` | 고양이 페르소나와 기억 조회 |
| POST | `/cats/{cat_asset_public_id}/memories` | 기억 추가 |
| DELETE | `/cats/{cat_asset_public_id}/memories/{memory_public_id}` | 기억 선택 삭제 |
| DELETE | `/cats/{cat_asset_public_id}/memories` | 해당 고양이 기억 전체 삭제 |

## 관련 문서

- [Part 2 통합 계약](../features/part2-integration-contract.md)
- [Part 2 구현 현황](../features/part2-status.md)
- [문제·숙련도·추천 정책](../features/part2-learning-system.md)
- [Django Auth Bridge](../features/host-auth-integration.md)
- [Part 3 연동 계약](../architecture/part3-integration-contract.md)
- [현재 ERD](../architecture/current-erd.md)

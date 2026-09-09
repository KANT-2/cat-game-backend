# AX2 통합 플랫폼 VIEW 연동

## 인증과 식별자

기존 인증 우선순위(게임 세션/개발 헤더 → Django 세션 브리지)를 유지한다.
브리지 `/api/auth/me/` 성공 응답의 `id` = `accounts_user.id` = 게임
`users.homepage_user_id` = 두 VIEW의 `user_id`다. 게임 `users.id` 및
`users.public_id`와는 다르다. 이메일로 계정을 추측하거나 자동 연결하지 않는다.
게임 자체 계정 중 `homepage_user_id`가 없는 계정은 `unlinked`다.

조회는 `CurrentUser` 인증 완료 후 `/session/me` 및 팀 이력 경로에서만 실행한다.
다른 게임 명령에는 AX2 DB 연결 비용이나 장애 영향을 추가하지 않는다.
VIEW의 role/is_active/approval_status/is_staff/is_superuser는 인증이나 권한 판단에
사용하지 않는다. 기존 브리지의 표시 이름, 이메일, 역할 동기화도 유지한다.
VIEW는 별도 `platform.profile`로 보강하며 게임 DB에 복제하지 않는다.

## API

`GET /api/v1/session/me`는 기존 필드를 유지하고 다음 필드만 추가한다.

```json
{
  "platform": {
    "status": "available",
    "profile": {
      "user_email": "player@example.test",
      "primary_email": null,
      "first_name": "여름",
      "last_name": null,
      "display_name_snapshot": "여름",
      "profile_image": "/media/avatar.png",
      "team_name": "대표 팀"
    }
  }
}
```

- `available`: VIEW 행 있음. 팀 미소속은 `team_name: null`일 수 있다.
- `not_found`: 매핑된 사용자의 VIEW 행 없음.
- `unlinked`: 게임 사용자에 플랫폼 식별자 없음.
- `disabled`: DB URL 미설정/빈 값.
- `unavailable`: 연결, SQL, timeout 또는 응답 형식 오류.

`available` 이외에는 `profile: null`이며 기존 인증/기본 프로필의 200 응답은 유지한다.
VIEW의 대표 팀 선정 규칙은 플랫폼이 소유한다. 게임에서 최신 Round를 임의로 선택하지 않는다.
이미지 값은 원본 문자열이며 서버가 원격 이미지를 가져오지 않는다.

`GET /api/v1/session/me/round-teams?round_id=2`는 인증된 사용자의 Round별 팀 이력을
조회한다. 생략하면 전체 이력, 지정하면 AX2 `round_id`에 한정한다. 이 필터는 플랫폼의
외부 식별자이며 게임 내부 PK가 아니다. 사용자 ID는 요청에서 받지 않는다.
응답은 `round_title`, `round_status`, `display_name_snapshot`, `team_number`, `team_name`의
배열이며 정렬은 Round/참가자/팀 ID 오름차순이다. 매칭 행이 없으면 `[]`다.
게임/플랫폼 PK, 전화번호, 학생번호, 세션 및 관리 권한 필드는 응답에 노출하지 않는다.

이력 조회는 미연결 계정 404 `ax-platform-user-unlinked`, 설정 누락 503
`ax-platform-not-configured`, DB 연동 장애 503 `ax-platform-unavailable`, 잘못된 Round
필터 422를 반환한다. 기존 인증 실패 401 및 브리지 장애 503은 기존 동작을 유지한다.
예상하지 못한 게임 오류는 기존 500 경계에서 처리하며 AX2 오류로 숨기지 않는다.

## 배포 설정

- `AX_PLATFORM_DATABASE_URL`: `SecretStr`, 기본값 미설정. 배포 Secret 저장소에서 주입한다.
  비밀번호 없는 형식 예: `postgresql://ax_evaluation@10.2.16.91:5432/ax_evaluation`.
  `postgresql+psycopg://`도 지원한다. 실제 비밀번호는 안전한 채널로 받아 URL 인코딩 후
  Secret에만 설정한다. 코드, 문서, GitHub, 로그에 실제 URL/비밀번호를 기록하지 않는다.
- `AX_PLATFORM_CONNECT_TIMEOUT_SECONDS`: 기본 3초, 1~30초.
- `AX_PLATFORM_STATEMENT_TIMEOUT_MS`: 기본 1000ms, 1~30000ms.
- 기존 `AX_AUTH_BASE_URL`, `AX_AUTH_ME_PATH`, `AX_AUTH_TIMEOUT_SECONDS`,
  `AX_AUTH_SESSION_COOKIE_NAME` 및 게임 `DATABASE_URL`은 별도 설정으로 유지한다.

앱 서버에서 내부망 `10.2.16.91:5432` 접근과 DB 인증을 운영 담당자가 설정해야 한다.
DB 계정은 두 VIEW에 필요한 SELECT/스키마 USAGE만 부여하는 구성을 권장한다.
연결은 기본 읽기 전용과 트랜잭션 읽기 전용을 모두 설정하고 SQL 파라미터를 바인딩한다.
서비스가 요청별 별도 연결을 열고 닫아 롤백하며 repository는 commit하지 않는다.
게임 DB 세션/트랜잭션과 분리되고 풀/캐시는 추가하지 않는다. timeout은 연결 및 각 SQL별
제한이며 전체 HTTP 요청의 절대 deadline을 의미하지 않는다.

플랫폼 VIEW 생성/수정은 이 저장소의 마이그레이션에 넣지 않는다. DBA가 실제 컬럼 타입,
대표 팀 선정 SQL과 중복 행 처리, null 정책, 읽기 권한을 확인해야 한다.
실제 AX2 DB 비밀번호가 없어 운영 DB 접속은 검증하지 않았다.

## 검증 및 변경 범위

단위 테스트는 바인딩, 비밀값 마스킹, 연결 정리, graceful fallback, 인증 없는 조회 차단,
현재 사용자 매핑과 HTTP 오류를 검증한다. PostgreSQL 통합 테스트는 테스트 VIEW의 조회,
Round 필터/사용자 격리, 실제 쓰기 거절, SQL timeout과 브리지→게임→VIEW 연결을 검증한다.
통합 테스트는 기존 테스트와 동일하게 폐기 가능한 `DATABASE_URL`에서만 실행한다.

프론트 최신 main의 `BackendApiClient.parseUser`는 public_id/username/balance만 읽으므로
추가 응답 필드와 호환되며 프론트 수정은 없다. 기존 게임 모델/마이그레이션도 변경하지 않는다.

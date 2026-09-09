# AX2 VIEW 연동 반영 및 검증 기록

## 반영 위치

구현은 백엔드 main의 [b720b7ccabd0750df9273a55edb13951016542c4](https://github.com/KANT-2/cat-game-backend/commit/b720b7ccabd0750df9273a55edb13951016542c4)에 이미 반영되어 있다.
이 문서를 추가하는 PR은 구현을 새로 병합하는 PR이 아니라, 직접 반영된 변경의 검토 및 운영 인수인계를 위한 후속 PR이다.
실제 구현 diff는 위 커밋에서 확인한다. main을 되돌리거나 force push하지 않았다.

## 무엇이 바뀌었는가

- `app/core/config.py`, `.env.example`: SecretStr AX_PLATFORM_DATABASE_URL 및 연결/SQL timeout 설정.
- `app/integrations/ax_platform.py`: 두 public VIEW에 대한 읽기 전용 repository/service. 파라미터 바인딩, 연결 정리, 비밀값을 숨긴 오류 경계.
- `app/modules/identity/router.py`: `/session/me`에 platform 프로필/대표 팀 보강, `/session/me/round-teams`에 선택적 round_id 조회.
- `docs/features/ax-platform-views.md`, `host-auth-integration.md`, `docs/api/README.md`: API, 매핑, 오류 및 배포 계약.
- `tests/unit/test_ax_platform.py`, `tests/integration/test_ax_platform_integration.py`: 신규 검증 15개.
- `tests/test_client_integration.py`: 세션 응답 테스트의 새 의존성 반영.

Django Session Auth Bridge 및 게임 자체 세션 인증은 유지한다.
인증된 사용자의 `homepage_user_id`를 VIEW `user_id`로 사용하며 게임 내부 id나 이메일로 매핑하지 않는다.
VIEW 장애에도 기본 세션/프로필 응답을 유지하고, 명시적인 팀 이력 조회 실패는 503으로 처리한다.
VIEW의 역할 및 관리자 플래그로 권한을 부여하지 않는다. DB 모델/마이그레이션 및 프론트 AX2 UI는 변경하지 않았다.

## 검증 근거

- 로컬 Python 3.12 / PostgreSQL 18: 전체 pytest 389 passed, 10 skipped, Ruff 통과.
- 로컬 skip: SQL grader 전용 DB 테스트 5개, Docker grader 실행 테스트 5개.
- 신규 AX2 테스트 15개: 모두 통과. 실제 PostgreSQL VIEW 조회, 사용자 격리, Round 필터, 쓰기 거절, timeout, 브리지와 게임 사용자 매핑 포함.
- [GitHub Actions](https://github.com/KANT-2/cat-game-backend/actions/runs/34300450542): PostgreSQL 16 기반 Alembic upgrade/downgrade, Docker grader 빌드, pytest, Ruff 단계 모두 통과.
- 추가 로컬 alembic check에서는 기존 main의 `ix_task_attempts_grading_queue` 모델/마이그레이션 불일치가 재현되었다. 이번 변경과 무관하여 수정하지 않았다.
- 실제 AX2 운영 DB 접속 및 운영 홈페이지 로그인 E2E는 비밀번호/내부망 설정이 없어 미검증이다.

## 운영 담당자 설정

1. `AX_PLATFORM_DATABASE_URL`은 배포 Secret에만 주입한다. 비밀번호는 별도 보안 채널로 전달하며 코드/문서/GitHub에 기록하지 않는다.
2. 앱 서버에서 `10.2.16.91:5432`, DB `ax_evaluation`, 사용자 `ax_evaluation` 접근 및 VIEW SELECT 권한을 확인한다.
3. 기존 `AX_AUTH_*`와 게임 `DATABASE_URL`은 유지한다.
4. 기본 timeout은 연결 3초, SQL 1000ms다. `AX_PLATFORM_CONNECT_TIMEOUT_SECONDS`, `AX_PLATFORM_STATEMENT_TIMEOUT_MS`로 설정한다.
5. 실제 홈페이지 로그인 후 `/api/v1/session/me`의 platform 상태와 대표 팀, `/api/v1/session/me/round-teams` 필터 결과를 확인한다.

자세한 응답 예시와 오류 상태는 [AX2 VIEW 연동 계약](ax-platform-views.md)을 따른다.

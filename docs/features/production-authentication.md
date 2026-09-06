# 운영 브라우저 인증

## 계정과 비밀번호

`POST /api/v1/session/register`는 정규화한 이메일, 표시 이름, 12~128자 비밀번호로 학생 계정을 만든다.
비밀번호는 `pwdlib`의 권장 Argon2id 설정으로 개별 salt를 포함해 해시하며 평문을 저장하거나 로그에 남기지
않는다. `POST /api/v1/session/login`은 존재하지 않는 계정에도 더미 Argon2 해시 검증을 수행하고 모든 인증
실패를 `invalid-credentials`로 통일한다.

기존 개발·호스트 계정의 `password_hash`는 nullable이다. 이 계정은 비밀번호 로그인을 할 수 없으며,
`X-User-Public-ID` 개발 헤더는 `APP_ENV=local|test`에서만 허용한다.

## 불투명 세션

가입과 로그인은 CSPRNG로 만든 256비트 세션 토큰을 쿠키에 넣고, PostgreSQL `auth_sessions`에는 SHA-256
해시와 만료·폐기 시각만 저장한다. 운영 쿠키 이름은 `__Host-nyang_session`이며 `Secure`, `HttpOnly`,
`SameSite=Lax`, `Path=/` 속성을 사용한다. 기본 만료는 30일이고 `SESSION_DAYS`로 조정한다.

`POST /api/v1/session/logout`은 현재 세션 행을 폐기하고 세션·CSRF 쿠키를 만료한다. 만료됐거나 폐기된
토큰, DB에 없는 임의 토큰은 모두 `authentication-required` 401로 처리한다.

## CSRF와 CORS

쿠키로 인증한 `POST`, `PUT`, `PATCH`, `DELETE` 요청은 별도 `nyang_csrf` 쿠키 값과 동일한
`X-CSRF-Token`을 보내야 한다. 서버는 이 값의 해시를 현재 세션 행과 상수 시간 비교한다. SameSite는
방어 계층 중 하나이며 CSRF 토큰을 대체하지 않는다. 허용 CORS origin은 명시 목록이고 자격 증명 요청을
허용하며, 허용 헤더에 `X-CSRF-Token`을 포함한다.

## 인증 시도 제한

로그인 실패는 정규화된 계정과 클라이언트 IP 두 범위에서 집계하고, 가입 요청은 클라이언트 IP 범위에서
집계한다. 원문 이메일과 IP 대신 운영 비밀키로 만든 HMAC-SHA-256 버킷만 `auth_rate_limits`에 저장한다.
행 잠금으로 같은 버킷의 동시 요청을 직렬화하므로 API 인스턴스가 여러 개여도 제한을 우회할 수 없다.
기본 로그인 실패 한도는 15분에 5회, 가입 요청 한도는 15분에 10회이며 초과 시 `429`와 `Retry-After`를
반환한다. 운영에서는 인스턴스마다 동일한 고엔트로피 `AUTH_RATE_LIMIT_SECRET`을 반드시 설정한다.
오래된 버킷은 운영 스케줄러에서 매일 `python scripts/prune_auth_rate_limits.py`를 실행해 정리한다.

## 클라이언트 연결과 남은 운영 항목

PWA는 모든 요청에 브라우저 자격 증명을 포함하고, 상태 변경 요청에 CSRF 헤더를 자동으로 붙인다. 운영
빌드에서 기존 세션이 없으면 Canvas 로그인·가입 화면을 표시하며, 인증이나 서버 연결 실패를 로컬 게임
성공으로 대체하지 않는다. Docker 브라우저 스모크는 가입, CSRF 보호 명령, 새로고침 후 세션 복원을
검증한다.

API는 `APP_ENV=production`일 때 시작 전에 PostgreSQL 연결 URL과 단일 HTTPS CORS origin을 검사한다.
SQLite, HTTP, 와일드카드, 여러 origin, 사용자 정보나 경로가 포함된 origin은 호스트 전용 Secure 쿠키 계약과
맞지 않으므로 설정 오류로 즉시 종료한다.

비밀번호 재설정·이메일 검증 정책은 별도 완료 항목이다. 이 문서는 현재 구현을 완료로 과장하지 않는다.

설계 기준은 OWASP Password Storage, Session Management, CSRF Prevention Cheat Sheet와 FastAPI의
Argon2 비밀번호 해싱 예제다.

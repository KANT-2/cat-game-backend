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

## 남은 운영 항목

클라이언트의 Canvas 로그인 화면과 쿠키 전송 연결, 분산 환경에서도 공유되는 로그인 시도 제한,
비밀번호 재설정·이메일 검증 정책은 별도 완료 항목이다. 이 문서는 현재 구현을 완료로 과장하지 않는다.

설계 기준은 OWASP Password Storage, Session Management, CSRF Prevention Cheat Sheet와 FastAPI의
Argon2 비밀번호 해싱 예제다.

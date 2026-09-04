# 홈페이지 로그인 연동 계약

게임은 별도 회원가입이나 비밀번호를 저장하지 않는다. 통합 홈페이지의 Django DB 세션이
인증의 기준이며, 게임 서버는 홈페이지 세션 테이블을 직접 조회하지 않는다.

## 요청 흐름

1. 브라우저가 홈페이지에서 로그인한다.
2. 같은 사이트의 게임 API 요청에 Django `sessionid` 쿠키가 포함된다.
3. 게임 서버가 쿠키를 `AX_AUTH_BASE_URL + AX_AUTH_ME_PATH`에 전달한다.
4. 홈페이지 Bridge API가 세션, `is_active`, `approval_status=approved`를 검증한다.
5. 성공 응답의 `id`, `display_name`, `role`로 게임 사용자를 생성하거나 갱신한다.

권장 성공 응답은 다음과 같다.

```json
{"id": 28, "display_name": "김여름", "role": "student"}
```

`id`는 홈페이지 `accounts_user.id`(BigAutoField)이며 게임 DB의
`users.homepage_user_id` BIGINT에 유일값으로 저장한다. 이메일은 선택값이며, 세션키·비밀번호·
홈페이지 DB 접속정보는 저장하지 않는다. 홈페이지가 401/403을 반환하면 게임도 접근을 거절하고,
홈페이지가 응답하지 않거나 계약과 다른 응답을 주면 503으로 처리한다.

`display_name`과 `role`은 로그인 확인 때마다 홈페이지 값을 Source of Truth로 동기화한다.
로그아웃 Webhook은 MVP 범위가 아니며 이후 게임 API 요청에서 다시 세션을 검증한다.

## 필요한 환경변수

- `AX_AUTH_BASE_URL`: 환경별 홈페이지 주소
- `AX_AUTH_ME_PATH`: 기본값 `/api/auth/me/`
- `AX_AUTH_TIMEOUT_SECONDS`: 기본값 3초
- `AX_AUTH_SESSION_COOKIE_NAME`: 기본값 `sessionid`

서로 다른 사이트에 배포하면 브라우저의 세션 쿠키가 게임 도메인으로 전달되지 않을 수 있으므로,
통합 reverse proxy에서 게임 API를 홈페이지와 같은 site 아래에 두는 구성을 권장한다.

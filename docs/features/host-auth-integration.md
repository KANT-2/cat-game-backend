# 홈페이지 로그인 연동 계약

홈페이지 연동 경로에서는 별도 비밀번호를 저장하지 않는다. 게임 자체 계정 인증도 별도로 존재한다.
홈페이지 연동에서는 통합 홈페이지의 Django DB 세션이
인증의 기준이며, 게임 서버는 홈페이지 세션 테이블을 직접 조회하지 않는다.

## 요청 흐름

1. 브라우저가 홈페이지에서 로그인한다.
2. 같은 사이트의 게임 API 요청에 Django `sessionid` 쿠키가 포함된다.
3. 게임 서버가 쿠키를 `AX_AUTH_BASE_URL + AX_AUTH_ME_PATH`에 전달한다.
4. 홈페이지 Bridge API가 세션, `is_active`, `approval_status=approved`를 검증한다.
5. 성공 응답의 `id`, `display_name`, `role`로 게임 사용자를 생성하거나 갱신하고,
   `profile_image`가 있으면 현재 프로필 이미지로 사용한다.

권장 성공 응답은 다음과 같다.

```json
{
  "id": 28,
  "display_name": "김여름",
  "role": "student",
  "email": "player@example.test",
  "profile_image": "/media/profiles/avatar.jpg"
}
```

`id`는 홈페이지 `accounts_user.id`(BigAutoField)이며 게임 DB의
`users.homepage_user_id` BIGINT에 유일값으로 저장한다. 이메일은 선택값이며, 세션키·비밀번호·
홈페이지 DB 접속정보는 저장하지 않는다. 홈페이지가 401/403을 반환하면 게임도 접근을 거절하고,
홈페이지가 응답하지 않거나 계약과 다른 응답을 주면 503으로 처리한다.

`display_name`과 `role`은 로그인 확인 때마다 홈페이지 값을 Source of Truth로 동기화한다.
`profile_image`는 nullable이며 이미지 파일이 아니라 홈페이지 미디어 서버 기준 경로다.
인증 API가 반환한 이미지 경로를 우선 사용하고, 통합 DB VIEW는 추가 정보와 fallback에 사용한다.
로그아웃 Webhook은 MVP 범위가 아니며 이후 게임 API 요청에서 다시 세션을 검증한다.

## 필요한 환경변수

- `AX_AUTH_BASE_URL`: 환경별 홈페이지 주소
- `AX_AUTH_ME_PATH`: 기본값 `/api/auth/me/`
- `AX_AUTH_TIMEOUT_SECONDS`: 기본값 3초
- `AX_AUTH_SESSION_COOKIE_NAME`: 기본값 `sessionid`

서로 다른 사이트에 배포하면 브라우저의 세션 쿠키가 게임 도메인으로 전달되지 않을 수 있으므로,
통합 reverse proxy에서 게임 API를 홈페이지와 같은 site 아래에 두는 구성을 권장한다.

## AX2 VIEW 보강

인증 완료 후 프로필/팀 VIEW 조회는 [AX2 VIEW 연동](ax-platform-views.md)을 따른다.

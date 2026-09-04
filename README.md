# Cat Game Backend

코딩 학습과 채점, 일일 미션, 배틀, 상점·가챠, 고양이와 하우징을 제공하는 FastAPI 기반 모듈형 모놀리스다.

## 시작

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

- Health check: `GET /health`
- OpenAPI UI: `/docs`
- 업무 API 기본 경로: `/api/v1`

## API 통합 구조

각 기능은 자기 모듈의 `router.py`와 `service.py`에서 요청 처리와 업무 규칙을 분리한다. 모든 기능 라우터는 `app/api/router.py`의 단일 `api_router`에 등록되고, `app/main.py`가 이를 `/api/v1` 아래에 한 번만 연결한다.

```text
app/main.py
└─ /api/v1
   └─ app/api/router.py
      ├─ /session          인증·현재 사용자
      ├─ /learning         추천 문제·취약 개념
      ├─ /attempts         Python·SQL·객관식 제출과 결과
      ├─ /daily            일일 미션
      ├─ /battle/rooms     배틀
      ├─ /shop             상점
      ├─ /gacha            가챠
      ├─ /housing          하우징
      └─ /cats             고양이 페르소나·기억
```

공통 연결 규칙:

- 인증 사용자는 FastAPI `CurrentUser` dependency로 모든 보호 API에 주입한다.
- 외부 API에는 내부 INTEGER PK/FK를 노출하지 않고 UUID `public_id`, `*_public_id`만 사용한다.
- Pydantic 요청·응답 DTO는 `app/schemas`에 두고 채점 정답과 테스트 케이스는 공개 응답에서 제외한다.
- CORS 허용 origin은 `CORS_ORIGINS` 환경변수로 관리하며 credential 요청을 허용한다.
- API의 최종 필드 계약은 실행 서버의 `/docs` OpenAPI가 기준이다.

전체 엔드포인트: [API 명세 요약](docs/api/README.md)

## 로그인 연동 구현

게임 서버는 별도 비밀번호 인증을 운영하거나 홈페이지 세션 DB를 직접 조회하지 않는다. 통합 홈페이지의 Django DB Session이 인증 원본이다.

```text
브라우저
  └─ sessionid 쿠키
     └─ FastAPI CurrentUser
        └─ Django GET /api/auth/me/
           └─ 홈페이지 사용자 확인
              └─ 게임 users.homepage_user_id 연결
```

처리 과정:

1. 브라우저가 게임 API에 Django `sessionid` 쿠키를 보낸다.
2. `app/api/dependencies.py`가 쿠키를 홈페이지 Auth Bridge로 전달한다.
3. 홈페이지 응답의 `id`, `display_name`, `role`, 선택적 `email`을 검증한다.
4. `accounts_user.id`를 게임 DB의 `users.homepage_user_id BIGINT UNIQUE`로 조회한다.
5. 최초 접속이면 게임 사용자를 자동 생성하고, 기존 사용자면 표시명·역할·이메일을 동기화한다.
6. 만들어진 내부 `User` 객체를 학습·채점·DAILY·BATTLE·Part 3 API가 공통으로 사용한다.

보안 및 오류 계약:

- 비밀번호, Django 세션키, 홈페이지 DB 접속정보는 게임 DB에 저장하지 않는다.
- 홈페이지가 `401/403`을 반환하면 게임 접근도 거절한다.
- Auth Bridge 장애, timeout, JSON 또는 필드 계약 오류는 `503`으로 처리한다.
- `local`·`test` 환경에서만 `X-User-Public-ID`와 `POST /session/development`를 제공한다.
- Integration·Production에서는 개발용 헤더 인증을 거절한다.

| 환경변수 | 용도 | 기본값 |
|---|---|---|
| `AX_AUTH_BASE_URL` | 환경별 홈페이지 주소 | 없음 |
| `AX_AUTH_ME_PATH` | Auth Bridge 경로 | `/api/auth/me/` |
| `AX_AUTH_TIMEOUT_SECONDS` | 홈페이지 응답 제한 시간 | `3` |
| `AX_AUTH_SESSION_COOKIE_NAME` | Django 세션 쿠키 이름 | `sessionid` |

실제 E2E 전 홈페이지 팀과 API 경로·응답 필드·쿠키 속성·환경별 주소·테스트 계정을 확정해야 한다. 서로 다른 사이트에 배포하면 쿠키 전달 문제가 생길 수 있어 동일 사이트 reverse proxy 구성을 권장한다.

상세 계약: [Django Session Auth Bridge](docs/features/host-auth-integration.md)

## 구현 현황

### Part 2 — 코딩 학습·채점

- [x] Python CODE Docker sandbox 비동기 채점
- [x] 격리된 PostgreSQL SQL 채점과 읽기 전용·timeout·결과 제한
- [x] 객관식 채점, 숙련도·취약 개념·문제 추천
- [x] Python 150개·SQL 150개 문제 데이터
- [x] DAILY 자동 배정·완료·보상 API
- [x] BATTLE 방·참가·준비·시작·점수·승자 API
- [x] Django Session Auth Bridge 게임 서버 연동부
- [x] 전체 회귀 테스트 `248 passed`
- [ ] 홈페이지 인증 API와 프런트엔드를 포함한 종단간 검증

최근 정리에서는 채점 실행과 상태 전이·숙련도·DAILY/BATTLE 후처리를 분리했다. 외부 API와 채점 정책은 변경하지 않았다.

- [Part 2 구현 현황](docs/features/part2-status.md)
- [학습 문제·객관식·숙련도·추천](docs/features/part2-learning-system.md)
- [Python·SQL Concept 및 SQL 권한 정책](docs/features/concept-policy.md)

### Part 3 — 상점·가챠·하우징

Part 3의 상점·가챠·하우징·고양이 기억 API도 동일한 통합 라우터, `CurrentUser`, 공개 UUID 규칙을 사용한다.

- [Part 3 구현 현황](docs/architecture/part3-status.md)
- [Part 3 API·트랜잭션 계약](docs/architecture/part3-integration-contract.md)

## 구조 원칙

- 기능 중심 모듈형 모놀리스
- HTTP router와 비즈니스 규칙 분리
- 서비스와 Unit of Work가 업무 트랜잭션 소유
- 배틀은 서버 권위 상태 머신으로 관리
- Docker 채점과 일반 학습 기능 분리
- 재화 변경은 economy 모듈을 단일 진입점으로 사용
- 공개 방문자는 타인의 영구 상태에 read-only
- 미확정 가격·확률·보상 정책은 환경변수 또는 정책 객체로 주입

## 문서

- [전체 문서 안내](docs/README.md)
- [현재 ERD](docs/architecture/current-erd.md)
- [아키텍처 개요](docs/architecture/overview.md)

## Codex cloud에서 작업

GitHub 저장소를 Codex cloud 환경에 연결하고 Python 3.12를 사용한다.

```bash
bash scripts/cloud_setup.sh
```

루트의 `AGENTS.md`와 담당 기능 문서를 먼저 확인한다. 비밀값과 실제 `.env`는 Git에 올리지 않고 환경변수 또는 secrets로 설정한다.

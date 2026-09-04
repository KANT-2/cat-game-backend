# Cat Game Backend

코딩 학습, 채점, 일일 미션, 배틀, 랭킹·승급전, 경제, 상점·가챠, 고양이와 하우징을 제공하는 FastAPI 백엔드다.

## 구조 원칙

- 기능 중심 모듈형 모놀리스
- HTTP router와 비즈니스 규칙 분리
- 배틀은 서버 권위 상태 머신으로 관리
- Docker 채점과 일반 학습 기능 분리
- 재화 변경은 economy 모듈을 단일 진입점으로 사용
- 공개 방문자는 타인의 영구 상태에 read-only
- 미확정 가격·확률·보상 정책은 코드에 하드코딩하지 않음

## 시작

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

## API

업무 API의 기본 경로는 `/api/v1`이다. 실행 중인 서버의 `/docs`에서 OpenAPI 명세를 확인할 수 있다.

| 영역 | 대표 경로 | 기능 |
|---|---|---|
| 인증 | `/session/*` | 현재 사용자, 로컬 개발 세션 |
| 학습 | `/learning/*` | 추천 문제, 취약 개념 |
| 채점 | `/attempts/*` | Python·SQL·객관식 제출 및 결과 조회 |
| 일일 미션 | `/daily/*` | 출석, 자동 배정, 완료, 보상 |
| 배틀 | `/battle/rooms/*` | 방, 참가, 준비, 시작, 점수, 승자 |
| 상점·가챠 | `/shop/*`, `/gacha/*` | 구매 및 고양이 뽑기 |
| 하우징·고양이 | `/housing/*`, `/cats/*` | 꾸미기와 고양이 기억 |

전체 엔드포인트와 인증·응답 규칙: [API 명세 요약](docs/api/README.md)

## 구현 현황

| 담당 | 범위 | 상태 | 상세 문서 |
|---|---|---|---|
| Part 2 | 학습·Python/SQL 채점·일일 미션·배틀·Auth Bridge | MVP 완료, 외부 E2E 대기 | [Part 2 현황](docs/features/part2-status.md) |
| Part 3 | 상점·가챠·하우징·고양이 기억 API | API 연결 완료, 정책·PostgreSQL 최종 검증 대기 | [Part 3 현황](docs/architecture/part3-status.md) |

### Part 2

- Python CODE: Docker sandbox 비동기 채점
- SQL CODE: 격리된 PostgreSQL, 읽기 전용·timeout·결과 제한
- MULTIPLE_CHOICE: 서버 정답 비교
- 문제 데이터: Python 150개 + SQL 150개, 난이도별 각 50개
- 학습: 최근 10회 숙련도, 취약 개념, 최근 문제 회피 추천
- DAILY: 당일 자동 배정, 완료 반영, 중복 없는 보상
- BATTLE: 방 생성·참가·준비·시작, 제출 검증, 점수·종료·승자
- 인증: Django `sessionid` Auth Bridge와 로컬 개발 헤더
- 검증: 전체 테스트 `248 passed`

남은 작업은 홈페이지 인증 API를 포함한 로그인 E2E, 프런트엔드 연결, 실제 배포 환경의 DAILY/BATTLE E2E다. 세부 정책은 [문제·숙련도·추천](docs/features/part2-learning-system.md), [Concept·SQL 정책](docs/features/concept-policy.md), [인증 계약](docs/features/host-auth-integration.md)에 분리한다.

문제 데이터 적재:

```powershell
python scripts\seed_learning_tasks.py
python scripts\seed_sql_tasks.py
```

미확정 정책값인 `DAILY_REWARD_BALANCE`, `BATTLE_CORRECT_SCORE`는 환경변수로 주입한다.

## Codex cloud에서 작업

웹에서는 GitHub 저장소를 Codex cloud 환경에 연결한 뒤 이 저장소를 선택한다. 환경의 Python 버전은 3.12로 지정하고 setup script에는 다음을 사용한다.

```bash
bash scripts/cloud_setup.sh
```

새 작업은 루트의 `AGENTS.md`와 `docs/architecture/part3-status.md`를 읽도록 요청하고, Part 3 상태 문서의 권장 순서를 한 항목씩 진행한다. 비밀값과 실제 `.env`는 Git에 올리지 말고 Codex cloud 환경 변수 또는 secrets로 설정한다.


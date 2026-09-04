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

## 기능 진행상황

### Part 2 — 코딩 학습·채점

채점·학습·일일 미션·배틀 백엔드 MVP 구현과 로컬 검증을 완료했다.

- [x] Python CODE Docker sandbox 비동기 채점
- [x] 격리된 PostgreSQL SQL 채점과 읽기 전용·timeout·결과 제한
- [x] 객관식 채점, 숙련도·취약 개념·문제 추천
- [x] Python 150개·SQL 150개 문제 데이터
- [x] DAILY 자동 배정·완료·보상 API
- [x] BATTLE 방·참가·준비·시작·점수·승자 API
- [x] Django Session Auth Bridge 게임 서버 연동부
- [x] 전체 회귀 테스트 `248 passed`
- [ ] 홈페이지 인증 API와 프런트엔드를 포함한 종단간 검증

최근 정리에서는 채점 실행과 상태 전이·숙련도·DAILY/BATTLE 후처리를 분리해 서비스 책임을 명확히 했다. 외부 API와 채점 정책은 변경하지 않았으며 Ruff와 전체 회귀 테스트를 다시 통과했다.

자세한 내용: [Part 2 코딩 학습·채점 진행상황](docs/features/part2-status.md)

Part 2 확장 설계: [학습 문제·객관식·숙련도·추천 MVP](docs/features/part2-learning-system.md)

### Part 3 — 상점·가챠·하우징

자세한 내용: [Part 3 진행상황](docs/architecture/part3-status.md)

## API

업무 API의 기본 경로는 `/api/v1`이며 실행 중인 서버의 `/docs`가 최종 OpenAPI 명세다.

전체 엔드포인트와 인증·응답 규칙: [API 명세 요약](docs/api/README.md)

## Codex cloud에서 작업

웹에서는 GitHub 저장소를 Codex cloud 환경에 연결한 뒤 이 저장소를 선택한다. 환경의 Python 버전은 3.12로 지정하고 setup script에는 다음을 사용한다.

```bash
bash scripts/cloud_setup.sh
```

새 작업은 루트의 `AGENTS.md`와 `docs/architecture/part3-status.md`를 읽도록 요청하고, Part 3 상태 문서의 권장 순서를 한 항목씩 진행한다. 비밀값과 실제 `.env`는 Git에 올리지 말고 Codex cloud 환경 변수 또는 secrets로 설정한다.


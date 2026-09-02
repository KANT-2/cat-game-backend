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

## Codex cloud에서 작업

웹에서는 GitHub 저장소를 Codex cloud 환경에 연결한 뒤 이 저장소를 선택한다. 환경의 Python 버전은 3.12로 지정하고 setup script에는 다음을 사용한다.

```bash
bash scripts/cloud_setup.sh
```

새 작업은 루트의 `AGENTS.md`와 `docs/architecture/part3-status.md`를 읽도록 요청하고, Part 3 상태 문서의 권장 순서를 한 항목씩 진행한다. 비밀값과 실제 `.env`는 Git에 올리지 말고 Codex cloud 환경 변수 또는 secrets로 설정한다.


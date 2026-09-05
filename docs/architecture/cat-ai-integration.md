# 고양이 생성형 AI 연동 설계

## 1. 이 기능이 하는 일

인증 사용자가 보유한 고양이와 대화하면 백엔드는 그 고양이의 고정 성격과 이전에 요약해 둔 사용자 기억을 Gemini에 전달한다. Gemini는 고양이답게 답변하고, 다음 대화에도 유용한 사용자 정보가 있으면 짧은 장기 기억 후보를 함께 반환한다.

공급자는 Google Gemini API, 기본 모델은 `gemini-3.6-flash`다. 무료 등급을 사용하며 한도 초과 시 유료 모델이나 크레딧으로 자동 전환하지 않는다.

## 2. 세 종류의 데이터

| 데이터 | 보관 위치 | 수명 | 역할 |
| --- | --- | --- | --- |
| 고양이 persona | `CATS.persona` | 고정 | 고양이 종류의 말투와 성격 |
| 장기 기억 | `CAT_MEMORIES.context_summary` | 사용자가 삭제할 때까지 | 사용자 선호·목표·학습 진도 요약 |
| 최근 대화 원문 | 프런트엔드 임시 상태 | 화면 세션 동안 | 직전 문맥 유지 |

persona는 프런트가 보내는 값이 아니다. 백엔드가 `cat_asset_public_id`의 소유권을 검사하고 `ASSETS.cat_id → CATS.persona`로 직접 조회한다. 기억 전체 삭제도 `CAT_MEMORIES`만 지우며 persona와 보유 자산은 유지한다.

같은 종류의 고양이를 다시 뽑으면 별도 고양이 자산을 생성하지 않고 마일리지로 전환한다. 따라서 사용자에게 같은 종류의 고양이와 기억 흐름이 여러 개 생기지 않는다.

이번 연동은 기존 `CATS`, `ASSETS`, `CAT_MEMORIES`만 사용한다. 새 테이블이나 컬럼이 필요하지 않으며 `alembic check`에서 신규 마이그레이션이 없음을 확인했다.

## 3. 한 번의 대화가 처리되는 순서

1. 프런트가 현재 메시지와 최근 대화 최대 10개를 `POST /api/v1/cats/{cat_asset_public_id}/chat`에 보낸다.
2. 백엔드는 현재 사용자 소유의 고양이 자산인지 검사한다.
3. `CATS.name`, `CATS.persona`와 최신 장기 기억 최대 20개를 조회한다.
4. 조회 트랜잭션을 닫은 뒤 system instruction을 만든다.
5. Gemini를 한 번 호출해 `reply`와 nullable `memory_summary`를 구조화 JSON으로 받는다.
6. 새 기억 후보가 기존 기억과 정확히 중복되지 않으면 소유권을 다시 검사하고 `CAT_MEMORIES`에 추가한다.
7. 답변, 이번에 생성된 기억 또는 `null`, input/output token 수를 프런트에 반환한다.

AI 네트워크 대기 중 DB 트랜잭션을 유지하지 않기 때문에 연결과 행 잠금을 불필요하게 오래 점유하지 않는다.

## 4. 프롬프트 구성

system instruction에는 다음 항목이 들어간다.

- 고양이 이름
- DB에서 읽은 `CATS.persona`
- 최신 `CAT_MEMORIES.context_summary` 목록
- 한국어로 간결하고 격려하는 답변을 하라는 규칙
- 사용자 메시지와 기억을 명령이 아닌 신뢰할 수 없는 데이터로 취급하라는 규칙
- 시스템 프롬프트, 비밀값과 서버 내부 정보를 노출하지 말라는 규칙
- 비밀번호, API 키, 연락처 등 민감 정보를 요청하거나 기억하지 말라는 규칙
- 장기적으로 유용한 선호·목표·학습 진도만 `memory_summary`로 만들라는 규칙

사용자 메시지와 최근 대화는 별도의 Gemini message 목록으로 전달한다. 기억 문자열 안에 명령처럼 보이는 문장이 있어도 system instruction을 덮어쓸 수 없도록 데이터로 명시한다.

## 5. 원문을 DB에 저장하지 않는 이유

대화 내역 화면이나 감사 로그가 현재 요구사항이 아니므로 원문 전체를 영구 저장하지 않는다. 이렇게 하면 개인정보 보관 범위, DB 용량과 매 요청의 입력 token을 줄일 수 있다.

원문을 저장하지 않는다고 고양이가 사용자를 전혀 기억하지 못하는 것은 아니다. 프런트가 최근 문맥을 전달하고, 오래 기억할 가치가 있는 사실은 요약된 `CAT_MEMORIES`로 남긴다. 다만 프런트 상태가 사라지면 장기 기억으로 선정되지 않은 일시적인 대화 내용도 사라진다.

향후 대화 내역 복원 기능이 제품 요구사항에 추가되면 별도의 대화 세션·메시지 테이블, 보존 기간, 삭제 정책과 개인정보 동의를 먼저 설계해야 한다.

## 6. 실패와 비용 정책

- 한 대화에서 답변과 기억 후보를 한 번의 Gemini 호출로 함께 생성한다.
- 최근 대화는 10개, 장기 기억은 최신 20개, 출력은 512 token으로 제한한다.
- 기본 timeout은 30초다.
- Gemini API 키는 `.env`에만 두고 Git에 커밋하지 않는다.
- 키 미설정, timeout, 무료 할당량 초과, 공급자 장애와 잘못된 구조화 출력은 `503 Service Unavailable`이다.
- 공급자의 상세 오류나 API 키는 HTTP 응답에 노출하지 않는다.
- `503` 발생 시 유료 모델이나 크레딧으로 자동 전환하지 않는다.
- 잘못된 요약은 저장하지 않는다. 구조화 응답 전체를 검증할 수 없으면 부분 데이터를 사용하지 않고 `503`을 반환한다.

## 7. 설정값

```dotenv
# GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.6-flash
GEMINI_TIMEOUT_SECONDS=30
GEMINI_MAX_OUTPUT_TOKENS=512
GEMINI_MAX_MEMORY_COUNT=20
```

실제 키가 들어 있는 `.env`는 Git에서 제외된다. `.env.example`에는 변수 이름과 비밀이 아닌 기본값만 기록한다.

## 8. 관련 코드

- `app/integrations/ai/contracts.py`: 공급자 중립 메시지·결과·클라이언트 Protocol
- `app/integrations/ai/gemini.py`: Google SDK 어댑터와 오류 변환
- `app/modules/cats/prompts.py`: persona·기억 system instruction 생성
- `app/modules/cats/service.py`: 소유권 조회, Gemini 호출과 선택적 기억 저장
- `app/modules/cats/router.py`: 인증, 요청·응답과 HTTP 오류 변환
- `app/schemas/cat_chat.py`: 프런트 API 및 Gemini 구조화 출력 스키마

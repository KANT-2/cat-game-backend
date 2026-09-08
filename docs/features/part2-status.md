# Part 2 학습·채점 시스템 진행상황

기준일: 2026-09-03  
작업 브랜치: `feature/part2-learning`

## 현재 상태

채점 백엔드 MVP 구현과 로컬 검증을 완료했다.

- 전체 테스트: **248 passed**
- PostgreSQL 마이그레이션: **통과**
- FastAPI 서버 및 `/health`: **정상**
- Swagger `/docs`의 grading API 등록: **확인**
- Docker grader 이미지 build/run: **정상**
- PostgreSQL SQL grader 통합 테스트: **QUERY/MUTATION/SCHEMA 검증 포함**

게임 백엔드 담당 범위의 구현은 완료됐다. 아래 잔여 항목은 내부 추가 검증과 외부 팀 의존 작업으로 구분한다.

## 완료된 작업

- [x] Python 코드 제출 요청 스키마
- [x] LEARNING, DAILY, BATTLE 제출 구분
- [x] context별 공개 UUID 조합 검증
- [x] 제출 API 구현
  - `POST /api/v1/attempts`
  - PENDING 상태 저장
  - 백그라운드 채점 예약
- [x] 채점 결과 조회 API 구현
  - `GET /api/v1/attempts/{attempt_public_id}`
  - 본인 제출 결과만 조회
- [x] 테스트 케이스 JSON 파싱 및 형식 검증
- [x] 여러 테스트 케이스 순차 실행
- [x] 정답과 오답 판정
- [x] 문법 오류와 런타임 오류 판정
- [x] 실행 시간 초과 처리
- [x] 채점 상태 및 상세 결과 DB 저장
  - PENDING → RUNNING → COMPLETED 또는 FAILED
- [x] DAILY 정답 제출 시 일일 문제 완료 처리
- [x] 서버 날짜 기준 DAILY 출석 생성과 연속 출석 계산
- [x] 사용자 추천 기반 일일 문제 자동 배정과 조회
- [x] 전체 완료 후 설정 기반 보상 지급 및 중복 수령 방지
- [x] BATTLE 방 생성, 참가, 준비, host 시작
- [x] host가 공개 UUID로 지정한 배틀 문제 배정
- [x] 최초 정답만 설정 기반 점수 반영
- [x] 전원 제출 완료 시 종료 및 공동 승자 계산
- [x] Docker 샌드박스 실행 코드 및 제한 옵션 구현
  - 네트워크 차단
  - 읽기 전용 파일시스템
  - CPU, 메모리, 프로세스, 출력량 제한
- [x] 실제 Docker grader 이미지 빌드
- [x] 실제 컨테이너 정답 판정 확인
- [x] 실제 컨테이너 오답 판정 확인
- [x] 실제 컨테이너 시간 초과 판정 확인
- [x] 내부 INTEGER ID와 비공개 테스트 케이스 API 비노출
- [x] CODE 문제의 PYTHON/SQL dispatcher 분기
- [x] SQL 전용 PostgreSQL, QUERY read-only 트랜잭션, statement timeout
- [x] SQL MUTATION/SCHEMA 모드와 제출 후 강제 rollback
- [x] SQL 위험 구문·multi-statement 차단 및 row/output 제한
- [x] SQL 문제별 seed 스키마 생성 및 실행 후 초기화
- [x] Part 2 응답 DTO와 OpenAPI response model 명시

## 잔여 검증과 외부 의존 작업

### 백엔드에서 추가 가능한 검증

- [ ] 인증 대역을 포함한 제출·조회 API 통합 테스트 강화
- [ ] PENDING → RUNNING → COMPLETED/FAILED 상태 전이 DB 통합 테스트 강화
- [ ] mock Auth Bridge와 BackgroundTasks를 포함한 DAILY/BATTLE API 통합 테스트
- [ ] 운영 배포 환경에서 Python/SQL grader 네트워크와 자원 제한 재검증

### 다른 팀 또는 정책 확정 필요

- [ ] 홈페이지 `/api/auth/me/` 구현본과 실제 로그인 종단간 검증
- [ ] DAILY 보상액과 BATTLE 점수값 최종 확정 및 배포 환경변수 설정
- [ ] BATTLE 시간 보너스·힌트 감점 등 추가 정책 확정
- [ ] AI 문제 생성 측 test_cases 생성·검수 정책 확정
- [ ] 프런트엔드 제출·진행 상태·결과 화면 연결

## 현재 API 사용 시 주의사항

로그인은 홈페이지의 `/api/auth/me/` Bridge API 계약을 사용한다. 홈페이지 세션 쿠키 없이 grading API를 호출하면 `401 Unauthorized`, Bridge 주소가 설정되지 않으면 `503 Service Unavailable`이 반환된다.

인증 연결 후 다음 흐름을 최종 검증해야 한다.

1. 사용자가 코드를 제출한다.
2. API가 PENDING attempt UUID를 반환한다.
3. Docker 채점기가 코드를 실행한다.
4. 프런트엔드가 결과 조회 API로 완료 여부를 확인한다.
5. DAILY 또는 BATTLE 기능이 채점 결과를 사용한다.

## 관련 문서

- 상세 검증 체크리스트: `docs/features/verified-grading-checklist.md`
- 전체 백엔드 구조: `docs/architecture/overview.md`
- Part 3 진행상황: `docs/architecture/part3-status.md`

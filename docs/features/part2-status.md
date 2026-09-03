# Part 2 코딩 학습·채점 진행상황

기준일: 2026-09-03  
작업 브랜치: `feature/part2-learning`

## 현재 상태

채점 백엔드 MVP 구현과 로컬 검증을 완료했다.

- 전체 테스트: **88개 통과, 실패 0개**
- PostgreSQL 마이그레이션: **통과**
- FastAPI 서버 및 `/health`: **정상**
- Swagger `/docs`의 grading API 등록: **확인**
- Docker grader 이미지 build/run: **정상**

실제 서비스 적용 전에는 팀 인증, 보안 제한의 세부 검증, 프런트엔드 연결이 필요하다.

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
- [x] Docker 샌드박스 실행 코드 및 제한 옵션 구현
  - 네트워크 차단
  - 읽기 전용 파일시스템
  - CPU, 메모리, 프로세스, 출력량 제한
- [x] 실제 Docker grader 이미지 빌드
- [x] 실제 컨테이너 정답 판정 확인
- [x] 실제 컨테이너 오답 판정 확인
- [x] 실제 컨테이너 시간 초과 판정 확인
- [x] 내부 INTEGER ID와 비공개 테스트 케이스 API 비노출

## 아직 남은 작업

- [ ] 팀 로그인·인증 기능을 `get_current_user`에 연결
- [ ] Docker 네트워크·읽기 전용·권한·메모리 제한의 개별 공격 시나리오 검증
- [ ] 인증을 포함한 제출·조회 API 통합 테스트
- [ ] PENDING → RUNNING → 완료 상태 전이 DB 통합 테스트
- [ ] DAILY 완료 처리 통합 테스트
- [ ] BATTLE 점수·보너스·감점 정책 확정 및 서비스 연결
- [ ] AI 문제 생성 측 test_cases 생성·검수 정책 확정
- [ ] 프런트엔드 제출·진행 상태·결과 화면 연결

## 현재 API 사용 시 주의사항

팀 인증 기능이 아직 연결되지 않았다. 따라서 Swagger에서 grading API를 바로 호출하면 `401 Unauthorized`가 반환되는 것이 정상이다.

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

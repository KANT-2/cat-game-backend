# Documentation

- `product/`: 사용자 흐름과 미확정 정책
- `features/`: 기능별 단일 시나리오 문서
- `architecture/`: 시스템·트랜잭션·채점·실시간 설계
- `adr/`: 중요한 설계 결정 기록
- `api/`: 외부 API 경로와 인증·응답 계약 요약

`by_flow`와 `by_function`으로 같은 내용을 복제하지 않는다.

## API

- `api/README.md`: 전체 공개 API 빠른 목록. 상세 필드의 최종 기준은 실행 서버의 `/docs`다.

## Part 3 핵심 문서

- `architecture/part3-integration-contract.md`: 트랜잭션 계약과 Frontend ↔ Backend API 입출력
- `architecture/part3-status.md`: 현재 구현·검증 상태와 남은 위험
- `architecture/part3-implementation-checklist.md`: 구현 및 PostgreSQL 통합 검증 체크리스트


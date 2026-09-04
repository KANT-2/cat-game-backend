# Python·SQL Concept 기준

Concept는 학습 영역만 나타내며 난이도는 `TASKS.difficulty`에서 별도로 관리한다. 숫자 `concept_id`는 DB 내부 식별자이므로 코드에 고정하지 않고, 시드는 아래의 안정적인 Concept 이름을 조회해 연결한다. 외부 API에는 `concept_public_id` UUID만 노출한다.

## Python Concept 7개

```text
PYTHON:basics
PYTHON:conditionals
PYTHON:loops
PYTHON:strings
PYTHON:collections
PYTHON:functions
PYTHON:exceptions
```

알고리즘·그래프·동적 계획법은 별도 Concept로 만들지 않는다. 문제의 핵심 학습 영역에 따라 `collections`, `functions` 등에 포함하고 실제 복잡도는 Bronze, Silver, Gold 난이도로 표현한다.

## SQL Concept 9개

```text
SQL:basics
SQL:filtering
SQL:aggregation
SQL:joins
SQL:subqueries
SQL:advanced_queries
SQL:data_manipulation
SQL:schema
SQL:transactions
```

조회뿐 아니라 `INSERT`, `UPDATE`, `DELETE`, 테이블 정의와 트랜잭션도 SQL 교육 Concept에 포함한다.

## 현재 SQL 샌드박스 모드

현재 구현은 문제의 숨겨진 채점 명세에 따라 세 모드로 분리한다.

```text
QUERY    → SELECT 실행 후 기준 쿼리 결과와 비교
MUTATION → INSERT/UPDATE/DELETE 한 문장 실행 후 테이블 상태 검사
SCHEMA   → CREATE/ALTER/DROP 한 문장 실행 후 information_schema 검사
```

모든 모드는 문제별 임시 스키마와 트랜잭션에서 실행되고 제출 종료 시 rollback 및 스키마 삭제를 수행한다. `TRUNCATE`, `GRANT`, `REVOKE`, `COPY`, `CALL`, `DO`와 multi-statement는 계속 차단한다.

이 구문들은 중요하지 않아서 제외한 것이 아니다. 다른 제출의 seed data 변경, 스키마 삭제, 권한 변경, 대량 데이터 생성, 검사 우회, 운영 DB 오연결 시 실제 데이터 손상 위험 때문에 현재 실행 권한에서 차단했다.

현재 보호 장치는 다음과 같다.

- 운영 DB와 분리된 전용 PostgreSQL
- 문제별 임시 seed 스키마
- QUERY의 read-only transaction, 변경 모드의 강제 rollback
- statement 및 연결 timeout
- 결과 행 수와 출력 크기 제한
- 실행 후 임시 스키마 삭제
- DB 자격증명과 내부 오류 비노출

권한 및 외부 접근 위험이 큰 `GRANT`, `REVOKE`, `COPY`, `CALL`, `DO`와 여러 문장을 요구하는 트랜잭션 실습은 객관식으로 제공한다.

## 전체 수

```text
Python Concept   7개
SQL Concept      9개
전체 Concept     16개
```

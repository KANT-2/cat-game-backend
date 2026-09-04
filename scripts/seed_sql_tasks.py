"""Idempotently seed 150 SQL tasks: 50 Bronze, 50 Silver, and 50 Gold."""

from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.concept import Concept
from app.models.task import Task

SEED_PREFIX = "[SAMPLE:SQL:"
SEED_SQL = """
CREATE TABLE students (id int, name text, team text, score int, active boolean);
INSERT INTO students VALUES
 (1,'Miso','RED',75,true),(2,'Nabi','BLUE',92,true),(3,'Bori','RED',84,false),
 (4,'Coco','BLUE',68,true),(5,'Dodo','GREEN',92,true);
CREATE TABLE orders (id int, student_id int, amount int, status text);
INSERT INTO orders VALUES
 (1,1,1200,'PAID'),(2,2,800,'PAID'),(3,1,500,'CANCELLED'),
 (4,3,1500,'PAID'),(5,5,700,'READY'),(6,2,1100,'PAID');
CREATE TABLE nums (n int);
INSERT INTO nums SELECT generate_series(1,10);
""".strip()


def query_case(reference_query: str) -> str:
    expected = json.dumps({"mode": "QUERY", "reference_query": reference_query})
    return json.dumps([{"input": SEED_SQL, "expected_output": expected}], ensure_ascii=False)


def task(level: str, number: int, concept: str, title: str, prompt: str, query: str) -> dict:
    return {
        "title": f"{SEED_PREFIX}{level}:{number:03d}] {title}",
        "concept": f"SQL:{concept}",
        "difficulty": level,
        "type": "CODE",
        "description": prompt,
        "template_code": "-- SELECT 문을 작성하세요.\n",
        "test_cases": query_case(query),
        "options": None,
        "correct_option": None,
        "hint_text": "결과의 행 순서까지 문제의 요구와 일치시켜야 합니다.",
    }


def build_query_tasks(level: str, definitions: list[tuple[str, str, str, str]]) -> list[dict]:
    return [task(level, i, *definition) for i, definition in enumerate(definitions, 1)]


def bronze_definitions() -> list[tuple[str, str, str, str]]:
    rows = []
    for i in range(1, 6):
        rows.extend([
            ("basics", f"숫자 {i} 출력", f"정수 {i}를 한 행으로 조회하세요.", f"SELECT {i}"),
            ("filtering", f"학번 {i} 학생", f"students에서 id가 {i}인 이름을 조회하세요.", f"SELECT name FROM students WHERE id={i}"),
            ("filtering", f"점수 {60 + i * 5} 이상", "해당 점수 이상 학생 이름을 id순 조회하세요.", f"SELECT name FROM students WHERE score>={60 + i * 5} ORDER BY id"),
            ("basics", f"점수에 {i} 더하기", f"모든 학생의 id와 score+{i}를 id순 조회하세요.", f"SELECT id,score+{i} FROM students ORDER BY id"),
            ("filtering", f"앞에서 {i}명", f"학생 이름을 id순으로 앞에서 {i}명 조회하세요.", f"SELECT name FROM students ORDER BY id LIMIT {i}"),
            ("basics", f"별칭 score_{i}", f"id와 score를 score_{i} 별칭으로 조회하세요.", f'SELECT id,score AS score_{i} FROM students ORDER BY id'),
            ("filtering", f"{i} 제외 학생", f"id가 {i}가 아닌 학생 이름을 id순 조회하세요.", f"SELECT name FROM students WHERE id<>{i} ORDER BY id"),
            ("basics", f"이름 길이 {i} 이상", f"이름 길이가 {i} 이상인 이름과 길이를 조회하세요.", f"SELECT name,length(name) FROM students WHERE length(name)>={i} ORDER BY id"),
            ("filtering", f"nums의 {i}배수", f"nums에서 {i}의 배수를 오름차순 조회하세요.", f"SELECT n FROM nums WHERE n%{i}=0 ORDER BY n"),
            ("basics", f"점수 구간 {i}", f"점수가 {i * 10}보다 큰 학생 id와 점수를 조회하세요.", f"SELECT id,score FROM students WHERE score>{i * 10} ORDER BY id"),
        ])
    return rows


def silver_definitions() -> list[tuple[str, str, str, str]]:
    rows = []
    for i in range(1, 6):
        rows.extend([
            ("aggregation", f"팀별 인원 {i}", f"id가 {i} 이상인 학생을 팀별 집계하세요.", f"SELECT team,count(*) FROM students WHERE id>={i} GROUP BY team ORDER BY team"),
            ("aggregation", f"팀별 최고점 {i}", f"id가 {i} 이상인 학생의 팀별 최고점을 조회하세요.", f"SELECT team,max(score) FROM students WHERE id>={i} GROUP BY team ORDER BY team"),
            ("joins", f"학생 주문 {i}", f"주문 id가 {i} 이상인 주문의 학생명과 금액을 조회하세요.", f"SELECT s.name,o.amount FROM students s JOIN orders o ON o.student_id=s.id WHERE o.id>={i} ORDER BY o.id"),
            ("joins", f"주문 없는 학생 기준 {i}", f"금액이 {i * 300} 이상인 주문과 학생을 LEFT JOIN 결과로 조회하세요.", f"SELECT s.name,o.amount FROM students s LEFT JOIN orders o ON o.student_id=s.id AND o.amount>={i * 300} ORDER BY s.id,o.id"),
            ("subqueries", f"평균 초과 점수 {i}", f"id가 {i} 이상인 학생 평균보다 점수가 높은 학생을 조회하세요.", f"SELECT name FROM students WHERE id>={i} AND score>(SELECT avg(score) FROM students WHERE id>={i}) ORDER BY id"),
            ("aggregation", f"결제 합계 {i}", f"student_id가 {i} 이상인 PAID 주문 합계를 학생별 조회하세요.", f"SELECT student_id,sum(amount) FROM orders WHERE status='PAID' AND student_id>={i} GROUP BY student_id ORDER BY student_id"),
            ("filtering", f"이름 패턴 위치 {i}", f"이름의 {i}번째 문자와 학생 id를 조회하세요.", f"SELECT id,substring(name FROM {i} FOR 1) FROM students ORDER BY id"),
            ("subqueries", f"주문 보유 학생 {i}", f"{i * 400} 이상 주문이 있는 학생을 조회하세요.", f"SELECT name FROM students s WHERE EXISTS (SELECT 1 FROM orders o WHERE o.student_id=s.id AND o.amount>={i * 400}) ORDER BY id"),
            ("aggregation", f"HAVING 주문수 {i}", f"주문이 {i}개 이상인 학생별 주문 수를 조회하세요.", f"SELECT student_id,count(*) FROM orders GROUP BY student_id HAVING count(*)>={i} ORDER BY student_id"),
            ("joins", f"결제 주문 순위값 {i}", f"PAID 주문 중 id가 {i} 이상인 학생명·금액을 금액 내림차순 조회하세요.", f"SELECT s.name,o.amount FROM orders o JOIN students s ON s.id=o.student_id WHERE o.status='PAID' AND o.id>={i} ORDER BY o.amount DESC,o.id"),
        ])
    return rows


def gold_definitions() -> list[tuple[str, str, str, str]]:
    rows = []
    for i in range(1, 6):
        rows.extend([
            ("advanced_queries", f"점수 순위 {i}", f"id가 {i} 이상인 학생의 점수 순위를 구하세요.", f"SELECT name,dense_rank() OVER(ORDER BY score DESC) FROM students WHERE id>={i} ORDER BY id"),
            ("advanced_queries", f"누적 주문액 {i}", f"주문 id {i} 이상에서 학생별 누적 주문액을 구하세요.", f"SELECT id,student_id,sum(amount) OVER(PARTITION BY student_id ORDER BY id) FROM orders WHERE id>={i} ORDER BY id"),
            ("advanced_queries", f"직전 점수 차 {i}", f"id {i} 이상 학생을 id순으로 직전 점수와 비교하세요.", f"SELECT id,score-lag(score) OVER(ORDER BY id) FROM students WHERE id>={i} ORDER BY id"),
            ("subqueries", f"팀 최고점 학생 {i}", f"id {i} 이상 범위에서 각 팀 최고점 학생을 조회하세요.", f"SELECT name,team,score FROM students s WHERE id>={i} AND score=(SELECT max(score) FROM students x WHERE x.team=s.team AND x.id>={i}) ORDER BY id"),
            ("advanced_queries", f"재귀 합계 {i}", f"재귀 CTE로 1부터 {i + 5}까지 합을 조회하세요.", f"WITH RECURSIVE r(n) AS (VALUES(1) UNION ALL SELECT n+1 FROM r WHERE n<{i + 5}) SELECT sum(n) FROM r"),
            ("joins", f"팀별 결제 최고액 {i}", f"id {i} 이상 학생의 팀별 PAID 주문 최고액을 조회하세요.", f"SELECT s.team,max(o.amount) FROM students s JOIN orders o ON o.student_id=s.id WHERE s.id>={i} AND o.status='PAID' GROUP BY s.team ORDER BY s.team"),
            ("advanced_queries", f"이동 평균 {i}", f"id {i} 이상 학생 점수의 현재·직전 행 평균을 구하세요.", f"SELECT id,avg(score) OVER(ORDER BY id ROWS BETWEEN 1 PRECEDING AND CURRENT ROW) FROM students WHERE id>={i} ORDER BY id"),
        ])
    return rows


def build_tasks() -> list[dict]:
    rows = build_query_tasks("BRONZE", bronze_definitions())
    rows += build_query_tasks("SILVER", silver_definitions())
    gold = build_query_tasks("GOLD", gold_definitions())
    scores = [75, 92, 84, 68, 92]
    for i in range(1, 6):
        spec = json.dumps({"mode": "MUTATION", "verification_query": f"SELECT score FROM students WHERE id={i}", "expected_rows": [[scores[i - 1] + i]]})
        gold.append({**task("GOLD", 35 + i, "data_manipulation", f"학생 {i} 점수 수정", f"id {i}의 점수를 {i} 올리세요.", "SELECT 1"), "template_code": "-- UPDATE 문을 작성하세요.\n", "test_cases": json.dumps([{"input": SEED_SQL, "expected_output": spec}], ensure_ascii=False)})
        ddl_spec = json.dumps({"mode": "SCHEMA", "verification_query": f"SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='badges_{i}' ORDER BY ordinal_position", "expected_rows": [["id"], ["label"]]})
        gold.append({**task("GOLD", 40 + i, "schema", f"배지 테이블 {i}", f"badges_{i}(id int, label text) 테이블을 만드세요.", "SELECT 1"), "template_code": "-- CREATE TABLE 문을 작성하세요.\n", "test_cases": json.dumps([{"input": SEED_SQL, "expected_output": ddl_spec}], ensure_ascii=False)})
        gold.append({**task("GOLD", 45 + i, "transactions", f"트랜잭션 판단 {i}", "여러 변경을 하나의 작업으로 확정하거나 취소할 때 사용하는 명령 묶음을 고르세요.", "SELECT 1"), "type": "MULTIPLE_CHOICE", "template_code": "", "test_cases": "[]", "options": {"A": "BEGIN / COMMIT / ROLLBACK", "B": "SELECT / FROM / WHERE", "C": "GRANT / REVOKE", "D": "COPY / CALL"}, "correct_option": "A", "hint_text": "원자성과 확정·취소를 생각하세요."})
    rows += gold
    assert len(rows) == 150
    assert len({row["title"] for row in rows}) == 150
    return rows


def seed_key(title: str) -> str:
    return title.partition("]")[0] + "]"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        concepts = {row.name: row for row in db.scalars(select(Concept)).all()}
        existing = {seed_key(row.title): row for row in db.scalars(select(Task).where(Task.title.startswith(SEED_PREFIX))).all()}
        created = updated = 0
        for data in build_tasks():
            concept_name = data.pop("concept")
            concept = concepts.get(concept_name)
            if concept is None:
                concept = Concept(name=concept_name)
                db.add(concept)
                db.flush()
                concepts[concept_name] = concept
            values = {**data, "concept_id": concept.id, "domain": "SQL", "is_active": True}
            row = existing.get(seed_key(data["title"]))
            if row is None:
                db.add(Task(**values))
                created += 1
            else:
                for key, value in values.items():
                    setattr(row, key, value)
                updated += 1
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        print({"created": created, "updated": updated, "dry_run": args.dry_run})
    finally:
        db.close()


if __name__ == "__main__":
    main()

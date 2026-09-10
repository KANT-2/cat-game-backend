"""Idempotently seed 150 SQL tasks: 50 Bronze, 50 Silver, and 50 Gold."""

from __future__ import annotations

import argparse
import json

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.concept import Concept
from app.models.task import Task

SEED_PREFIX = "[SAMPLE:SQL:"
CAT_HELPERS = ("치즈", "나비", "보리", "코코", "모카")
STORIES = (
    "츄르를 사고 싶어 고양이 학교 친구들의 주문 장부를 살펴보고 있어요.",
    "고양이용 우유를 함께 주문하려고 친구들의 신청 기록을 정리하고 있어요.",
    "장난감 놀이 대회를 준비하며 친구들의 점수와 팀 기록을 확인하고 있어요.",
    "방석 공동구매를 준비하며 결제한 주문과 취소한 주문을 확인하고 있어요.",
    "리본과 목걸이 선물을 준비하며 친구 목록과 주문 기록을 살펴보고 있어요.",
    "캣타워 놀이 모임에서 친구들의 점수 기록을 정리하고 있어요.",
    "생선 가게 심부름을 마치고 친구들의 주문 내역을 정리하고 있어요.",
)
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


def sql_hint(concept: str, title: str) -> str:
    if "이름 패턴" in title:
        return "`substring(name FROM 위치 FOR 1)`로 문자를 꺼내고 `ORDER BY id`로 정렬하세요."
    if concept == "filtering":
        return "`WHERE`에 문제의 비교 조건을 쓰고, 요구된 순서는 `ORDER BY`, 개수 제한은 `LIMIT`로 처리하세요."
    if concept == "basics":
        return "`SELECT` 뒤에 요구된 열이나 계산식을 적고, 별칭은 `AS`, 이름 길이는 `length(name)`을 사용하세요."
    if concept == "aggregation":
        if "HAVING" in title:
            return "`GROUP BY student_id`로 묶은 뒤 `HAVING count(*) >= 기준값`으로 그룹을 거르세요."
        return "행 조건은 `WHERE`에 쓰고, 기준 열로 `GROUP BY`한 뒤 `count`, `max`, `sum` 중 문제의 집계 함수를 사용하세요."
    if concept == "joins":
        if "주문 없는" in title:
            return "학생을 남겨야 하므로 `students LEFT JOIN orders ON ...`을 쓰고 금액 조건도 `ON` 안에 두세요."
        return "학생 id와 주문의 student_id를 `JOIN ... ON`으로 연결한 뒤 `WHERE`, `GROUP BY`, `ORDER BY`를 문제 순서대로 붙이세요."
    if concept == "subqueries":
        if "주문 보유" in title:
            return "학생별 주문 존재 여부를 `WHERE EXISTS (SELECT 1 FROM orders ... )` 형태로 확인하세요."
        if "평균 초과" in title:
            return "비교 기준 평균을 괄호 안 `SELECT avg(score)`로 먼저 구해 바깥 `WHERE score > (...)`에서 사용하세요."
        return "바깥 학생의 team과 안쪽 학생의 team을 연결한 상관 서브쿼리에서 `max(score)`를 구하세요."
    if concept == "advanced_queries":
        if "점수 순위" in title:
            return "`dense_rank() OVER (ORDER BY score DESC)`로 동점에 같은 순위를 매기세요."
        if "누적 주문액" in title:
            return "`sum(amount) OVER (PARTITION BY student_id ORDER BY id)`로 학생별 누적 합을 구하세요."
        if "직전 점수" in title:
            return "`lag(score) OVER (ORDER BY id)`로 직전 점수를 가져와 현재 score에서 빼세요."
        if "재귀 합계" in title:
            return "`WITH RECURSIVE`에서 1을 시작값으로 두고 N까지 1씩 늘린 뒤 바깥에서 `sum`하세요."
        return "`avg(score) OVER (ORDER BY id ROWS BETWEEN 1 PRECEDING AND CURRENT ROW)` 창 범위를 사용하세요."
    if concept == "data_manipulation":
        return "`UPDATE students` 뒤 `SET`에서 기존 score에 값을 더하고, `WHERE id = ...`로 한 학생만 고르세요."
    if concept == "schema":
        return "`CREATE TABLE 테이블명 (...)` 안에 id는 int, label은 text 열로 선언하세요."
    return "문제에서 요구한 SQL 절을 데이터 안내의 테이블과 열 이름으로 순서대로 구성하세요."


def staged_sql_hint(concept: str, title: str) -> str:
    if concept == "data_manipulation":
        start = "[대상] 바꿀 행의 id와 바꿀 열을 문제에서 먼저 표시하세요."
        check = "[확인] `WHERE`가 한 학생만 선택하는지, 새 score가 기존 값에 더해졌는지 확인하세요."
    elif concept == "schema":
        start = "[대상] 만들 테이블 이름과 필요한 열 이름·자료형을 먼저 적어 보세요."
        check = "[확인] 세미콜론 전까지 테이블명, 열 순서, int/text 자료형이 요구와 같은지 확인하세요."
    else:
        start = "[대상] 최종 결과에 필요한 열, 필터 조건, 정렬 순서를 문제에서 각각 찾아 표시하세요."
        check = "[확인] `SELECT` 열 순서와 `ORDER BY`가 문제의 출력 순서와 같은지 마지막으로 확인하세요."
    return "\n".join((start, f"[작성] {sql_hint(concept, title)}", check))


def task(level: str, number: int, concept: str, title: str, prompt: str, query: str) -> dict:
    cat = CAT_HELPERS[(number - 1) % len(CAT_HELPERS)]
    return {
        "title": f"{SEED_PREFIX}{level}:{number:03d}] 🐾 {cat}의 데이터 부탁: {title}",
        "concept": f"SQL:{concept}",
        "difficulty": level,
        "type": "CODE",
        "description": (
            f"[도와주세요!] {cat}가 {STORIES[(number - 1) % len(STORIES)]}\n\n"
            "[데이터 안내] students는 고양이 학교 학생과 놀이 점수, orders는 학생별 주문, "
            "nums는 숫자 연습표예요. 아래 문제에 적힌 테이블과 열 이름을 그대로 사용해 주세요.\n\n"
            f"[문제] {prompt}"
        ),
        "template_code": "-- 아래에 SQL을 작성하세요.\n",
        "test_cases": query_case(query),
        "options": None,
        "correct_option": None,
        "hint_text": staged_sql_hint(concept, title),
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
        gold.append({**task("GOLD", 35 + i, "data_manipulation", f"학생 {i} 점수 수정", f"id {i}의 점수를 {i} 올리세요.", "SELECT 1"), "test_cases": json.dumps([{"input": SEED_SQL, "expected_output": spec}], ensure_ascii=False), "hint_text": staged_sql_hint("data_manipulation", f"학생 {i} 점수 수정")})
        ddl_spec = json.dumps({"mode": "SCHEMA", "verification_query": f"SELECT column_name FROM information_schema.columns WHERE table_schema=current_schema() AND table_name='badges_{i}' ORDER BY ordinal_position", "expected_rows": [["id"], ["label"]]})
        gold.append({**task("GOLD", 40 + i, "schema", f"배지 테이블 {i}", f"badges_{i}(id int, label text) 테이블을 만드세요.", "SELECT 1"), "test_cases": json.dumps([{"input": SEED_SQL, "expected_output": ddl_spec}], ensure_ascii=False), "hint_text": staged_sql_hint("schema", f"배지 테이블 {i}")})
        gold.append({**task("GOLD", 45 + i, "transactions", f"트랜잭션 판단 {i}", "여러 변경을 하나의 작업으로 확정하거나 취소할 때 사용하는 명령 묶음을 고르세요.", "SELECT 1"), "type": "MULTIPLE_CHOICE", "template_code": "", "test_cases": "[]", "options": {"A": "BEGIN / COMMIT / ROLLBACK", "B": "SELECT / FROM / WHERE", "C": "GRANT / REVOKE", "D": "COPY / CALL"}, "correct_option": "A", "hint_text": staged_sql_hint("transactions", f"트랜잭션 판단 {i}")})
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
        concepts = {
            row.name: row
            for row in db.scalars(select(Concept).where(Concept.domain == "SQL")).all()
        }
        existing = {seed_key(row.title): row for row in db.scalars(select(Task).where(Task.title.startswith(SEED_PREFIX))).all()}
        created = updated = 0
        for data in build_tasks():
            concept_name = data.pop("concept").removeprefix("SQL:")
            concept = concepts.get(concept_name)
            if concept is None:
                concept = Concept(domain="SQL", name=concept_name)
                db.add(concept)
                db.flush()
                concepts[concept_name] = concept
            values = {**data, "concept_id": concept.id, "is_active": True}
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

"""Idempotently replace benchmark rows and seed 150 Python learning tasks."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from sqlalchemy import delete, or_, select

from app.db.session import SessionLocal
from app.models.concept import Concept
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.models.user_proficiency import UserProficiency
from app.modules.learning.proficiency import update_proficiency

SEED_PREFIX = "[SAMPLE:PYTHON:"
BENCHMARK_MARKERS = ("[BENCHMARK]", "BENCHMARK:", "LOAD TEST:", "PERF TEST:")
VARIANTS = (
    ("기본기", "먼저 작은 예제로 정확한 기본 동작을 확인합니다."),
    ("데이터 정리", "학습 기록을 정리하는 상황에 적용합니다."),
    ("게임 점수", "게임 점수 데이터를 처리하는 상황에 적용합니다."),
    ("상점 통계", "상점 주문 정보를 계산하는 상황에 적용합니다."),
    ("경계값", "조건의 경계와 예외적인 값을 놓치지 않도록 풉니다."),
)

PYTHON_CONCEPTS = {
    "PYTHON:basics",
    "PYTHON:conditionals",
    "PYTHON:loops",
    "PYTHON:strings",
    "PYTHON:collections",
    "PYTHON:functions",
    "PYTHON:exceptions",
}

LEGACY_CONCEPT_MAP = {
    "PYTHON:variables": "PYTHON:basics",
    "PYTHON:type_conversion": "PYTHON:basics",
    "PYTHON:boolean_logic": "PYTHON:conditionals",
    "PYTHON:tuples": "PYTHON:basics",
    "PYTHON:iteration": "PYTHON:loops",
    "PYTHON:nested_loops": "PYTHON:loops",
    "PYTHON:string_methods": "PYTHON:strings",
    "PYTHON:parsing": "PYTHON:strings",
    "PYTHON:state_machines": "PYTHON:strings",
    "PYTHON:lists": "PYTHON:collections",
    "PYTHON:list_comprehensions": "PYTHON:collections",
    "PYTHON:sets": "PYTHON:collections",
    "PYTHON:dictionaries": "PYTHON:collections",
    "PYTHON:sorting": "PYTHON:collections",
    "PYTHON:search": "PYTHON:collections",
    "PYTHON:two_pointers": "PYTHON:collections",
    "PYTHON:aggregation": "PYTHON:collections",
    "PYTHON:data_modeling": "PYTHON:collections",
    "PYTHON:graph_basics": "PYTHON:collections",
    "PYTHON:algorithms": "PYTHON:functions",
    "PYTHON:recursion": "PYTHON:functions",
    "PYTHON:dynamic_programming": "PYTHON:functions",
}


@dataclass(frozen=True)
class Spec:
    concept: str
    title: str
    prompt: str
    hint: str
    operation: str


BRONZE = [
    Spec("basics", "두 수의 합", "두 정수 a, b를 읽고 합을 출력하세요.", "+ 연산자를 사용하세요.", "sum"),
    Spec("strings", "문자열 길이", "문자열 한 줄을 읽고 글자 수를 출력하세요.", "len을 사용하세요.", "length"),
    Spec("conditionals", "짝수 판별", "정수 하나를 읽고 짝수면 YES, 아니면 NO를 출력하세요.", "% 2를 확인하세요.", "even"),
    Spec("loops", "1부터 N까지", "N을 읽고 1부터 N까지의 합을 출력하세요.", "range 또는 등차수열을 쓰세요.", "range_sum"),
    Spec("collections", "리스트 최댓값", "공백으로 구분된 정수 목록의 최댓값을 출력하세요.", "max를 사용할 수 있습니다.", "max"),
    Spec("basics", "좌표 거리", "x와 y를 읽어 원점과의 맨해튼 거리를 출력하세요.", "좌표를 튜플로 묶어도 됩니다.", "manhattan"),
    Spec("collections", "중복 제거 개수", "공백으로 구분된 값에서 서로 다른 값의 개수를 출력하세요.", "set을 사용하세요.", "unique"),
    Spec("collections", "단어 빈도", "공백으로 구분된 단어 중 첫 단어가 나온 횟수를 출력하세요.", "dict로 빈도를 세어보세요.", "frequency"),
    Spec("basics", "섭씨 정수 변환", "실수 문자열 하나를 읽고 소수점을 버린 정수를 출력하세요.", "float 다음 int를 적용하세요.", "truncate"),
    Spec("conditionals", "범위 안인지 확인", "정수 n을 읽고 1 이상 100 이하면 YES를 출력하세요.", "비교 연산을 연결할 수 있습니다.", "range_check"),
]

SILVER = [
    Spec("collections", "짝수 제곱 합", "정수 목록에서 짝수의 제곱 합을 출력하세요.", "필터와 변환을 함께 적용하세요.", "even_square_sum"),
    Spec("strings", "정규화한 단어 수", "문장을 소문자로 바꾼 뒤 공백 기준 단어 수를 출력하세요.", "lower와 split을 조합하세요.", "word_count"),
    Spec("collections", "두 번째로 큰 수", "중복을 제거한 정수 목록에서 두 번째로 큰 수를 출력하세요.", "set과 sorted를 조합하세요.", "second_largest"),
    Spec("collections", "최빈 문자", "소문자 단어에서 가장 자주 나온 문자를 출력하세요. 동률이면 알파벳순입니다.", "빈도와 정렬 기준을 함께 생각하세요.", "mode_char"),
    Spec("loops", "약수 개수", "양의 정수 N의 약수 개수를 출력하세요.", "1부터 N까지 나누어 보세요.", "divisor_count"),
    Spec("functions", "안전한 평균", "정수 목록의 평균을 소수 둘째 자리까지 출력하세요.", "합계와 길이를 함수로 분리하세요.", "average"),
    Spec("exceptions", "안전한 나눗셈", "a와 b를 읽고 몫을 출력하되 b가 0이면 ZERO를 출력하세요.", "0인 경우를 먼저 처리하세요.", "safe_div"),
    Spec("collections", "교집합 정렬", "두 줄의 정수 목록에 공통인 수를 오름차순으로 출력하세요.", "집합 교집합 뒤 정렬하세요.", "intersection"),
    Spec("loops", "연속 증가 길이", "정수 목록에서 처음부터 연속으로 증가하는 구간 길이를 출력하세요.", "이전 값과 비교하세요.", "increasing_prefix"),
    Spec("strings", "키-값 합계", "공백으로 구분된 key:value 항목들의 value 합을 출력하세요.", "':'로 한 번 분리하세요.", "kv_sum"),
]

GOLD = [
    Spec("functions", "회문 함수", "is_palindrome(text) 함수를 작성하고 입력 문자열의 결과를 YES/NO로 출력하세요.", "비교용 문자열을 뒤집어 보세요.", "palindrome"),
    Spec("functions", "괄호 균형", "is_balanced(text) 함수를 작성해 괄호가 올바르면 YES를 출력하세요.", "스택을 사용하세요.", "balanced"),
    Spec("functions", "계단 경우의 수", "ways(n) 함수를 작성해 1칸 또는 2칸씩 N칸을 오르는 경우의 수를 출력하세요.", "이전 두 값을 저장하세요.", "stairs"),
    Spec("collections", "이진 탐색 위치", "search(values, target) 함수로 정렬 목록의 target 인덱스를 출력하세요. 없으면 -1입니다.", "탐색 범위를 절반씩 줄이세요.", "binary_search"),
    Spec("collections", "학생별 최고점", "name:score 목록에서 학생별 최고점 합계를 출력하세요.", "이름별 최대값을 dict에 저장하세요.", "best_scores"),
    Spec("functions", "최대공약수", "gcd(a, b) 함수를 작성해 최대공약수를 출력하세요.", "유클리드 호제법을 사용하세요.", "gcd"),
    Spec("collections", "목표 합 쌍", "정수 목록과 target을 읽고 합이 target인 서로 다른 인덱스 쌍의 수를 출력하세요.", "정렬 또는 해시 집합을 고려하세요.", "pair_sum"),
    Spec("collections", "구간 합 질의", "정수 목록과 l, r을 읽고 l부터 r까지(0-based, 양 끝 포함) 합을 출력하세요.", "누적 합 함수를 작성하세요.", "range_total"),
    Spec("collections", "연결 요소 크기", "간선 목록과 시작점을 읽고 시작점에서 도달 가능한 정점 수를 출력하세요.", "인접 목록과 DFS/BFS를 사용하세요.", "reachable"),
    Spec("strings", "연속 문자 압축", "encode(text) 함수를 작성해 aaabb를 a3b2처럼 압축해 출력하세요.", "현재 문자와 개수를 유지하세요.", "run_length"),
]


def cases(operation: str, variant: int) -> list[dict[str, str]]:
    data = {
        "sum": [(f"{variant} {variant + 2}\n", f"{variant * 2 + 2}\n")],
        "length": [("codex\n", "5\n")], "even": [(f"{variant + 2}\n", "YES\n" if (variant + 2) % 2 == 0 else "NO\n")],
        "range_sum": [(f"{variant + 3}\n", f"{sum(range(1, variant + 4))}\n")],
        "max": [(f"{variant} 9 -2 4\n", "9\n")], "manhattan": [(f"-{variant} {variant + 1}\n", f"{variant * 2 + 1}\n")],
        "unique": [("a b a c b\n", "3\n")], "frequency": [("cat dog cat bird cat\n", "3\n")],
        "truncate": [(f"{variant}.75\n", f"{variant}\n")], "range_check": [(f"{variant * 20}\n", "YES\n" if variant * 20 <= 100 else "NO\n")],
        "even_square_sum": [("1 2 3 4\n", "20\n")], "word_count": [("Hello Python World\n", "3\n")],
        "second_largest": [("4 9 9 2 7\n", "7\n")], "mode_char": [("banana\n", "a\n")],
        "divisor_count": [("12\n", "6\n")], "average": [("2 4 6 8\n", "5.00\n")],
        "safe_div": [("8 0\n", "ZERO\n"), ("9 3\n", "3\n")], "intersection": [("1 4 2 8\n2 3 4\n", "2 4\n")],
        "increasing_prefix": [("1 3 8 7 9\n", "3\n")], "kv_sum": [("a:2 b:7 c:-1\n", "8\n")],
        "palindrome": [("level\n", "YES\n"), ("python\n", "NO\n")], "balanced": [("(()())\n", "YES\n"), ("(()\n", "NO\n")],
        "stairs": [("5\n", "8\n")], "binary_search": [("1 3 5 7 9\n7\n", "3\n")],
        "best_scores": [("amy:8 bob:7 amy:10 bob:9\n", "19\n")], "gcd": [("48 18\n", "6\n")],
        "pair_sum": [("1 2 3 4 5\n6\n", "2\n")], "range_total": [("2 4 6 8 10\n1 3\n", "18\n")],
        "reachable": [("5 3\n0 1\n1 2\n3 4\n0\n", "3\n")], "run_length": [("aaabbc\n", "a3b2c1\n")],
    }
    return [{"input": item[0], "expected_output": item[1]} for item in data[operation]]


def build_tasks() -> list[dict]:
    rows = []
    for difficulty, specs in (("BRONZE", BRONZE), ("SILVER", SILVER), ("GOLD", GOLD)):
        for variant in range(1, 6):
            for spec in specs:
                local_number = (variant - 1) * 10 + specs.index(spec) + 1
                is_choice = difficulty == "BRONZE" and local_number % 2 == 0
                variant_title, variant_context = VARIANTS[variant - 1]
                options = ({
                    "A": spec.hint,
                    "B": "항상 외부 패키지를 설치해야만 해결할 수 있습니다.",
                    "C": "입력값은 확인하지 않고 고정 문자열만 출력하면 됩니다.",
                    "D": "이 문제는 Python으로 표현할 수 없습니다.",
                } if is_choice else None)
                prompt = (
                    f"[학습 목표] {spec.title}\n\n[상황] {variant_context}\n\n"
                    "[문제] 가장 올바른 설명을 고르세요. 오답은 실행 환경과 입력 조건을 "
                    "임의로 가정한 설명입니다."
                    if is_choice else
                    f"[학습 목표] {spec.title}\n\n[상황] {variant_context}\n\n"
                    f"[문제] {spec.prompt}\n\n[제약] 표준 입력만 읽고 표준 출력에 정답만 "
                    "출력하세요. 입력 형식과 줄바꿈을 정확히 지켜야 합니다."
                )
                rows.append({
                    "title": f"{SEED_PREFIX}{difficulty}:{local_number:03d}] {spec.title} - {variant_title}",
                    "concept": f"PYTHON:{spec.concept}", "difficulty": difficulty,
                    "type": "MULTIPLE_CHOICE" if is_choice else "CODE", "description": prompt,
                    "template_code": "" if is_choice else (
                        "def solve() -> None:\n"
                        "    # 입력을 읽고 정답을 출력하세요.\n"
                        "    pass\n\n"
                        "if __name__ == '__main__':\n"
                        "    solve()\n"
                    ),
                    "test_cases": "[]" if is_choice else json.dumps(cases(spec.operation, variant), ensure_ascii=False),
                    "options": options, "correct_option": "A" if is_choice else None,
                    "hint_text": spec.hint,
                })
    assert len(rows) == 150
    assert {d: sum(row["difficulty"] == d for row in rows) for d in ("BRONZE", "SILVER", "GOLD")} == {"BRONZE": 50, "SILVER": 50, "GOLD": 50}
    return rows


def cleanup_benchmarks(db) -> int:
    task_ids = db.scalars(select(Task.id).where(or_(
        *(Task.title.startswith(marker) for marker in BENCHMARK_MARKERS)
    ))).all()
    if not task_ids:
        return 0
    db.execute(delete(TaskAttempt).where(TaskAttempt.task_id.in_(task_ids)))
    db.execute(delete(Task).where(Task.id.in_(task_ids)))
    return len(task_ids)


def seed_key(title: str) -> str:
    return title.partition("]")[0] + "]"


def consolidate_legacy_concepts(db, concepts: dict[str, Concept]) -> int:
    affected: set[tuple[int, int]] = set()
    removed = 0
    for legacy_name, target_name in LEGACY_CONCEPT_MAP.items():
        legacy = concepts.get(legacy_name)
        target = concepts.get(target_name)
        if legacy is None or target is None or legacy.id == target.id:
            continue
        for task in db.scalars(select(Task).where(Task.concept_id == legacy.id)):
            task.concept_id = target.id
        proficiency_rows = db.scalars(
            select(UserProficiency).where(UserProficiency.concept_id == legacy.id)
        ).all()
        for row in proficiency_rows:
            affected.add((row.user_id, target.id))
            db.delete(row)
        db.flush()
        db.delete(legacy)
        removed += 1
    db.flush()
    for user_id, concept_id in affected:
        update_proficiency(db, user_id, concept_id)
    return removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--cleanup-only", action="store_true")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        removed = cleanup_benchmarks(db)
        created = updated = consolidated = 0
        if not args.cleanup_only:
            concepts = {row.name: row for row in db.scalars(select(Concept)).all()}
            existing = {
                seed_key(row.title): row
                for row in db.scalars(select(Task).where(Task.title.startswith(SEED_PREFIX))).all()
            }
            for data in build_tasks():
                concept = concepts.get(data["concept"])
                if concept is None:
                    concept = Concept(name=data["concept"])
                    db.add(concept)
                    db.flush()
                    concepts[concept.name] = concept
                row = existing.get(seed_key(data["title"]))
                values = {key: value for key, value in data.items() if key != "concept"}
                values.update(concept_id=concept.id, domain="PYTHON", is_active=True)
                if row is None:
                    db.add(Task(**values)); created += 1
                else:
                    for key, value in values.items(): setattr(row, key, value)
                    updated += 1
            db.flush()
            consolidated = consolidate_legacy_concepts(db, concepts)
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        print({
            "benchmark_tasks_removed": removed,
            "created": created,
            "updated": updated,
            "legacy_concepts_removed": consolidated,
            "dry_run": args.dry_run,
        })
    finally:
        db.close()


if __name__ == "__main__":
    main()

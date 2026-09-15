"""Idempotently replace benchmark rows and seed 150 Python learning tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import textwrap
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
    ("치즈의 첫 심부름", "아기 고양이 치즈가 처음 맡은 심부름이에요. 차근차근 도와주세요, 야옹!"),
    ("나비의 기록 정리", "꼼꼼한 나비가 흩어진 학습 기록을 정리하고 있어요. 발바닥 도장을 받을 수 있게 도와주세요."),
    ("보리의 놀이 점수", "보리가 신나게 놀고 받은 점수를 세다가 수염이 꼬였어요. 정확한 답을 알려주세요!"),
    ("코코의 간식 준비", "코코가 친구들과 나눌 간식을 준비하고 있어요. 간식 시간이 늦지 않도록 도와주세요."),
    ("모카의 수상한 상자", "호기심 많은 모카가 상자 속 경계값을 발견했어요. 빠뜨리는 값 없이 확인해 주세요, 야옹~"),
)

STORIES = {
    "sum": "츄르를 먹고 싶은데 두 주머니에 모은 돈이 모두 얼마인지 모르겠어요. 두 금액을 더해 주세요.",
    "length": "목걸이 이름표를 만들려고 해요. 새길 글자가 몇 개인지 세어 주세요.",
    "even": "리본을 두 개씩 짝지어 달고 싶어요. 짝수인지 확인해 주세요.",
    "range_sum": "캣타워 놀이를 마칠 때마다 1점부터 차례로 점수를 받았어요. 누적 점수를 세어 주세요.",
    "max": "장난감 놀이 점수판에 음수인 벌점도 있어요. 가장 높은 기록을 찾아 주세요.",
    "manhattan": "방석에서 장난감까지 격자를 따라 이동하려고 해요. 가로와 세로 이동 거리를 합쳐 주세요.",
    "unique": "간식 상자에 붙은 이름표가 섞였어요. 서로 다른 이름표가 몇 종류인지 알려 주세요.",
    "frequency": "친구들의 간식 신청 메모에서 첫 번째 단어가 몇 번 나오는지 궁금해요.",
    "truncate": "고양이용 우유의 온도 기록을 정리하려고 해요. 소수 부분을 버린 온도를 알려 주세요.",
    "range_check": "간식 할인 쿠폰 번호는 1부터 100까지만 유효해요. 사용할 수 있는 번호인지 확인해 주세요.",
    "even_square_sum": "장난감 게임의 짝수 점수만 제곱해 보너스로 합산하려고 해요.",
    "word_count": "간식 주문 메모의 대소문자를 통일하고 단어가 몇 개인지 세고 싶어요.",
    "second_largest": "캣타워 놀이 점수에서 중복 기록을 빼고 두 번째로 높은 점수를 찾아 주세요.",
    "mode_char": "리본에 찍을 문자 도장을 고르고 있어요. 가장 자주 나온 문자를 찾아 주세요.",
    "divisor_count": "간식을 같은 수씩 나누어 포장하려고 해요. 남김없이 나눌 수 있는 수가 몇 개인지 세어 주세요.",
    "average": "고양이용 우유를 준비하며 친구들이 적은 수량의 평균을 알고 싶어요.",
    "safe_div": "간식을 같은 수씩 나누고 싶은데 친구 수가 0으로 적힌 기록도 있어요. 안전하게 계산해 주세요.",
    "intersection": "두 친구의 장난감 희망 목록에서 공통 번호를 정렬해 주세요.",
    "increasing_prefix": "놀이 점수가 처음부터 계속 오른 구간이 얼마나 긴지 궁금해요.",
    "kv_sum": "간식 장부에 구매액과 음수인 할인액이 함께 적혀 있어요. 금액을 모두 더해 주세요.",
    "palindrome": "목걸이 이름을 거꾸로 읽어도 같은지 확인하는 함수를 만들어 주세요.",
    "balanced": "장난감 포장 메모의 괄호가 제대로 닫혔는지 확인하는 함수를 만들어 주세요.",
    "stairs": "캣타워 계단을 한 칸이나 두 칸씩 올라가려고 해요. 올라가는 방법을 세어 주세요.",
    "binary_search": "정렬된 장난감 번호 목록에서 원하는 번호가 있는 위치를 빨리 찾고 싶어요.",
    "best_scores": "고양이 학교 놀이 대회의 학생별 최고 점수를 모아 합산하려고 해요.",
    "gcd": "두 종류의 간식을 같은 크기의 묶음으로 나누려고 해요. 공통으로 나눌 가장 큰 수를 찾아 주세요.",
    "pair_sum": "간식 교환 점수 두 개를 합쳐 목표 점수를 만들고 싶어요. 가능한 쌍을 세어 주세요.",
    "range_total": "여러 날의 우유 주문 수량 중 지정한 기간의 합계를 알고 싶어요.",
    "reachable": "고양이 놀이터의 길 지도를 보고 지금 위치에서 갈 수 있는 장소를 세어 주세요.",
    "run_length": "리본 무늬 기록에서 연속된 같은 문자를 짧게 묶어 적고 싶어요.",
}

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
    Spec("basics", "두 수의 합", "공백으로 구분된 정수 a, b를 한 줄로 입력받으세요. 두 수를 더한 값을 출력하세요.", "+ 연산자를 사용하세요.", "sum"),
    Spec("strings", "문자열 길이", "문자열 한 줄을 입력받으세요. 그 문자열의 글자 수를 세어 출력하세요.", "len을 사용하세요.", "length"),
    Spec("conditionals", "짝수 판별", "정수 하나를 한 줄로 입력받으세요. 그 수가 짝수이면 `야옹~`을, 홀수이면 `갸우뚱...`을 출력하세요.", "% 2를 확인하세요.", "even"),
    Spec("loops", "1부터 N까지", "정수 N을 한 줄로 입력받으세요. 1부터 N까지의 정수를 모두 더한 값을 출력하세요.", "range 또는 등차수열을 쓰세요.", "range_sum"),
    Spec("collections", "리스트 최댓값", "공백으로 구분된 정수 여러 개를 한 줄로 입력받으세요. 그중 가장 큰 값을 출력하세요.", "max를 사용할 수 있습니다.", "max"),
    Spec("basics", "좌표 거리", "공백으로 구분된 정수 x, y를 한 줄로 입력받으세요. 원점(0, 0)에서 좌표 (x, y)까지의 거리(|x| + |y|)를 출력하세요.", "좌표를 튜플로 묶어도 됩니다.", "manhattan"),
    Spec("collections", "중복 제거 개수", "공백으로 구분된 값 여러 개를 한 줄로 입력받으세요. 그중 서로 다른(중복이 아닌) 값이 몇 종류인지 출력하세요.", "set을 사용하세요.", "unique"),
    Spec("collections", "단어 빈도", "공백으로 구분된 단어 여러 개를 한 줄로 입력받으세요. 첫 번째 단어가 전체에서 몇 번 나오는지 출력하세요.", "dict로 빈도를 세어보세요.", "frequency"),
    Spec("basics", "섭씨 정수 변환", "실수(소수) 하나를 한 줄로 입력받으세요. 소수점 아래를 버리고 정수 부분만 출력하세요.", "float 다음 int를 적용하세요.", "truncate"),
    Spec("conditionals", "범위 안인지 확인", "정수 n을 한 줄로 입력받으세요. n이 1 이상 100 이하이면 `야옹~`을, 그 범위를 벗어나면 `상자 밖!`을 출력하세요.", "비교 연산을 연결할 수 있습니다.", "range_check"),
]

SILVER = [
    Spec("collections", "짝수 제곱 합", "공백으로 구분된 정수 여러 개를 한 줄로 입력받으세요. 그중 짝수만 골라 각각 제곱한 값을 모두 더해 출력하세요.", "필터와 변환을 함께 적용하세요.", "even_square_sum"),
    Spec("strings", "정규화한 단어 수", "문장 한 줄을 입력받으세요. 전체를 소문자로 바꾼 뒤, 공백으로 구분된 단어의 개수를 출력하세요.", "lower와 split을 조합하세요.", "word_count"),
    Spec("collections", "두 번째로 큰 수", "공백으로 구분된 정수 여러 개를 한 줄로 입력받으세요. 중복된 값을 제거한 뒤, 그중 두 번째로 큰 값을 출력하세요.", "set과 sorted를 조합하세요.", "second_largest"),
    Spec("collections", "최빈 문자", "소문자로만 이루어진 단어 하나를 한 줄로 입력받으세요. 그 단어에서 가장 자주 나온 글자를 출력하세요. 여러 글자가 같은 횟수로 나오면 알파벳 순서가 빠른 글자를 출력하세요.", "빈도와 정렬 기준을 함께 생각하세요.", "mode_char"),
    Spec("loops", "약수 개수", "양의 정수 N을 한 줄로 입력받으세요. N을 나머지 없이 나누어떨어지게 하는 약수가 몇 개인지 출력하세요.", "1부터 N까지 나누어 보세요.", "divisor_count"),
    Spec("functions", "안전한 평균", "공백으로 구분된 정수 여러 개를 한 줄로 입력받으세요. 그 평균값을 소수점 둘째 자리까지 출력하세요.", "합계와 길이를 함수로 분리하세요.", "average"),
    Spec("exceptions", "안전한 나눗셈", "공백으로 구분된 정수 a, b를 한 줄로 입력받으세요. a를 b로 나눈 몫(정수 나눗셈)을 출력하되, b가 0이면 `ZERO`를 출력하세요.", "ZeroDivisionError를 처리하세요.", "safe_div"),
    Spec("collections", "교집합 정렬", "공백으로 구분된 정수 목록을 두 줄에 걸쳐 입력받으세요. 두 줄에 공통으로 들어있는 값을 오름차순으로 정렬해 공백으로 구분해 출력하세요.", "집합 교집합 뒤 정렬하세요.", "intersection"),
    Spec("loops", "연속 증가 길이", "공백으로 구분된 정수 여러 개를 한 줄로 입력받으세요. 맨 앞에서부터 바로 앞 값보다 큰 상태가 계속 이어지는 구간의 길이(개수)를 출력하세요.", "이전 값과 비교하세요.", "increasing_prefix"),
    Spec("strings", "키-값 합계", "`이름:값` 형태의 항목이 공백으로 구분되어 한 줄로 입력됩니다(예: a:2 b:7). 콜론(:) 뒤에 있는 값들을 모두 더해 출력하세요.", "':'로 한 번 분리하세요.", "kv_sum"),
]

GOLD = [
    Spec("functions", "회문 함수", "문자열 한 줄을 입력받으세요. 앞뒤로 읽어도 같은 문자열(회문)인지 판별하는 함수를 작성해 활용하고, 회문이면 `YES`, 아니면 `NO`를 출력하세요.", "비교용 문자열을 뒤집어 보세요.", "palindrome"),
    Spec("functions", "괄호 균형", "괄호 문자열 하나를 한 줄로 입력받으세요. 여는 괄호와 닫는 괄호의 짝이 순서대로 모두 맞는지 판별하는 함수를 작성해 활용하고, 짝이 맞으면 `YES`, 아니면 `NO`를 출력하세요.", "스택을 사용하세요.", "balanced"),
    Spec("functions", "계단 경우의 수", "정수 N을 한 줄로 입력받으세요. 한 번에 1칸 또는 2칸씩 올라가 총 N칸을 오르는 방법이 몇 가지인지 계산하는 함수를 작성해 활용하고 그 값을 출력하세요.", "이전 두 값을 저장하세요.", "stairs"),
    Spec("collections", "이진 탐색 위치", "오름차순으로 정렬된 정수 목록을 첫 줄에, 찾을 값(target)을 둘째 줄에 입력받으세요. 이진 탐색으로 target의 인덱스(0부터 시작)를 찾는 함수를 작성해 활용하고, 목록에 없으면 -1을 출력하세요.", "탐색 범위를 절반씩 줄이세요.", "binary_search"),
    Spec("collections", "학생별 최고점", "`이름:점수` 형태의 기록이 공백으로 구분되어 한 줄로 입력됩니다(같은 이름이 여러 번 나올 수 있습니다). 이름별로 가장 높은 점수를 찾은 뒤, 그 최고 점수들을 모두 더해 출력하세요.", "이름별 최대값을 dict에 저장하세요.", "best_scores"),
    Spec("functions", "최대공약수", "공백으로 구분된 정수 a, b를 한 줄로 입력받으세요. 두 수를 모두 나누어떨어지게 하는 가장 큰 수(최대공약수)를 계산하는 함수를 작성해 활용하고 그 값을 출력하세요.", "유클리드 호제법을 사용하세요.", "gcd"),
    Spec("collections", "목표 합 쌍", "정수 목록을 첫 줄에, 목표 합(target)을 둘째 줄에 입력받으세요. 목록에서 서로 다른 두 위치를 골라 더했을 때 합이 target이 되는 쌍이 몇 개인지 출력하세요.", "정렬 또는 해시 집합을 고려하세요.", "pair_sum"),
    Spec("collections", "구간 합 질의", "정수 목록을 첫 줄에, 공백으로 구분된 두 정수 l과 r을 둘째 줄에 입력받으세요. 목록의 인덱스는 0부터 시작하며, l번째부터 r번째까지(양 끝 포함) 값의 합을 출력하세요.", "누적 합 함수를 작성하세요.", "range_total"),
    Spec("collections", "연결 요소 크기", "첫 줄에 정점 수와 간선 수를 입력받고, 이어서 그 수만큼의 줄에 걸쳐 간선을 이루는 두 정점 번호를 입력받습니다. 마지막 줄에는 출발 정점 번호가 주어집니다. 출발 정점에서 간선을 따라 도달할 수 있는 정점이 (자기 자신을 포함해) 모두 몇 개인지 출력하세요.", "인접 목록과 DFS/BFS를 사용하세요.", "reachable"),
    Spec("strings", "연속 문자 압축", "문자열 하나를 한 줄로 입력받으세요. 연속으로 같은 문자가 반복되는 구간을 `문자+개수`로 압축하는 encode(text) 함수를 작성해 활용하고 그 결과를 출력하세요(예: aaabb → a3b2).", "현재 문자와 개수를 유지하세요.", "run_length"),
]

DIRECT_HINTS = {
    "sum": "`map(int, input().split())`으로 두 수를 읽고 `+` 결과를 출력하세요.",
    "length": "`input()`으로 문자열 한 줄을 읽고 `len(문자열)`을 출력하세요.",
    "even": "정수를 읽은 뒤 `n % 2 == 0`을 조건으로 두 문장 중 하나를 출력하세요.",
    "range_sum": "`range(1, n + 1)`로 1부터 N까지 만들고 `sum(...)` 결과를 출력하세요.",
    "max": "한 줄을 `map(int, input().split())`으로 바꾼 뒤 `max(...)`를 사용하세요.",
    "manhattan": "x와 y를 정수로 읽고 원점까지의 거리인 `abs(x) + abs(y)`를 출력하세요.",
    "unique": "입력값을 `split()`한 뒤 `set(...)`으로 중복을 없애고 `len(...)`으로 세세요.",
    "frequency": "단어 목록의 첫 값을 저장하고 `count(...)` 또는 딕셔너리로 등장 횟수를 세세요.",
    "truncate": "입력 문자열을 먼저 `float`로 바꾸고, 그 결과를 `int`로 바꿔 출력하세요.",
    "range_check": "`1 <= n <= 100` 조건이 참인지 확인해 요구된 두 문장 중 하나를 출력하세요.",
    "even_square_sum": "목록을 순회하며 `n % 2 == 0`인 값만 `n ** 2`로 바꿔 합치세요.",
    "word_count": "문장을 `lower()`로 통일하고 `split()`한 목록의 길이를 출력하세요.",
    "second_largest": "`set(...)`으로 중복을 없애고 정렬한 뒤 끝에서 두 번째 값을 고르세요.",
    "mode_char": "문자별 횟수를 센 뒤 `(-횟수, 문자)` 기준으로 정렬하면 동률은 알파벳순이 됩니다.",
    "divisor_count": "1부터 N까지 순회하며 `n % i == 0`일 때만 개수를 1씩 늘리세요.",
    "average": "정수 목록의 `sum(values) / len(values)`를 계산하고 `:.2f` 형식으로 출력하세요.",
    "safe_div": "`try`에서 `a // b`를 계산하고 `except ZeroDivisionError`에서 ZERO를 출력하세요.",
    "intersection": "두 줄을 각각 집합으로 바꿔 `&`로 교집합을 구하고 정렬해 출력하세요.",
    "increasing_prefix": "두 번째 값부터 이전 값과 비교하고, 증가하지 않는 순간 반복을 멈추세요.",
    "kv_sum": "각 항목을 `split(':', 1)`로 나누고 오른쪽 값을 정수로 바꿔 합치세요.",
    "palindrome": "판별 함수에서 문자열과 `text[::-1]`을 비교하고 결과에 따라 YES/NO를 출력하세요.",
    "balanced": "`(`는 스택에 넣고 `)`는 하나 꺼내세요. 중간에 꺼낼 값이 없거나 끝에 남으면 균형이 아닙니다.",
    "stairs": "첫 두 경우의 수를 저장하고, 다음 값은 직전 두 값의 합으로 갱신하세요.",
    "binary_search": "left와 right를 두고 mid 값을 target과 비교해 탐색 구간을 절반씩 줄이세요.",
    "best_scores": "name별 최고 score를 딕셔너리에 저장하고 마지막에 최고점 값들을 모두 더하세요.",
    "gcd": "b가 0이 될 때까지 `a, b = b, a % b`를 반복한 뒤 a를 출력하세요.",
    "pair_sum": "각 값을 보며 `target - value`가 앞서 본 집합에 있는지 확인하고 쌍의 수를 늘리세요.",
    "range_total": "누적 합 배열을 만들고 0-based 양 끝 포함 구간을 `prefix[r + 1] - prefix[l]`로 구하세요.",
    "reachable": "간선을 인접 목록에 넣고 시작점부터 DFS/BFS하며 방문한 정점 집합의 크기를 출력하세요.",
    "run_length": "현재 문자와 연속 개수를 유지하다 문자가 바뀔 때 `문자+개수`를 결과에 추가하세요.",
}

# Multiple-choice options are short programs, not computed outputs: the player has to read Python
# and recognise the working solution. Each distractor models one concrete beginner mistake for that
# operation (wrong operator, missing int(), off-by-one, swapped branches, ...) and several of them
# would raise at runtime - that is intentional, the player reasons about the code instead of running
# it. Options describe the operation's logic, so they do not depend on the story variant.
_RAW_CODE_OPTIONS: dict[str, tuple[str, list[str]]] = {
    "sum": (
        """
        a, b = map(int, input().split())
        print(a + b)
        """,
        [
            # subtracts instead of adding
            """
            a, b = map(int, input().split())
            print(a - b)
            """,
            # no int(), so + joins the two pieces of text
            """
            a, b = input().split()
            print(a + b)
            """,
            # off-by-one
            """
            a, b = map(int, input().split())
            print(a + b + 1)
            """,
        ],
    ),
    "length": (
        """
        text = input()
        print(len(text))
        """,
        [
            # counts words instead of letters
            """
            text = input()
            print(len(text.split()))
            """,
            # off-by-one
            """
            text = input()
            print(len(text) - 1)
            """,
            # len is a built-in function, not a string method
            """
            text = input()
            print(text.len())
            """,
        ],
    ),
    "even": (
        """
        n = int(input())
        print("야옹~" if n % 2 == 0 else "갸우뚱...")
        """,
        [
            # even and odd branches swapped
            """
            n = int(input())
            print("야옹~" if n % 2 == 1 else "갸우뚱...")
            """,
            # // instead of %
            """
            n = int(input())
            print("야옹~" if n // 2 == 0 else "갸우뚱...")
            """,
            # no int(), so % on text raises TypeError
            """
            n = input()
            print("야옹~" if n % 2 == 0 else "갸우뚱...")
            """,
        ],
    ),
    "range_sum": (
        """
        n = int(input())
        print(sum(range(1, n + 1)))
        """,
        [
            # range stops before n, so N itself is left out
            """
            n = int(input())
            print(sum(range(1, n)))
            """,
            # no int(), so range gets a string
            """
            n = input()
            print(sum(range(1, n + 1)))
            """,
            # / makes the formula a float, printing 15.0 instead of 15
            """
            n = int(input())
            print(n * (n + 1) / 2)
            """,
        ],
    ),
    "max": (
        """
        nums = list(map(int, input().split()))
        print(max(nums))
        """,
        [
            # smallest instead of largest
            """
            nums = list(map(int, input().split()))
            print(min(nums))
            """,
            # adds the values instead of picking the largest
            """
            nums = list(map(int, input().split()))
            print(sum(nums))
            """,
            # forgot to index, so the whole sorted list is printed
            """
            nums = list(map(int, input().split()))
            print(sorted(nums, reverse=True))
            """,
        ],
    ),
    "manhattan": (
        """
        x, y = map(int, input().split())
        print(abs(x) + abs(y))
        """,
        [
            # forgot abs, so a negative coordinate shrinks the distance
            """
            x, y = map(int, input().split())
            print(x + y)
            """,
            # abs applied to the sum instead of to each coordinate
            """
            x, y = map(int, input().split())
            print(abs(x + y))
            """,
            # straight-line distance instead of grid distance
            """
            x, y = map(int, input().split())
            print((x ** 2 + y ** 2) ** 0.5)
            """,
        ],
    ),
    "unique": (
        """
        values = input().split()
        print(len(set(values)))
        """,
        [
            # counts every value, duplicates included
            """
            values = input().split()
            print(len(values))
            """,
            # forgot split, so it counts distinct characters
            """
            values = input()
            print(len(set(values)))
            """,
            # prints the set itself instead of how many items it holds
            """
            values = input().split()
            print(set(values))
            """,
        ],
    ),
    "frequency": (
        """
        words = input().split()
        print(words.count(words[0]))
        """,
        [
            # counts how many words there are in total
            """
            words = input().split()
            print(len(words))
            """,
            # counts the second word, reading index 1 as "the first one"
            """
            words = input().split()
            print(words.count(words[1]))
            """,
            # the comparison is inverted, so it counts every other word
            """
            words = input().split()
            print(sum(1 for w in words if w != words[0]))
            """,
        ],
    ),
    "truncate": (
        """
        value = float(input())
        print(int(value))
        """,
        [
            # rounds instead of dropping the decimals
            """
            value = float(input())
            print(round(value))
            """,
            # int() cannot parse "21.75" directly
            """
            print(int(input()))
            """,
            # prints the number unchanged
            """
            value = float(input())
            print(value)
            """,
        ],
    ),
    "range_check": (
        """
        n = int(input())
        print("야옹~" if 1 <= n <= 100 else "상자 밖!")
        """,
        [
            # excludes 1 and 100 themselves
            """
            n = int(input())
            print("야옹~" if 1 < n < 100 else "상자 밖!")
            """,
            # or instead of and, so every number passes
            """
            n = int(input())
            print("야옹~" if n >= 1 or n <= 100 else "상자 밖!")
            """,
            # the two messages are the wrong way round
            """
            n = int(input())
            print("상자 밖!" if 1 <= n <= 100 else "야옹~")
            """,
        ],
    ),
    "even_square_sum": (
        """
        nums = list(map(int, input().split()))
        print(sum(n ** 2 for n in nums if n % 2 == 0))
        """,
        [
            # keeps the odd values instead of the even ones
            """
            nums = list(map(int, input().split()))
            print(sum(n ** 2 for n in nums if n % 2 == 1))
            """,
            # doubles each value instead of squaring it
            """
            nums = list(map(int, input().split()))
            print(sum(n * 2 for n in nums if n % 2 == 0))
            """,
            # squares the total instead of squaring each value
            """
            nums = list(map(int, input().split()))
            print(sum(n for n in nums if n % 2 == 0) ** 2)
            """,
        ],
    ),
    "word_count": (
        """
        words = input().lower().split()
        print(len(words))
        """,
        [
            # counts characters instead of words
            """
            text = input().lower()
            print(len(text))
            """,
            # splits on commas, so a space-separated line stays in one piece
            """
            words = input().lower().split(",")
            print(len(words))
            """,
            # lower is never called, so split runs on a method object
            """
            words = input().lower.split()
            print(len(words))
            """,
        ],
    ),
    "second_largest": (
        """
        nums = sorted(set(map(int, input().split())))
        print(nums[-2])
        """,
        [
            # duplicates are kept, so a repeated top score wins twice
            """
            nums = sorted(map(int, input().split()))
            print(nums[-2])
            """,
            # second smallest instead of second largest
            """
            nums = sorted(set(map(int, input().split())))
            print(nums[1])
            """,
            # the largest value, not the second largest
            """
            nums = sorted(set(map(int, input().split())))
            print(nums[-1])
            """,
        ],
    ),
    "mode_char": (
        """
        text = input()
        print(min(set(text), key=lambda c: (-text.count(c), c)))
        """,
        [
            # picks the rarest character instead of the most frequent one
            """
            text = input()
            print(min(set(text), key=lambda c: (text.count(c), c)))
            """,
            # prints how many times it appeared instead of the character
            """
            text = input()
            print(max(text.count(c) for c in set(text)))
            """,
            # index() is where a character first appears, not how often it appears
            """
            text = input()
            print(max(set(text), key=lambda c: text.index(c)))
            """,
        ],
    ),
    "divisor_count": (
        """
        n = int(input())
        print(sum(1 for i in range(1, n + 1) if n % i == 0))
        """,
        [
            # range stops before n, so N itself is never counted
            """
            n = int(input())
            print(sum(1 for i in range(1, n) if n % i == 0))
            """,
            # starts at 0, so n % 0 raises ZeroDivisionError
            """
            n = int(input())
            print(sum(1 for i in range(0, n + 1) if n % i == 0))
            """,
            # adds the divisors up instead of counting them
            """
            n = int(input())
            print(sum(i for i in range(1, n + 1) if n % i == 0))
            """,
        ],
    ),
    "average": (
        """
        nums = list(map(int, input().split()))
        print(f"{sum(nums) / len(nums):.2f}")
        """,
        [
            # no formatting, so it prints 5.0 instead of 5.00
            """
            nums = list(map(int, input().split()))
            print(sum(nums) / len(nums))
            """,
            # divides by one value too few
            """
            nums = list(map(int, input().split()))
            print(f"{sum(nums) / (len(nums) - 1):.2f}")
            """,
            # no int(), so sum() is handed a list of text
            """
            nums = input().split()
            print(f"{sum(nums) / len(nums):.2f}")
            """,
        ],
    ),
    "safe_div": (
        """
        a, b = map(int, input().split())
        try:
            print(a // b)
        except ZeroDivisionError:
            print("ZERO")
        """,
        [
            # catches the wrong error, so dividing by 0 still crashes
            """
            a, b = map(int, input().split())
            try:
                print(a // b)
            except ValueError:
                print("ZERO")
            """,
            # / gives 3.0 where the problem asks for 3
            """
            a, b = map(int, input().split())
            try:
                print(a / b)
            except ZeroDivisionError:
                print("ZERO")
            """,
            # guards the wrong side of the division
            """
            a, b = map(int, input().split())
            print("ZERO" if a == 0 else a // b)
            """,
        ],
    ),
    "intersection": (
        """
        first = set(map(int, input().split()))
        second = set(map(int, input().split()))
        print(" ".join(map(str, sorted(first & second))))
        """,
        [
            # every value from both lines instead of the shared ones
            """
            first = set(map(int, input().split()))
            second = set(map(int, input().split()))
            print(" ".join(map(str, sorted(first | second))))
            """,
            # prints the list itself, brackets and commas included
            """
            first = set(map(int, input().split()))
            second = set(map(int, input().split()))
            print(sorted(first & second))
            """,
            # values only on the first line instead of the shared ones
            """
            first = set(map(int, input().split()))
            second = set(map(int, input().split()))
            print(" ".join(map(str, sorted(first - second))))
            """,
        ],
    ),
    "increasing_prefix": (
        """
        nums = list(map(int, input().split()))
        count = 1
        while count < len(nums) and nums[count] > nums[count - 1]:
            count += 1
        print(count)
        """,
        [
            # starts counting at 0, so the first value is never counted
            """
            nums = list(map(int, input().split()))
            count = 0
            while count < len(nums) and nums[count] > nums[count - 1]:
                count += 1
            print(count)
            """,
            # compares the wrong way, measuring a decreasing run
            """
            nums = list(map(int, input().split()))
            count = 1
            while count < len(nums) and nums[count] < nums[count - 1]:
                count += 1
            print(count)
            """,
            # counts every rise in the list instead of stopping at the first drop
            """
            nums = list(map(int, input().split()))
            print(sum(1 for i in range(1, len(nums)) if nums[i] > nums[i - 1]) + 1)
            """,
        ],
    ),
    "kv_sum": (
        """
        items = input().split()
        print(sum(int(item.split(":", 1)[1]) for item in items))
        """,
        [
            # takes the name on the left of the colon instead of the value
            """
            items = input().split()
            print(sum(int(item.split(":", 1)[0]) for item in items))
            """,
            # no int(), so sum() is handed text
            """
            items = input().split()
            print(sum(item.split(":", 1)[1] for item in items))
            """,
            # splits the whole line on ':' instead of each item separately
            """
            parts = input().split(":")
            print(sum(int(p) for p in parts[1:]))
            """,
        ],
    ),
}

CODE_OPTIONS: dict[str, tuple[str, list[str]]] = {
    operation: (
        textwrap.dedent(correct).strip(),
        [textwrap.dedent(distractor).strip() for distractor in distractors],
    )
    for operation, (correct, distractors) in _RAW_CODE_OPTIONS.items()
}

CONCEPT_START_HINTS = {
    "basics": "`input()`으로 받은 값을 문제 순서대로 변수에 담고 필요한 숫자형으로 변환하세요.",
    "conditionals": "먼저 참과 거짓을 가르는 조건식을 한 줄로 적고 두 출력 경로를 나누세요.",
    "loops": "작은 입력을 손으로 써 본 뒤 반복할 범위와 반복 중 갱신할 값을 정하세요.",
    "strings": "입력 문자열의 공백과 대소문자를 어떻게 다룰지 먼저 정하세요.",
    "collections": "입력 목록에서 유지할 값과 빠르게 찾거나 셀 값을 구분해 알맞은 컬렉션을 고르세요.",
    "functions": "`def 함수명(매개변수):`로 함수를 정의하고 `return`한 값을 함수 호출로 사용하세요.",
    "exceptions": "오류가 날 수 있는 계산은 `try`에 두고 해당 예외를 `except`에서 처리하세요.",
}


def python_hint(spec: Spec) -> str:
    return "\n".join(
        (
            f"[시작] {CONCEPT_START_HINTS[spec.concept]}",
            f"[핵심] {DIRECT_HINTS[spec.operation]}",
            "[확인] 예시 입력을 직접 계산해 보고, `print`에는 설명 문장 없이 요구된 값만 출력하세요.",
        )
    )


def cases(operation: str, variant: int) -> list[dict[str, str]]:
    data = {
        "sum": [(f"{variant} {variant + 2}\n", f"{variant * 2 + 2}\n")],
        "length": [("야옹~\n", "3\n")], "even": [(f"{variant + 2}\n", "야옹~\n" if (variant + 2) % 2 == 0 else "갸우뚱...\n")],
        "range_sum": [(f"{variant + 3}\n", f"{sum(range(1, variant + 4))}\n")],
        "max": [(f"{variant} 9 -2 4\n", "9\n")], "manhattan": [(f"-{variant} {variant + 1}\n", f"{variant * 2 + 1}\n")],
        "unique": [("a b a c b\n", "3\n")], "frequency": [("cat dog cat bird cat\n", "3\n")],
        "truncate": [(f"{variant}.75\n", f"{variant}\n")], "range_check": [(f"{variant * 20}\n", "야옹~\n" if variant * 20 <= 100 else "상자 밖!\n")],
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


def _positioned_options(correct: str, distractors: list[str], seed: str) -> tuple[dict[str, str], str]:
    labels = ["A", "B", "C", "D"]
    correct_index = hashlib.sha256(seed.encode()).digest()[0] % len(labels)
    values = distractors[:3]
    values.insert(correct_index, correct)
    return dict(zip(labels, values, strict=True)), labels[correct_index]


def python_multiple_choice(spec: Spec, variant: int) -> tuple[str, dict[str, str], str]:
    correct, distractors = CODE_OPTIONS[spec.operation]
    if len({correct, *distractors}) != 4:
        raise ValueError(f"code options for {spec.operation} are not four distinct snippets")
    # Only the flavour text and the answer positions follow the variant; the code itself is the
    # operation's logic, which every variant of the same task shares.
    sample_input = cases(spec.operation, variant)[0]["input"].strip().replace("\n", "` / `")
    options, correct_option = _positioned_options(
        correct, list(distractors), f"{spec.operation}:{variant}"
    )
    prompt = (
        f"[도와주세요!] {VARIANTS[variant - 1][1]} {STORIES[spec.operation]}\n\n"
        f"[객관식 문제] {spec.prompt}\n"
        f"예시 입력은 `{sample_input}`이에요. "
        "다음 중 이 문제를 올바르게 해결하는 코드는 무엇인가요?"
    )
    return prompt, options, correct_option


def build_tasks() -> list[dict]:
    rows = []
    for difficulty, specs in (("BRONZE", BRONZE), ("SILVER", SILVER), ("GOLD", GOLD)):
        for variant in range(1, 6):
            for spec in specs:
                local_number = (variant - 1) * 10 + specs.index(spec) + 1
                variant_title, variant_context = VARIANTS[variant - 1]
                prompt = (
                    f"[도와주세요!] {variant_context} {STORIES[spec.operation]}\n\n"
                    f"[문제] {spec.prompt}\n\n"
                    "[약속] 표준 입력만 읽고 표준 출력에 정답만 "
                    "출력하세요. 입력 형식과 줄바꿈을 정확히 지켜야 합니다."
                )
                mcq_prompt = options = correct_option = None
                if difficulty != "GOLD":
                    mcq_prompt, options, correct_option = python_multiple_choice(spec, variant)
                rows.append({
                    "title": f"{SEED_PREFIX}{difficulty}:{local_number:03d}] 🐾 {variant_title}: {spec.title}",
                    "concept": f"PYTHON:{spec.concept}", "difficulty": difficulty,
                    "type": "CODE", "description": prompt,
                    # The grader executes each submission as a complete program for every stdin case.
                    # No function name or wrapper is part of that contract, so the editor starts empty.
                    "template_code": "",
                    "test_cases": json.dumps(cases(spec.operation, variant), ensure_ascii=False),
                    "multiple_choice_prompt": mcq_prompt,
                    "options": options, "correct_option": correct_option,
                    "hint_text": python_hint(spec),
                    "reward_coins": {"BRONZE": 30, "SILVER": 60, "GOLD": 100}[difficulty],
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
        legacy_name = legacy_name.removeprefix("PYTHON:")
        target_name = target_name.removeprefix("PYTHON:")
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
            concepts = {
                row.name: row
                for row in db.scalars(select(Concept).where(Concept.domain == "PYTHON")).all()
            }
            existing = {
                seed_key(row.title): row
                for row in db.scalars(select(Task).where(Task.title.startswith(SEED_PREFIX))).all()
            }
            for data in build_tasks():
                concept_name = data["concept"].removeprefix("PYTHON:")
                concept = concepts.get(concept_name)
                if concept is None:
                    concept = Concept(domain="PYTHON", name=concept_name)
                    db.add(concept)
                    db.flush()
                    concepts[concept.name] = concept
                row = existing.get(seed_key(data["title"]))
                values = {key: value for key, value in data.items() if key != "concept"}
                values.update(concept_id=concept.id, is_active=True)
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

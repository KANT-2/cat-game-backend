import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class CatChatCategory(StrEnum):
    COMPANION = "COMPANION"
    CODING = "CODING"
    GENERAL = "GENERAL"
    UNKNOWN = "UNKNOWN"
    PROMPT_INJECTION = "PROMPT_INJECTION"
    SAFETY = "SAFETY"
    PROFESSIONAL = "PROFESSIONAL"


@dataclass(frozen=True)
class CatChatDecision:
    message: str
    category: CatChatCategory
    direct_reply: str | None
    remember: bool


_ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
_PROMPT_INJECTION = re.compile(
    r"(이전|앞선|기존).{0,12}(대화|지시|명령|규칙).{0,12}(잊|무시|삭제)|"
    r"(지시|명령|규칙).{0,12}(무시|우회)|"
    r"시스템\s*(프롬프트|메시지)|개발자\s*(메시지|지시)|프롬프트\s*(공개|출력|보여)|"
    r"너는\s*이제|페르소나.{0,8}(바꿔|변경)|"
    r"ignore.{0,16}(previous|instruction)|forget.{0,16}(previous|instruction)|"
    r"system\s*prompt|developer\s*message|jailbreak|\bdan\b|act\s+as",
    re.IGNORECASE,
)
_SAFETY = re.compile(
    r"자해|자살|죽고\s*싶|폭탄|살인|해킹해|비밀번호\s*(훔|알아)|사기\s*(치|방법)|"
    r"아동.{0,8}(성적|음란)|마약.{0,8}(만들|제조)",
    re.IGNORECASE,
)
_PROFESSIONAL = re.compile(
    r"진단|처방|복용량|약을\s*먹|소송|법률\s*자문|투자\s*추천|주식\s*종목",
    re.IGNORECASE,
)
_CODING = re.compile(
    r"코딩|프로그래밍|파이썬|python|sql|자바스크립트|javascript|typescript|타입스크립트|"
    r"html|css|함수|변수|배열|리스트|딕셔너리|반복문|조건문|클래스|알고리즘|데이터\s*구조|"
    r"버그|디버깅|에러|오류|코드|api|데이터베이스|쿼리|git|깃허브",
    re.IGNORECASE,
)
_COMPANION = re.compile(
    r"안녕|반가|고마|미안|잘\s*잤|뭐\s*해|심심|놀자|놀래|놀까|놀아|놀이|좋아|싫어|기분|행복|슬퍼|우울|"
    r"힘들|피곤|졸려|배고파|공부|시험|숙제|학교|회사|친구|고양이|귀여|"
    r"사랑|응원|칭찬|이야기|대화|냐옹|야옹|냐앙|이름|너는|나는|내가|제일",
    re.IGNORECASE,
)

_DIRECT_REPLIES = {
    CatChatCategory.PROMPT_INJECTION: "냐… 냐앙. 나는 그냥 네 고양이로 있을래.",
    CatChatCategory.SAFETY: "냐아… 그건 도와줄 수 없어. 지금 위험하다면 곁의 믿을 만한 사람이나 긴급 도움에 바로 알려 줘.",
    CatChatCategory.PROFESSIONAL: "냐앙… 그건 고양이가 판단하면 안 되는 일이야. 의료·법률·재정 전문가에게 확인해 줘.",
}


def normalize_cat_chat_message(value: str) -> str:
    """Normalize untrusted chat text before every policy check.

    The returned value has compatibility Unicode normalized, zero-width controls removed,
    whitespace collapsed, and a hard 240-character boundary.
    """
    normalized = unicodedata.normalize("NFKC", value)
    normalized = _ZERO_WIDTH.sub("", normalized)
    return " ".join(normalized.split())[:240]


def classify_cat_chat(value: str) -> CatChatDecision:
    """Classify a user message before any external model receives it.

    Prompt-control, unsafe, and high-stakes professional requests never reach the provider.
    Other unmatched input is general conversation that Gemini may answer without remembering it.
    """
    message = normalize_cat_chat_message(value)
    if not message:
        return CatChatDecision(message, CatChatCategory.UNKNOWN, _DIRECT_REPLIES[CatChatCategory.UNKNOWN], False)
    if _PROMPT_INJECTION.search(message):
        category = CatChatCategory.PROMPT_INJECTION
    elif _SAFETY.search(message):
        category = CatChatCategory.SAFETY
    elif _PROFESSIONAL.search(message):
        category = CatChatCategory.PROFESSIONAL
    elif _CODING.search(message):
        category = CatChatCategory.CODING
    elif _COMPANION.search(message):
        category = CatChatCategory.COMPANION
    else:
        category = CatChatCategory.GENERAL
    return CatChatDecision(message, category, _DIRECT_REPLIES.get(category), category in {CatChatCategory.CODING, CatChatCategory.COMPANION})


def cat_chat_memory_summary(category: CatChatCategory) -> str:
    """Return a server-owned summary that cannot preserve user prompt instructions."""
    if category == CatChatCategory.CODING:
        return "사용자와 코딩 학습에 관해 대화했다."
    return "사용자와 일상과 기분에 관해 대화했다."


def safe_cat_chat_output(value: str | None) -> str | None:
    """Reject empty, oversized, or instruction-leaking provider output."""
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    if not normalized or len(normalized) > 220:
        return None
    if re.search(r"system\s*prompt|developer\s*message|시스템\s*프롬프트|개발자\s*지시", normalized, re.IGNORECASE):
        return None
    return normalized

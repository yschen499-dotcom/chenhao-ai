import logging
import re
from typing import List, Tuple

from campus_assistant_v3.config import settings
from campus_assistant_v3.llm import call_qwen, ensure_str
from campus_assistant_v3.prompts import build_query_rewrite_prompt
from campus_assistant_v3.schemas import QueryPlan


logger = logging.getLogger(__name__)


def format_recent_history_for_rewrite(history: List[Tuple[str, str]]) -> str:
    if not history:
        return "（无）"
    sliced = history[-settings.rewrite_context_turns :]
    lines = []
    for user_text, assistant_text in sliced:
        lines.append(f"用户：{user_text}")
        lines.append(f"助手：{assistant_text}")
    return "\n".join(lines)


def classify_question_type(question: str) -> str:
    question = ensure_str(question)
    if any(keyword in question for keyword in settings.process_question_keywords):
        return "process"
    if any(keyword in question for keyword in settings.policy_question_keywords):
        return "policy"
    if any(keyword in question for keyword in settings.fact_question_keywords):
        return "fact"
    return "general"


def should_rewrite_question(question: str, history: List[Tuple[str, str]]) -> bool:
    question = ensure_str(question)
    if not settings.query_rewrite_enabled or not question:
        return False
    if len(question) >= 28:
        return False

    ambiguous_patterns = [
        r"^(这个|那个|这个呢|那个呢|周末呢|然后呢|怎么办|怎么弄|怎么申请|什么时候|在哪|在哪里|怎么评)$",
        r"(这个|那个|周末呢|怎么办|怎么申请|什么时候|在哪里|能不能|可以吗)$",
    ]
    if any(re.search(pattern, question) for pattern in ambiguous_patterns):
        return True
    if len(question) <= 12:
        return True
    if history and len(question) <= 18:
        return True
    return False


def sanitize_rewritten_query(original_question: str, rewritten_query: str) -> str:
    original_question = ensure_str(original_question)
    rewritten_query = ensure_str(rewritten_query)
    if not rewritten_query:
        return original_question

    rewritten_query = rewritten_query.splitlines()[0].strip().strip("`\"' ")
    if not rewritten_query:
        return original_question

    answer_like_prefixes = ("答：", "回答：", "答案：", "根据", "一般来说", "可以", "不能")
    if rewritten_query.startswith(answer_like_prefixes):
        return original_question
    if len(rewritten_query) > 60:
        return original_question
    return rewritten_query


def rewrite_query(question: str, history: List[Tuple[str, str]]) -> str:
    if not should_rewrite_question(question, history):
        return question

    prompt = build_query_rewrite_prompt(question, format_recent_history_for_rewrite(history))
    try:
        rewritten_query = call_qwen(prompt, model_name=settings.rewrite_model, temperature=0.0)
        safe_query = sanitize_rewritten_query(question, rewritten_query)
        logger.info(f"🔁 查询改写：原问题={question} | 改写后={safe_query}")
        return safe_query
    except Exception as exc:
        logger.warning(f"⚠️ 查询改写失败，回退原问题：{exc}")
        return question


def build_query_plan(question: str, history: List[Tuple[str, str]]) -> QueryPlan:
    original_question = ensure_str(question)
    rewritten_question = rewrite_query(original_question, history)
    question_type = classify_question_type(original_question)
    use_rewrite = rewritten_question != original_question
    return QueryPlan(
        original_question=original_question,
        rewritten_question=rewritten_question,
        use_rewrite=use_rewrite,
        question_type=question_type,
    )

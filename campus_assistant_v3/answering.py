import logging
from typing import List, Tuple

from campus_assistant_v3.config import settings
from campus_assistant_v3.llm import call_qwen
from campus_assistant_v3.prompts import build_answer_style_prompt
from campus_assistant_v3.schemas import AnswerResult, RetrievalResult


logger = logging.getLogger(__name__)


def format_history(history: List[Tuple[str, str]], max_turns: int = settings.max_prompt_history_turns) -> str:
    if not history:
        return "（无）"
    sliced = history[-max_turns:]
    lines = []
    for user_text, assistant_text in sliced:
        lines.append(f"用户：{user_text}")
        lines.append(f"助手：{assistant_text}")
    return "\n".join(lines)


def format_docs_for_prompt(docs, max_chars: int = 6000) -> str:
    if not docs:
        return "（未检索到相关内容）"

    parts = []
    used = 0
    for index, doc in enumerate(docs, start=1):
        src = doc.metadata.get("source", "unknown")
        text = (doc.page_content or "").strip()
        block = f"[片段{index} | 来源：{src}]\n{text}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts) if parts else "（检索内容过长，已被截断）"


def build_answer_prompt(question: str, question_type: str, chat_history_text: str, context_text: str) -> str:
    logger.info(f"🧭 问题类型识别：{question_type}")
    if settings.answer_template_enabled:
        answer_style = build_answer_style_prompt(question_type, natural_style_enabled=settings.natural_style_enabled)
    else:
        answer_style = "请自然回答，先直接回答核心问题，再补充必要细节。"

    return f"""
你是【浙江科技大学专属校园智能问答助手】，回答必须符合浙科大校园场景。

请优先参考以下校园资料内容（不允许提及“检索/文档/RAG”等技术词）：
{context_text}

历史对话：
{chat_history_text}

用户问题：{question}

当前问题类型：{question_type}

回答风格建议：
{answer_style}

通用回答要求：
- 先回答核心问题，再补充必要细节
- 保持有条理，但语言自然，像老师或校园工作人员在说明，不要像公文或固定模板
- 只有信息较多时才使用短条目；如果一句话或一小段就能说清，就不要强行分段编号
- 如果资料不支持某一项内容，可以省略，不要为了凑结构硬写
- 优先依据资料回答，不要脱离资料随意发挥
- 不知道的内容不要编造，直接说“抱歉，我暂时没有找到相关信息”
- 不要提及“检索/文档/RAG”等技术词
""".strip()


def generate_answer(question: str, history: List[Tuple[str, str]], retrieval_result: RetrievalResult) -> AnswerResult:
    chat_history_text = format_history(history)
    context_text = format_docs_for_prompt(retrieval_result.docs)
    prompt = build_answer_prompt(
        question=question,
        question_type=retrieval_result.query_plan.question_type,
        chat_history_text=chat_history_text,
        context_text=context_text,
    )
    answer = call_qwen(prompt, model_name=settings.default_chat_model, temperature=0.1)
    return AnswerResult(
        answer=answer,
        sources=retrieval_result.sources,
        question_type=retrieval_result.query_plan.question_type,
        rewritten_question=retrieval_result.query_plan.rewritten_question if retrieval_result.query_plan.use_rewrite else None,
    )

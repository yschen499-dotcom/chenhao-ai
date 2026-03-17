import logging
import time
from typing import Any, Optional

import dashscope
from dashscope.aigc.chat_completion import Completions

from campus_assistant_v3.config import settings


logger = logging.getLogger(__name__)


def initialize_dashscope() -> None:
    if not settings.dashscope_api_key:
        logger.error("❌ DASHSCOPE_API_KEY未配置！请在.env文件中设置：DASHSCOPE_API_KEY=sk-xxxxxxxxx")
        raise SystemExit(1)

    dashscope.api_key = settings.dashscope_api_key
    if not getattr(dashscope, "base_compatible_api_url", None):
        dashscope.base_compatible_api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"


def ensure_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return " ".join(
            str(item) if not isinstance(item, dict) else item.get("text", str(item)) for item in value
        ).strip()
    return str(value).strip()


def extract_model_content(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    if message is None:
        return ""
    return ensure_str(getattr(message, "content", ""))


def call_qwen(prompt: str, model_name: Optional[str] = None, temperature: float = 0.1) -> str:
    text = ensure_str(prompt)
    if not text:
        return "请输入有效问题。"

    messages = [
        {"role": "system", "content": "你是浙江科技大学校园智能助手，请根据提供的资料简洁回答。"},
        {"role": "user", "content": text},
    ]

    last_error: Optional[Exception] = None
    for attempt in range(1, settings.model_max_retries + 1):
        try:
            response = Completions.create(
                model=model_name or settings.default_chat_model,
                messages=messages,
                temperature=temperature,
            )
            status_code = getattr(response, "status_code", 200)
            if status_code != 200:
                raise RuntimeError(getattr(response, "message", "通义千问调用失败"))

            content = extract_model_content(response)
            if not content:
                raise RuntimeError("通义千问返回了空内容")
            return content
        except Exception as exc:
            last_error = exc
            logger.warning(f"⚠️ 第 {attempt}/{settings.model_max_retries} 次模型调用失败：{exc}")
            if attempt < settings.model_max_retries:
                time.sleep(attempt)

    logger.error(f"❌ 模型服务连续调用失败：{last_error}")
    raise RuntimeError("大模型服务暂时不可用，请稍后重试。") from last_error

"""OpenAI 兼容 Chat Completions（用于深度解析与定时报告）。"""

from __future__ import annotations

import json
import logging
from typing import Any, List, Optional

import requests

from .config import get_llm_api_key, get_llm_base_url, get_llm_model, get_llm_timeout_seconds, is_llm_configured

_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
    return _session


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_llm_api_key()}",
        "Content-Type": "application/json",
    }


def warm_llm_connection() -> None:
    """
    进程启动后做一次极短请求，完成 DNS/TLS/连接池预热。
    钉钉对单条回复有等待上限，首条「测试早报」若冷启动过久会表现为「没反应」。
    """
    if not is_llm_configured():
        logging.info("LLM 未配置，跳过 warmup。")
        return
    try:
        chat_completion(
            [{"role": "user", "content": "只回复一个词：ok"}],
            temperature=0,
            max_tokens=8,
        )
        logging.info("LLM warmup 完成。")
    except Exception:
        logging.warning("LLM warmup 失败（不影响启动，用户首条仍可能较慢）", exc_info=True)


def chat_completion(
    messages: List[dict[str, Any]],
    *,
    temperature: float = 0.4,
    max_tokens: Optional[int] = None,
) -> str:
    if not is_llm_configured():
        raise RuntimeError("未配置 AGENT_LLM_API_KEY。")

    url = f"{get_llm_base_url()}/chat/completions"
    body: dict[str, Any] = {
        "model": get_llm_model(),
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens

    resp = _get_session().post(url, headers=_headers(), json=body, timeout=get_llm_timeout_seconds())
    resp.raise_for_status()
    data = resp.json()
    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as e:
        logging.error("LLM 响应异常: %s", json.dumps(data, ensure_ascii=False)[:800])
        raise RuntimeError("LLM 返回格式异常") from e

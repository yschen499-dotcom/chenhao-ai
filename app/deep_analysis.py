"""大模型深度解析：指定饰品走势与投资建议。"""

from __future__ import annotations

import logging
from typing import List

from .collector import SteamDTCollector
from .config import get_max_reply_chars, is_llm_configured
from .llm import chat_completion
from .storage import Storage


def _truncate(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 24] + "\n...(truncated)..."


def _history_lines(storage: Storage, item_name: str, source: str, limit: int = 12) -> str:
    hist = storage.recent_sell_prices_for_source(
        item_name, source, limit, scan_channel="background"
    )
    if not hist:
        return f"  {source}: 无历史在售价快照"
    return f"  {source}: 近{len(hist)}次在售价序列（由旧到新）={hist}"


def run_deep_analysis(item_name: str, storage: Storage, collector: SteamDTCollector) -> str:
    name = (item_name or "").strip()
    if not name:
        return "用法：深度解析 饰品名称"

    if not is_llm_configured():
        return "深度解析需要大模型：请在环境变量中配置 AGENT_LLM_API_KEY（及可选 AGENT_LLM_BASE_URL, AGENT_LLM_MODEL）。"

    try:
        collected = collector.fetch_single_price(name)
    except Exception as e:
        logging.exception("深度解析拉价失败")
        return f"拉取饰品行情失败：{e}"

    plat_lines: List[str] = []
    for row in collected.platform_prices:
        plat_lines.append(
            f"- 平台 {row.platform}: 在售价 ¥{row.sell_price:.2f} | 求购价 ¥{row.bidding_price:.2f} | "
            f"在售 {row.sell_count} | 求购 {row.bidding_count}"
        )

    hist_block = "\n".join(
        [
            _history_lines(storage, name, "YOUPIN"),
            _history_lines(storage, name, "BUFF"),
            _history_lines(storage, name, "C5"),
        ]
    )

    user = (
        f"饰品：{collected.item_name}\n"
        f"marketHashName：{collected.market_hash_name}\n\n"
        f"当前多平台报价：\n{chr(10).join(plat_lines)}\n\n"
        f"本地历史在售价（后台扫描写入，可能为空）：\n{hist_block}\n\n"
        "请用中文输出：\n"
        "1）结合价位与挂单量，简要判断短期趋势与流动性（偏事实描述，非喊单）。\n"
        "2）给出「专业风格」的风险提示与仓位/操作思路（分点、可执行；注明不构成投资建议）。\n"
    )

    system = (
        "你是熟悉 CS2 饰品二级市场与 SteamDT 类数据的分析助手。"
        "回答必须基于给定数据；若历史数据不足，请明确说明不确定性。"
        "禁止编造具体价格或成交；语气专业、克制。"
    )

    try:
        out = chat_completion(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.35,
            max_tokens=1800,
        )
    except Exception as e:
        logging.exception("深度解析 LLM 调用失败")
        return f"大模型分析失败：{e}"

    return _truncate(out, get_max_reply_chars())

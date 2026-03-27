"""定时早报 / 周报 / 月报：由大模型基于本地数据与即时大盘生成，并附带投资建议。"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Dict, List

from zoneinfo import ZoneInfo

from .collector import SteamDTCollector
from .config import get_max_reply_chars, get_scheduler_timezone, is_llm_configured
from .llm import chat_completion
from .market_overview import run_market_overview
from .storage import Storage


def _now_in_scheduler_tz():
    """无效 AGENT_SCHEDULER_TIMEZONE 时回退上海，避免 ZoneInfo 抛错导致整条命令无回复。"""
    name = (get_scheduler_timezone() or "").strip() or "Asia/Shanghai"
    try:
        z = ZoneInfo(name)
    except Exception:
        logging.warning("无效时区 %r，已回退 Asia/Shanghai", name)
        z = ZoneInfo("Asia/Shanghai")
        name = "Asia/Shanghai"
    return datetime.now(z), name


def _tz_today() -> date:
    return _now_in_scheduler_tz()[0].date()


def _truncate(s: str, max_chars: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 24] + "\n...(truncated)..."


def _watchlist_lines(storage: Storage, limit: int = 30) -> List[str]:
    names = storage.list_enabled_watch_item_names()
    if not names:
        return ["（当前无启用中的自选）"]
    out = []
    for n in names[:limit]:
        out.append(f"- {n}")
    if len(names) > limit:
        out.append(f"... 共 {len(names)} 个，仅列前 {limit} 个")
    return out


def _market_block_live(storage: Storage, collector: SteamDTCollector) -> str:
    try:
        t = run_market_overview(storage, collector)
        return _truncate(t, 2000)
    except Exception:
        logging.exception("大盘摘要拉取失败")
        return "（大盘摘要暂时不可用）"


def _group_snapshots_by_date(storage: Storage, start: str, end: str) -> Dict[str, Dict[str, object]]:
    rows = storage.list_market_snapshots_in_range(start, end)
    by_date: Dict[str, Dict[str, object]] = {}
    for r in rows:
        d = str(r["trade_date"])
        if d not in by_date:
            by_date[d] = {}
        by_date[d][str(r["slot"])] = r
    return by_date


def _pick_day_row(slots: Dict[str, object]):
    if "evening" in slots:
        return slots["evening"]
    if "morning" in slots:
        return slots["morning"]
    return None


def _fmt_row_line(r) -> str:
    return (
        f"点位 {float(r['index_value']):.2f} | 涨跌幅 {float(r['rise_fall_pct']):+.2f}% | "
        f"高 {float(r['high_price']):.2f} / 低 {float(r['low_price']):.2f} | "
        f"涨跌家数 涨{r['up_num']}/平{r['flat_num']}/跌{r['down_num']}"
    )


def _yesterday_market_summary(storage: Storage) -> List[str]:
    today = _tz_today()
    y = today - timedelta(days=1)
    ys = y.strftime("%Y-%m-%d")
    sm = storage.get_market_snapshot(ys, "morning")
    se = storage.get_market_snapshot(ys, "evening")
    if not sm and not se:
        return [
            f"**昨日（{ys}）大盘**：尚无本地快照。",
            "说明：需至少跑过 **9:00 早报任务** 与 **23:00 静默采集** 各一次后，才能汇总「昨日一天」；新部署首日无昨日数据属正常。",
        ]
    lines: List[str] = [f"**昨日（{ys}）综合大盘（本地快照）**"]
    if sm:
        lines.append(f"- 早盘采集：{_fmt_row_line(sm)}")
    if se:
        lines.append(f"- 晚盘采集：{_fmt_row_line(se)}")
    if sm and se:
        im, ie = float(sm["index_value"]), float(se["index_value"])
        intra = (ie - im) / im * 100.0 if im else 0.0
        lines.append(f"- 晚盘相对早盘：{'+' if intra >= 0 else ''}{intra:.2f}%（同一自然日内两次快照对比，非交易所官方）")
        lines.append(
            f"- 日内高低（优先取晚盘快照中的高/低）：高 {float(se['high_price']):.2f} / 低 {float(se['low_price']):.2f}"
        )
    elif sm:
        lines.append("- 仅早盘快照：暂无晚盘，无法计算「收盘相对开盘」式日内对比。")
    elif se:
        lines.append("- 仅晚盘快照：缺早盘，日内对比不完整。")
    return lines


def _range_market_summary(storage: Storage, days: int, title: str) -> List[str]:
    today = _tz_today()
    end = today - timedelta(days=1)
    start = today - timedelta(days=days)
    start_s = start.strftime("%Y-%m-%d")
    end_s = end.strftime("%Y-%m-%d")

    by_date = _group_snapshots_by_date(storage, start_s, end_s)
    if not by_date:
        return [
            f"**{title}**",
            f"区间 {start_s}～{end_s} 无快照数据。请保持机器人每日 9:00 与 23:00 能运行以积累记录。",
        ]

    lines: List[str] = [f"**{title}**（{start_s} ～ {end_s}）", ""]
    closes: List[float] = []
    highs: List[float] = []
    lows: List[float] = []

    cur = start
    while cur <= end:
        ds = cur.strftime("%Y-%m-%d")
        slots = by_date.get(ds, {})
        r = _pick_day_row(slots)
        if r is not None:
            iv = float(r["index_value"])
            closes.append(iv)
            highs.append(float(r["high_price"]))
            lows.append(float(r["low_price"]))
            which = "晚盘" if "evening" in slots else "早盘"
            lines.append(f"- {ds}（{which}）{_fmt_row_line(r)}")
        cur += timedelta(days=1)

    lines.append("")
    if len(closes) >= 2:
        net = (closes[-1] - closes[0]) / closes[0] * 100.0 if closes[0] else 0.0
        lines.append(
            f"- 区间首尾收盘（按日优选晚盘）：首 {closes[0]:.2f} → 末 {closes[-1]:.2f}，约 {'+' if net >= 0 else ''}{net:.2f}%"
        )
    if highs and lows:
        lines.append(f"- 区间内快照高低极值：高 max {max(highs):.2f} / 低 min {min(lows):.2f}")
    lines.append("")
    lines.append("说明：快照为当时 SteamDT 页面解析值，非官方指数连续行情。")
    return lines


def _llm_common_system() -> str:
    return (
        "你是 CS2 饰品二级市场研究助手。请严格基于用户提供的素材撰写报告，不要编造素材中不存在的数据。"
        "报告需用 Markdown 分节，语气专业、克制；必须包含「风险提示」与「不构成投资建议」类声明。"
        "在文末给出可操作的仓位/节奏建议（分点），并强调用户需自行核实。"
    )


def _run_llm_report(title_line: str, data_block: str) -> str:
    user = (
        f"{title_line}\n\n"
        f"以下为数据素材（可能不完整）：\n\n{data_block}\n\n"
        "请输出完整报告，并单列一节「针对性投资建议」（结合自选列表与大盘环境，若自选为空则说明以观望与指数为主）。"
    )
    return chat_completion(
        [
            {"role": "system", "content": _llm_common_system()},
            {"role": "user", "content": user},
        ],
        temperature=0.35,
        max_tokens=3500,
    )


def build_morning_report(storage: Storage, collector: SteamDTCollector) -> str:
    if not is_llm_configured():
        return "早报需大模型生成：请配置 AGENT_LLM_API_KEY（及可选 AGENT_LLM_BASE_URL / AGENT_LLM_MODEL）。"

    now, tz_label = _now_in_scheduler_tz()
    title = f"☀️ CS2 盯盘早报任务 · {now.strftime('%Y-%m-%d %H:%M')} ({tz_label})"

    # 昨日回顾与即时大盘互不依赖，并行拉取以缩短首包耗时（钉钉对回复有等待上限）
    with ThreadPoolExecutor(max_workers=2) as pool:
        f_y = pool.submit(_yesterday_market_summary, storage)
        f_m = pool.submit(_market_block_live, storage, collector)
        y_lines = f_y.result()
        m_live = f_m.result()

    data_block = "\n".join(
        [
            "### 昨日大盘回顾",
            *y_lines,
            "",
            "### 今日大盘（即时解析文本）",
            m_live,
            "",
            "### 自选监控",
            "\n".join(_watchlist_lines(storage)),
        ]
    )

    try:
        out = _run_llm_report(title, data_block)
    except Exception as e:
        logging.exception("早报 LLM 失败")
        return f"早报生成失败：{e}"

    return _truncate(out, get_max_reply_chars())


def build_weekly_report(storage: Storage, collector: SteamDTCollector) -> str:
    if not is_llm_configured():
        return "周报需大模型生成：请配置 AGENT_LLM_API_KEY（及可选 AGENT_LLM_BASE_URL / AGENT_LLM_MODEL）。"

    now, tz_label = _now_in_scheduler_tz()
    yp, wk, _ = now.isocalendar()
    title = f"📅 CS2 盯盘周报 · {yp}年第{wk}周 · {now.strftime('%Y-%m-%d %H:%M')} ({tz_label})"

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_r = pool.submit(_range_market_summary, storage, 7, "近 7 日大盘回顾")
        f_m = pool.submit(_market_block_live, storage, collector)
        r_lines = f_r.result()
        m_live = _truncate(f_m.result(), 1200)

    data_block = "\n".join(
        [
            *r_lines,
            "",
            "### 当前大盘（即时）",
            m_live,
            "",
            "### 自选监控",
            "\n".join(_watchlist_lines(storage)),
        ]
    )

    try:
        out = _run_llm_report(title, data_block)
    except Exception as e:
        logging.exception("周报 LLM 失败")
        return f"周报生成失败：{e}"

    return _truncate(out, get_max_reply_chars())


def build_monthly_report(storage: Storage, collector: SteamDTCollector) -> str:
    if not is_llm_configured():
        return "月报需大模型生成：请配置 AGENT_LLM_API_KEY（及可选 AGENT_LLM_BASE_URL / AGENT_LLM_MODEL）。"

    now, tz_label = _now_in_scheduler_tz()
    title = f"📆 CS2 盯盘月报 · {now.year}年{now.month}月 · {tz_label}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        f_r = pool.submit(_range_market_summary, storage, 30, "近 30 日大盘回顾")
        f_m = pool.submit(_market_block_live, storage, collector)
        r_lines = f_r.result()
        m_live = _truncate(f_m.result(), 1200)

    data_block = "\n".join(
        [
            *r_lines,
            "",
            "### 当前大盘（即时）",
            m_live,
            "",
            "### 自选监控",
            "\n".join(_watchlist_lines(storage)),
        ]
    )

    try:
        out = _run_llm_report(title, data_block)
    except Exception as e:
        logging.exception("月报 LLM 失败")
        return f"月报生成失败：{e}"

    return _truncate(out, get_max_reply_chars())

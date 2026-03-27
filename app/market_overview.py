"""
大盘（综合）：与 SteamDT 综合大盘页（默认 https://steamdt.cn/section?type=BROAD）首屏数据一致。
通过 section 页 BROAD 解析指数与涨跌家数；首页 __NUXT_DATA__ 解析成交量/成交额及环比（与 https://steamdt.com/ 首屏一致）。
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import List, NamedTuple, Optional, Tuple

import requests

from .config import (
    get_steamdt_home_url,
    get_steamdt_request_timeout_seconds,
    get_steamdt_section_broad_url,
)
from .collector import SteamDTCollector
from .storage import Storage


class BroadSnapshot(NamedTuple):
    update_time: str
    index: float
    yesterday: float
    high: float
    low: float
    rise_fall_diff: float
    rise_fall_rate_pct: float
    transaction_amount: float
    transaction_count: str
    up_num: int
    flat_num: int
    down_num: int


class HomeTradeStats(NamedTuple):
    """steamdt.com 首页 today/yesterday 成交块（与页面「饰品成交量/成交额」环比一致）。"""

    turnover_today: float
    turnover_yesterday: float
    trade_num_today: str
    trade_num_yesterday: str
    trade_volume_ratio_pct: float
    trade_amount_ratio_pct: float


_HOME_TRADE_BLOCK_RE = re.compile(
    r'tradeAmountRatio":\d+\},"(\d+)",([\d.]+),"(\d+)",([\d.]+),([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+),'
    r'\{"addNum":\d+,"addValuation":\d+,"tradeNum":\d+,"turnover":\d+\},'
    r'"(\d+)",([\d.]+),"(\d+)",([\d.]+)',
)


def _display_time(update_time: str) -> str:
    """2026-03-25 07:15:10 -> 2026/03/25 07:15:10"""
    s = (update_time or "").strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10].replace("-", "/") + s[10:].replace("-", "/")
    return s


def _fmt_wan_from_count(tcnt: str) -> str:
    n = float(str(tcnt).replace(",", ""))
    return f"{n / 10000:.3f}万"


def _fmt_yi_amount(yuan: float) -> str:
    return f"{yuan / 1e8:.3f}亿"


def _fmt_wan_from_yuan(yuan: float) -> str:
    """首页成交额以「万」展示（与 steamdt.com 卡片一致）。"""
    return f"{yuan / 10000:.3f}万"


def _fmt_chain_ratio_pct(r: float) -> str:
    """环比文案：↑ 2% / ↓ -2.9%（与首页一致）。"""
    if r > 0:
        s = f"{r:g}" if r == int(r) else f"{r:.2f}".rstrip("0").rstrip(".")
        return f"↑ {s}%"
    if r < 0:
        return f"↓ {r}%"
    return "→ 0%"


def _parse_home_trade_stats(raw_nuxt: str) -> Optional[HomeTradeStats]:
    m = _HOME_TRADE_BLOCK_RE.search(raw_nuxt)
    if not m:
        return None
    g = m.groups()
    try:
        return HomeTradeStats(
            turnover_today=float(g[3]),
            turnover_yesterday=float(g[11]),
            trade_num_today=g[2],
            trade_num_yesterday=g[10],
            trade_volume_ratio_pct=float(g[6]),
            trade_amount_ratio_pct=float(g[7]),
        )
    except (TypeError, ValueError):
        return None


def _fetch_home_trade_stats() -> Optional[HomeTradeStats]:
    url = get_steamdt_home_url()
    timeout = get_steamdt_request_timeout_seconds()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException:
        logging.warning("SteamDT 首页请求失败，成交环比将省略。", exc_info=True)
        return None
    hm = re.search(
        r'<script[^>]+id="__NUXT_DATA__"[^>]*>(.*?)</script>',
        r.text,
        re.DOTALL,
    )
    if not hm:
        logging.warning("SteamDT 首页未找到 __NUXT_DATA__，成交环比将省略。")
        return None
    raw = hm.group(1).strip()
    stats = _parse_home_trade_stats(raw)
    if stats is None:
        logging.warning("SteamDT 首页未解析到成交统计块，可能改版。")
    return stats


def _sentiment_label(up: int, flat: int, down: int) -> str:
    """涨跌家数为主（持平占比高时不参与分母），贴近常见机器人用语。"""
    if up + flat + down <= 0:
        return "—"
    if up + down == 0:
        return "震荡"
    if up > down * 1.2:
        return "活跃"
    if down > up * 1.2:
        return "谨慎"
    return "震荡"


def sentiment_score_0_100(
    up: int,
    flat: int,
    down: int,
    rise_fall_rate_pct: float,
) -> int:
    """
    0–100：越高表示情绪越偏乐观；结合涨跌结构与大盘涨跌幅做简单量化。
    """
    total = up + flat + down
    if total <= 0:
        return 50
    up_r = up / total
    down_r = down / total
    # 涨跌差主导 0–80 区间，大盘涨跌幅微调 ±10
    base = 50.0 + (up_r - down_r) * 40.0
    rf = max(-5.0, min(5.0, float(rise_fall_rate_pct)))
    base += rf * 1.2
    return int(round(max(0.0, min(100.0, base))))


def position_advice_for_sentiment(score: int) -> str:
    """与情绪分配套的仓位管理建议（普适性表述，非喊单）。"""
    if score >= 75:
        return "仓位建议：情绪偏热，可维持中等偏高仓位，但应分批止盈、严控单票集中度与回撤。"
    if score >= 60:
        return "仓位建议：中性偏多，可小步加仓或持有核心标的，预留现金应对波动。"
    if score >= 45:
        return "仓位建议：中性，宜均衡配置，观望为主、减少追涨杀跌。"
    if score >= 30:
        return "仓位建议：偏防御，建议降低总仓位与杠杆，优先风控与流动性。"
    return "仓位建议：情绪偏弱，宜轻仓或观望，避免重仓抄底。"


def _extract_update_time(html: str) -> str:
    m = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})</span>", html)
    return m.group(1).strip() if m else ""


def _extract_low_price(html: str) -> Optional[float]:
    """
    从首屏四宫格里取「最低」价（NUXT 元组在 low 与今收相同时可能不单独传 low）。
    """
    m = re.search(r"最低\s*:</div>\s*<div[^>]+>\s*([0-9]+\.[0-9]+)\s*</div>", html)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


def _parse_broad_from_nuxt_script(
    raw_json: str,
) -> Optional[Tuple[float, float, float, float, float, float, float, str, int, int, int]]:
    """
    在 __NUXT_DATA__ 文本中匹配 BROAD 行内序列。

    新版（2025–2026 常见）：index, yesterday, high, low, riseFallDiff, riseFallRate,
    transactionAmount, transactionCount, up, flat, down

    旧版：无单独 low，第三段价格后为涨跌字段（low 视为与 index 相同）。
    """
    pat4 = re.compile(
        r'"BROAD",\d+,null,'
        r"([0-9.]+),([0-9.]+),([0-9.]+),([0-9.]+),"
        r"([-0-9.]+),([-0-9.]+),([0-9.]+),"
        r'"([^"]*)",(\d+),(\d+),(\d+)'
    )
    m = pat4.search(raw_json)
    if m:
        idx, yest, high, low, rfd, rfr, tamt, tcnt, up, flat, down = m.groups()
        return (
            float(idx),
            float(yest),
            float(high),
            float(low),
            float(rfd),
            float(rfr),
            float(tamt),
            tcnt,
            int(up),
            int(flat),
            int(down),
        )

    pat3 = re.compile(
        r'"BROAD",\d+,null,'
        r"([0-9.]+),([0-9.]+),([0-9.]+),"
        r"([-0-9.]+),([-0-9.]+),([0-9.]+),"
        r'"([^"]*)",(\d+),(\d+),(\d+)'
    )
    m = pat3.search(raw_json)
    if not m:
        return None
    idx, yest, high, rfd, rfr, tamt, tcnt, up, flat, down = m.groups()
    ix, ys, hi = float(idx), float(yest), float(high)
    return (
        ix,
        ys,
        hi,
        ix,
        float(rfd),
        float(rfr),
        float(tamt),
        tcnt,
        int(up),
        int(flat),
        int(down),
    )


def _fetch_broad_snapshot() -> BroadSnapshot:
    url = get_steamdt_section_broad_url()
    timeout = get_steamdt_request_timeout_seconds()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    html = r.text

    m = re.search(
        r'<script[^>]+id="__NUXT_DATA__"[^>]*>(.*?)</script>',
        html,
        re.DOTALL,
    )
    if not m:
        raise RuntimeError("页面中未找到 __NUXT_DATA__，SteamDT 可能改版。")

    raw = m.group(1).strip()
    # 校验为合法 JSON（内部为 Nuxt 引用数组）
    try:
        json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"__NUXT_DATA__ 非合法 JSON：{e}") from e

    parsed = _parse_broad_from_nuxt_script(raw)
    if not parsed:
        raise RuntimeError("无法在 __NUXT_DATA__ 中解析 BROAD 行情元组，SteamDT 可能改版。")

    idx, yest, high, low_from_nuxt, rfd, rfr, tamt, tcnt, up, flat, down = parsed
    low_guess = _extract_low_price(html)
    low = low_guess if low_guess is not None else low_from_nuxt

    ut = _extract_update_time(html)
    if not ut:
        ut = datetime.utcnow().isoformat(timespec="seconds")

    return BroadSnapshot(
        update_time=ut,
        index=idx,
        yesterday=yest,
        high=high,
        low=low,
        rise_fall_diff=rfd,
        rise_fall_rate_pct=rfr,
        transaction_amount=tamt,
        transaction_count=tcnt,
        up_num=up,
        flat_num=flat,
        down_num=down,
    )


def fetch_broad_snapshot() -> BroadSnapshot:
    """供入库与统计使用：拉取当前 BROAD 综合大盘快照。"""
    return _fetch_broad_snapshot()


def run_market_overview(storage: Storage, collector: Optional[SteamDTCollector] = None) -> str:
    _ = storage, collector
    try:
        s = _fetch_broad_snapshot()
    except requests.RequestException as e:
        logging.exception("SteamDT 综合大盘页请求失败")
        return f"大盘数据获取失败（网络）：{e}"
    except Exception as e:
        logging.exception("SteamDT 综合大盘解析失败")
        return f"大盘数据获取失败：{e}"

    try:
        return _run_market_overview_body(s)
    except Exception as e:
        logging.exception("大盘汇总渲染失败")
        return f"大盘暂时不可用：{e}"


def _run_market_overview_body(s: BroadSnapshot) -> str:
    home_trade = _fetch_home_trade_stats()

    sep = "───────────────"
    t_disp = _display_time(s.update_time)
    pct = s.rise_fall_rate_pct
    diff = s.rise_fall_diff
    pct_s = f"{pct:+.2f}%"
    diff_s = f"({diff:+.2f})" if diff != 0 else "(0.00)"

    mood = _sentiment_label(s.up_num, s.flat_num, s.down_num)
    mood_score = sentiment_score_0_100(s.up_num, s.flat_num, s.down_num, s.rise_fall_rate_pct)
    pos_adv = position_advice_for_sentiment(mood_score)

    if home_trade is not None:
        vol_line = (
            f" 成交量: {_fmt_wan_from_count(home_trade.trade_num_today)} "
            f"(昨日: {_fmt_wan_from_count(home_trade.trade_num_yesterday)})"
        )
        amt_line = (
            f" 成交额: {_fmt_wan_from_yuan(home_trade.turnover_today)} "
            f"(昨日: {_fmt_yi_amount(home_trade.turnover_yesterday)})"
        )
        chain_line = (
            " 环比变化: 额"
            f"{_fmt_chain_ratio_pct(home_trade.trade_amount_ratio_pct)} / 量"
            f"{_fmt_chain_ratio_pct(home_trade.trade_volume_ratio_pct)}"
        )
    else:
        vol_line = f" 成交量: {_fmt_wan_from_count(s.transaction_count)}"
        amt_line = f" 成交额: {_fmt_yi_amount(s.transaction_amount)}"
        chain_line = " 环比变化: —"

    lines: List[str] = [
        f"📊 时间: {t_disp}",
        sep,
        "📈 【市场指数】",
        f" 大盘点位: {s.index:.2f}",
        f" 昨日收盘: {s.yesterday:.2f}",
        f" 今日最高: {s.high:.2f}",
        f" 今日最低: {s.low:.2f}",
        f" 今日涨幅: {pct_s} {diff_s}",
        sep,
        "💰 【饰品成交】",
        vol_line,
        amt_line,
        chain_line,
        sep,
        "🎭 【市场情绪】",
        f" 情绪指标（0–100）: {mood_score}（越高越偏乐观；量化依据：涨跌结构与大盘涨跌幅）",
        f" 情绪标签: {mood}",
        f" 涨跌家数: 涨{s.up_num} / 平{s.flat_num} / 跌{s.down_num}",
        f" 仓位管理: {pos_adv}",
    ]
    return "\n".join(lines).strip()

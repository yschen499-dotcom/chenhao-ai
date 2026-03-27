"""
自选监控用的多因子启发式：在售/求购/价格联动（非云端大模型）。
可随 AGENT_SIGNAL_* 环境变量调参。
"""

from __future__ import annotations

from typing import List

from .config import (
    get_signal_bid_up_min_ratio,
    get_signal_flat_price_max_pct,
    get_signal_sell_drop_for_bid_signal,
    get_signal_sell_vol_shock_abs_ratio,
    get_signal_sell_vol_shock_min_delta,
    get_signal_suppress_price_max_pct,
    get_signal_suppress_sell_drop_ratio,
)


def infer_liquidity_signals(
    price_change_pct: float,
    prev_sell_count: int,
    sell_count: int,
    prev_bid_count: int,
    bid_count: int,
) -> List[str]:
    """
    关键信号（启发式）：
    - 在售减少 + 求购增加 → 扫货嫌疑
    - 在售与价格同步下行 → 压价吸货嫌疑
    - 在售量剧烈波动 → 挂单操纵嫌疑
    - 在售大动、价格几乎不动 → 假挂单/异常盘口嫌疑
    """
    psc = max(int(prev_sell_count), 1)
    psb = max(int(prev_bid_count), 1)
    d_sell = (int(sell_count) - int(prev_sell_count)) / float(psc)
    d_bid = (int(bid_count) - int(prev_bid_count)) / float(psb)
    abs_bid = int(bid_count) - int(prev_bid_count)

    out: List[str] = []

    if (
        d_sell <= -get_signal_sell_drop_for_bid_signal()
        and (d_bid >= get_signal_bid_up_min_ratio() or abs_bid >= 5)
    ):
        out.append("在售明显减少且求购走强 → 疑似批量扫货/带队吃货")

    if price_change_pct < -get_signal_suppress_price_max_pct() and d_sell < -get_signal_suppress_sell_drop_ratio():
        out.append("在售价下行且在售同步收缩 → 疑似压价吸货（挂单侧）")

    shock = get_signal_sell_vol_shock_abs_ratio()
    if abs(d_sell) >= shock or abs(int(sell_count) - int(prev_sell_count)) >= get_signal_sell_vol_shock_min_delta():
        out.append("在售量剧烈变化 → 疑似庄家挂单操纵（需结合成交）")

    if abs(d_sell) >= shock * 0.9 and abs(price_change_pct) < get_signal_flat_price_max_pct():
        out.append("在售量异动大但价格几乎横盘 → 警惕假挂单/异常盘口")

    seen = set()
    uniq: List[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq

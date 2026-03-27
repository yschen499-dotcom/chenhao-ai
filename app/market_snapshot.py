"""写入综合大盘 BROAD 快照（早盘 / 晚盘），供日报/周报/月报汇总。"""

from __future__ import annotations

import logging
from datetime import datetime

from zoneinfo import ZoneInfo

from .config import get_scheduler_timezone
from .market_overview import fetch_broad_snapshot
from .storage import Storage


def save_market_snapshot_slot(storage: Storage, slot: str) -> None:
    """
    slot: morning（与早报同时刻）或 evening（23:00 静默采集，不推送）。
    trade_date 为 Asia/Shanghai 的日历日。
    """
    sl = (slot or "").strip().lower()
    if sl not in {"morning", "evening"}:
        raise ValueError("slot 须为 morning 或 evening")

    z = ZoneInfo(get_scheduler_timezone())
    trade_date = datetime.now(z).strftime("%Y-%m-%d")

    try:
        s = fetch_broad_snapshot()
    except Exception:
        logging.exception("大盘快照保存失败 slot=%s", sl)
        return

    storage.upsert_market_snapshot(
        trade_date,
        sl,
        index_value=s.index,
        yesterday_close=s.yesterday,
        high_price=s.high,
        low_price=s.low,
        rise_fall_pct=s.rise_fall_rate_pct,
        up_num=s.up_num,
        flat_num=s.flat_num,
        down_num=s.down_num,
    )
    logging.info("已写入大盘快照 trade_date=%s slot=%s index=%.2f", trade_date, sl, s.index)

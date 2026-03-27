"""定时任务：早报/周报/月报（钉钉 Webhook）；23:00 静默采集大盘快照（不推送晚报）。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from zoneinfo import ZoneInfo

from .config import get_scheduler_timezone, is_scheduler_enabled
from .dingtalk_notify import send_markdown_webhook
from .market_snapshot import save_market_snapshot_slot
from .monitor import MonitorService
from .reports import (
    build_monthly_report,
    build_morning_report,
    build_weekly_report,
)
from .storage import Storage


def start_scheduler(storage: Storage, monitor: MonitorService) -> Optional[BackgroundScheduler]:
    if not is_scheduler_enabled():
        logging.info("定时任务未启用（AGENT_SCHEDULER_ENABLED=false）。")
        return None

    tz_name = get_scheduler_timezone()
    collector = monitor.collector

    def notify(title: str, text: str) -> bool:
        return send_markdown_webhook(title, text)

    def job_morning() -> None:
        try:
            z = ZoneInfo(tz_name)
            today = datetime.now(z).strftime("%Y-%m-%d")
            if storage.read_state("last_morning_report_date", "") == today:
                return
            save_market_snapshot_slot(storage, "morning")
            text = build_morning_report(storage, collector)
            if notify("CS2 盯盘早报", text):
                storage.write_state("last_morning_report_date", today)
        except Exception:
            logging.exception("早报任务失败")

    def job_evening_snapshot() -> None:
        """仅写入晚盘快照，不推送任何消息。"""
        try:
            save_market_snapshot_slot(storage, "evening")
        except Exception:
            logging.exception("晚盘大盘快照任务失败")

    def job_weekly() -> None:
        try:
            z = ZoneInfo(tz_name)
            now = datetime.now(z)
            if now.weekday() != 6:
                return
            yp, wk, _wd = now.isocalendar()
            week_key = f"{yp}-W{wk:02d}"
            if storage.read_state("last_weekly_report_week", "") == week_key:
                return
            text = build_weekly_report(storage, collector)
            if notify("CS2 盯盘周报", text):
                storage.write_state("last_weekly_report_week", week_key)
        except Exception:
            logging.exception("周报任务失败")

    def job_monthly() -> None:
        try:
            z = ZoneInfo(tz_name)
            now = datetime.now(z)
            tomorrow = now + timedelta(days=1)
            if tomorrow.day != 1:
                return
            ym = f"{now.year}-{now.month:02d}"
            if storage.read_state("last_monthly_report_ym", "") == ym:
                return
            text = build_monthly_report(storage, collector)
            if notify("CS2 盯盘月报", text):
                storage.write_state("last_monthly_report_ym", ym)
        except Exception:
            logging.exception("月报任务失败")

    sched = BackgroundScheduler(timezone=tz_name)
    sched.add_job(job_morning, CronTrigger(hour=9, minute=0), id="morning_report")
    sched.add_job(job_evening_snapshot, CronTrigger(hour=23, minute=0), id="evening_market_snapshot")
    sched.add_job(job_weekly, CronTrigger(day_of_week="sun", hour=22, minute=0), id="weekly_report")
    sched.add_job(job_monthly, CronTrigger(hour=22, minute=0), id="monthly_report")
    sched.start()
    logging.info(
        "定时任务已启动：时区=%s；早报9:00（含早盘快照） 晚盘快照23:00（静默） 周报周日22:00 月末22:00月报。",
        tz_name,
    )
    return sched

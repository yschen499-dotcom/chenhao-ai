from datetime import datetime

from .storage import Storage


class MonitorService:
    def __init__(self, storage: Storage):
        self.storage = storage

    def scan_once(self) -> str:
        now = datetime.utcnow().isoformat(timespec="seconds")
        self.storage.write_state("last_scan_time", now)
        self.storage.write_state("last_error", "无")
        watch_count = self.storage.count_watch_items()
        return (
            "已完成一次内部测试扫描。\n"
            f"- 扫描时间: {now}\n"
            f"- 当前监控标的数: {watch_count}\n"
            "- 当前版本尚未接入真实市场采集器，这一步先用于打通命令、状态和存储链路。"
        )

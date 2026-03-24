import logging
from datetime import datetime

from .collector import SteamDTCollector
from .storage import Storage


class MonitorService:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.collector = SteamDTCollector()

    def scan_once(self) -> str:
        now = datetime.utcnow().isoformat(timespec="seconds")
        watch_items = self.storage.list_enabled_watch_item_names()
        if not watch_items:
            self.storage.write_state("last_scan_time", now)
            self.storage.write_state("last_error", "无")
            return "当前没有启用中的监控饰品，请先使用“添加监控 饰品名称”。"

        success_rows = []
        failed_rows = []

        for item_name in watch_items:
            try:
                collected = self.collector.fetch_single_price(item_name)
                self.storage.save_price_snapshot(
                    item_name=collected.item_name,
                    price=collected.sell_price,
                    volume=float(collected.sell_count),
                    source=collected.platform,
                )
                success_rows.append(collected)
            except Exception as exc:
                logging.exception("Failed to collect price for item=%r", item_name)
                failed_rows.append((item_name, str(exc)))

        self.storage.write_state("last_scan_time", now)
        if failed_rows:
            self.storage.write_state("last_error", failed_rows[0][1])
        else:
            self.storage.write_state("last_error", "无")
        if success_rows:
            self.storage.write_state("last_price_fetch_time", now)

        lines = [
            "已完成一次真实价格扫描。",
            f"- 扫描时间: {now}",
            f"- 监控标的数: {len(watch_items)}",
            f"- 成功抓取: {len(success_rows)}",
            f"- 抓取失败: {len(failed_rows)}",
        ]

        if success_rows:
            lines.append("- 最新价格：")
            for row in success_rows[:5]:
                lines.append(
                    f"  * {row.item_name} | {row.platform} 在售价 ¥{row.sell_price:.2f}"
                    f" | 在售 {row.sell_count} | 求购 ¥{row.bidding_price:.2f}"
                )

        if failed_rows:
            lines.append("- 失败项：")
            for item_name, error in failed_rows[:3]:
                lines.append(f"  * {item_name} -> {error}")

        return "\n".join(lines)

import logging
from datetime import datetime

from .collector import PlatformPrice, SteamDTCollector
from .storage import Storage


class MonitorService:
    def __init__(self, storage: Storage):
        self.storage = storage
        self.collector = SteamDTCollector()

    @staticmethod
    def _platform_label(platform: str) -> str:
        labels = {
            "BUFF": "BUFF",
            "YOUPIN": "悠悠",
            "C5": "C5",
            "STEAM": "Steam",
            "HALOSKINS": "HaloSkins",
        }
        return labels.get(platform.upper(), platform)

    @staticmethod
    def _pick_primary_platform(platform_prices: list[PlatformPrice]) -> PlatformPrice:
        priority = ["YOUPIN", "BUFF", "C5", "STEAM", "HALOSKINS"]
        by_name = {row.platform.upper(): row for row in platform_prices}
        for name in priority:
            if name in by_name:
                return by_name[name]
        return platform_prices[0]

    @staticmethod
    def _format_delta_text(current_price: float, previous_price: float | None) -> str:
        if previous_price is None or previous_price <= 0:
            return "（较上次：暂无数据）"

        delta = current_price - previous_price
        pct = (delta / previous_price) * 100
        arrow = "🔺" if delta > 0 else "🔻" if delta < 0 else "➖"
        return f"（较上次：{arrow}¥{abs(delta):.2f} / {arrow}{abs(pct):.2f}%）"

    def _format_platform_block(self, item_name: str, platform_prices: list[PlatformPrice]) -> list[str]:
        wanted_order = ["YOUPIN", "BUFF", "C5"]
        by_name = {row.platform.upper(): row for row in platform_prices}
        lines: list[str] = []

        for platform in wanted_order:
            row = by_name.get(platform)
            if row is None:
                lines.append(f"    ├ {self._platform_label(platform)}：暂无数据")
                continue
            previous_snapshot = self.storage.previous_price_snapshot(item_name, platform)
            previous_price = float(previous_snapshot["price"]) if previous_snapshot else None
            lines.append(
                f"    ├ {self._platform_label(platform)}：在售价 ¥{row.sell_price:.2f}"
                f" | 求购价 ¥{row.bidding_price:.2f} | 在售 {row.sell_count} "
                f"{self._format_delta_text(row.sell_price, previous_price)}"
            )

        return lines

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
                primary = self._pick_primary_platform(collected.platform_prices)
                for platform_row in collected.platform_prices:
                    self.storage.save_price_snapshot(
                        item_name=collected.item_name,
                        price=platform_row.sell_price,
                        volume=float(platform_row.sell_count),
                        source=platform_row.platform,
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
            "📡 已完成一次真实价格扫描",
            f"⏰ 扫描时间：{now}",
            f"🎯 监控标的：{len(watch_items)}",
            f"✅ 成功抓取：{len(success_rows)}",
            f"❌ 抓取失败：{len(failed_rows)}",
        ]

        if success_rows:
            lines.append("")
            lines.append("📦 最新价格面板")
            for row in success_rows[:5]:
                lines.append("━━━━━━━━━━━━━━━━━━")
                lines.append(f"🔹 {row.item_name}")
                lines.extend(self._format_platform_block(row.item_name, row.platform_prices))
            lines.append("━━━━━━━━━━━━━━━━━━")

        if failed_rows:
            lines.append("")
            lines.append("⚠️ 失败项")
            for item_name, error in failed_rows[:3]:
                lines.append(f"  • {item_name} -> {error}")

        return "\n".join(lines)

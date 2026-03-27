import logging
from dataclasses import dataclass
from datetime import datetime

from .alerts import (
    build_multimetric_alert_key,
    build_multimetric_alert_message,
)
from .collector import CollectedPrice, PlatformPrice, SteamDTCollector
from .config import get_alert_threshold_percent
from .storage import Storage


@dataclass
class TriggeredAlert:
    alert_type: str
    alert_key: str
    message: str
    item_name: str


@dataclass
class ScanResult:
    summary_text: str
    triggered_alerts: list[TriggeredAlert]


def _pct_move_abs(prev: float, curr: float) -> float:
    """
    相对波动幅度（%），用于与阈值比较。

    上一拍 ≤0 时视为**无有效基准**（例如首次出现求购、接口曾返回 0），返回 0，
    不触发「从 0→有 = 100%」类误报；有基准后仍按 |Δ|/prev 计算。
    """
    if prev <= 0:
        return 0.0
    return abs((float(curr) - float(prev)) / prev) * 100.0


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
    def _format_delta_text(current_price: float, previous_price: float | None) -> str:
        if previous_price is None or previous_price <= 0:
            return "（较上次：暂无数据）"

        delta = current_price - previous_price
        pct = (delta / previous_price) * 100
        arrow = "🔺" if delta > 0 else "🔻" if delta < 0 else "➖"
        return f"（较上次：{arrow}¥{abs(delta):.2f} / {arrow}{abs(pct):.2f}%）"

    def _format_platform_block(
        self,
        item_name: str,
        platform_prices: list[PlatformPrice],
        *,
        delta_scan_channel: str | None = "background",
    ) -> list[str]:
        wanted_order = ["YOUPIN", "BUFF", "C5"]
        by_name = {row.platform.upper(): row for row in platform_prices}
        lines: list[str] = []

        for platform in wanted_order:
            row = by_name.get(platform)
            if row is None:
                lines.append(f"    ├ {self._platform_label(platform)}：暂无数据")
                continue
            previous_snapshot = self.storage.previous_price_snapshot(
                item_name, platform, scan_channel=delta_scan_channel
            )
            previous_price = float(previous_snapshot["price"]) if previous_snapshot else None
            lines.append(
                f"    ├ {self._platform_label(platform)}：在售价 ¥{row.sell_price:.2f}"
                f" | 求购价 ¥{row.bidding_price:.2f} | 在售 {row.sell_count} "
                f"{self._format_delta_text(row.sell_price, previous_price)}"
            )

        return lines

    def _build_triggered_alerts(
        self, row: CollectedPrice, *, scan_channel: str = "background"
    ) -> list[TriggeredAlert]:
        threshold = get_alert_threshold_percent()
        alerts: list[TriggeredAlert] = []

        for platform_row in row.platform_prices:
            latest = self.storage.latest_price_snapshot(
                row.item_name, platform_row.platform, scan_channel=scan_channel
            )
            if not latest:
                continue

            prev_sell = float(latest["price"])
            prev_bid_p = float(latest["bid_price"] or 0)
            prev_sell_vol = int(float(latest["volume"] or 0))
            prev_bid_vol = int(float(latest["bid_volume"] or 0))

            curr_sell = platform_row.sell_price
            curr_bid_p = platform_row.bidding_price
            curr_sell_vol = platform_row.sell_count
            curr_bid_vol = platform_row.bidding_count

            p_sell = _pct_move_abs(prev_sell, curr_sell)
            p_bid = _pct_move_abs(prev_bid_p, curr_bid_p)
            p_sv = _pct_move_abs(float(prev_sell_vol), float(curr_sell_vol))
            p_bv = _pct_move_abs(float(prev_bid_vol), float(curr_bid_vol))

            detail_lines: list[str] = []
            if p_sell >= threshold:
                detail_lines.append(
                    f"在售价（购入参考）：¥{prev_sell:.2f} → ¥{curr_sell:.2f}（波动 {p_sell:.2f}%）"
                )
            if p_bid >= threshold:
                detail_lines.append(
                    f"求购价：¥{prev_bid_p:.2f} → ¥{curr_bid_p:.2f}（波动 {p_bid:.2f}%）"
                )
            if p_sv >= threshold:
                detail_lines.append(f"在售量：{prev_sell_vol} → {curr_sell_vol}（波动 {p_sv:.2f}%）")
            if p_bv >= threshold:
                detail_lines.append(f"求购量：{prev_bid_vol} → {curr_bid_vol}（波动 {p_bv:.2f}%）")

            if not detail_lines:
                continue

            alert_key = build_multimetric_alert_key(
                row.item_name, platform_row.platform, platform_row.update_time
            )
            message = build_multimetric_alert_message(
                row.item_name,
                self._platform_label(platform_row.platform),
                threshold,
                detail_lines,
            )
            alerts.append(
                TriggeredAlert(
                    alert_type="metric_move",
                    alert_key=alert_key,
                    message=message,
                    item_name=row.item_name,
                )
            )

        return alerts

    def run_scan(self, *, scan_channel: str = "background") -> ScanResult:
        now = datetime.utcnow().isoformat(timespec="seconds")
        watch_items = self.storage.list_enabled_watch_item_names()
        if not watch_items:
            self.storage.write_state("last_scan_time", now)
            self.storage.write_state("last_error", "无")
            return ScanResult(
                summary_text="当前没有启用中的监控饰品，请先使用“添加监控 饰品名称”。",
                triggered_alerts=[],
            )

        success_rows = []
        failed_rows = []
        triggered_alerts: list[TriggeredAlert] = []

        for item_name in watch_items:
            try:
                collected = self.collector.fetch_single_price(item_name)
                triggered_alerts.extend(
                    self._build_triggered_alerts(collected, scan_channel=scan_channel)
                )
                for platform_row in collected.platform_prices:
                    self.storage.save_price_snapshot(
                        item_name=collected.item_name,
                        price=platform_row.sell_price,
                        volume=float(platform_row.sell_count),
                        source=platform_row.platform,
                        bid_volume=float(platform_row.bidding_count),
                        bid_price=platform_row.bidding_price,
                        scan_channel=scan_channel,
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
            self.storage.write_state("last_successful_scan_time", now)

        lines = [
            "📡 后台扫描完成（价格已写入本地）",
            f"⏰ 扫描时间：{now}",
            f"🎯 监控标的：{len(watch_items)}",
            f"✅ 成功抓取：{len(success_rows)}",
            f"❌ 抓取失败：{len(failed_rows)}",
        ]

        if success_rows:
            lines.append("")
            lines.append("📦 最新价格面板（较上次 = 相对上一次后台扫描）")
            for row in success_rows[:5]:
                lines.append("━━━━━━━━━━━━━━━━━━")
                lines.append(f"🔹 {row.item_name}")
                lines.extend(
                    self._format_platform_block(
                        row.item_name,
                        row.platform_prices,
                        delta_scan_channel=scan_channel,
                    )
                )
            lines.append("━━━━━━━━━━━━━━━━━━")

        if failed_rows:
            lines.append("")
            lines.append("⚠️ 失败项")
            for item_name, error in failed_rows[:3]:
                lines.append(f"  • {item_name} -> {error}")

        return ScanResult(summary_text="\n".join(lines), triggered_alerts=triggered_alerts)

from typing import Callable, Optional

from .alerts import build_test_alert_message, record_test_alert
from .config import DB_PATH, SCAN_INTERVAL_SECONDS
from .storage import Storage


def _format_watch_rows(storage: Storage) -> str:
    rows = storage.list_watch_items()
    if not rows:
        return "当前监控列表为空。可使用 `add 名称` 添加一个标的。"

    lines = ["当前监控列表："]
    for idx, row in enumerate(rows, start=1):
        state = "on" if row["enabled"] else "off"
        lines.append(f"{idx}. {row['item_name']} [{state}]")
    return "\n".join(lines)


def help_text() -> str:
    return (
        "内部测试命令：\n"
        "- ping\n"
        "- help\n"
        "- status\n"
        "- watchlist\n"
        "- add 名称\n"
        "- remove 名称\n"
        "- scan\n"
        "- test alert"
    )


def status_text(storage: Storage) -> str:
    last_scan = storage.read_state("last_scan_time", "未扫描")
    last_error = storage.read_state("last_error", "无")
    watch_count = storage.count_watch_items()
    recent_alerts = storage.recent_alerts(limit=3)

    lines = [
        "内部测试状态：",
        f"- 数据库: {DB_PATH}",
        f"- 扫描间隔: {SCAN_INTERVAL_SECONDS}s",
        f"- 监控标的数: {watch_count}",
        f"- 最近扫描: {last_scan}",
        f"- 最近错误: {last_error}",
    ]

    if recent_alerts:
        lines.append("- 最近提醒：")
        for row in recent_alerts:
            item_name = row["item_name"] or "-"
            lines.append(f"  * {row['created_at']} | {row['alert_type']} | {item_name}")

    return "\n".join(lines)


def watchlist_text(storage: Storage) -> str:
    return _format_watch_rows(storage)


def add_watch_item(storage: Storage, item_name: str) -> str:
    name = item_name.strip()
    if not name:
        return "用法：add 名称"
    created = storage.add_watch_item(name)
    if created:
        return f"已添加监控标的：{name}"
    return f"监控标的已存在：{name}"


def remove_watch_item(storage: Storage, item_name: str) -> str:
    name = item_name.strip()
    if not name:
        return "用法：remove 名称"
    removed = storage.remove_watch_item(name)
    if removed:
        return f"已删除监控标的：{name}"
    return f"未找到监控标的：{name}"


def trigger_scan(storage: Storage, scan_callback: Optional[Callable[[], str]]) -> str:
    if scan_callback is None:
        return "扫描器尚未初始化。"
    return scan_callback()


def trigger_test_alert(storage: Storage) -> str:
    return record_test_alert(storage)


def parse_admin_command(text: str, storage: Storage, scan_callback: Optional[Callable[[], str]] = None) -> Optional[str]:
    t = (text or "").strip()
    if not t:
        return None

    lower = t.lower()

    if lower == "ping":
        return "pong"
    if lower == "help":
        return help_text()
    if lower == "status":
        return status_text(storage)
    if lower == "watchlist":
        return watchlist_text(storage)
    if lower == "scan":
        return trigger_scan(storage, scan_callback)
    if lower == "test alert":
        return trigger_test_alert(storage)
    if lower.startswith("add "):
        return add_watch_item(storage, t[4:])
    if lower.startswith("remove "):
        return remove_watch_item(storage, t[7:])

    return None

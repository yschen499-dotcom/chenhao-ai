from typing import Callable, Optional

from .alerts import build_test_alert_message, record_test_alert
from .config import DB_PATH, SCAN_INTERVAL_SECONDS
from .storage import Storage


def _format_watch_rows(storage: Storage) -> str:
    rows = storage.list_watch_items()
    if not rows:
        return "当前监控列表为空。可使用“添加监控 饰品名称”添加一个饰品。"

    lines = ["当前监控列表："]
    for idx, row in enumerate(rows, start=1):
        state = "启用" if row["enabled"] else "停用"
        lines.append(f"{idx}. {row['item_name']} [{state}]")
    return "\n".join(lines)


def help_text() -> str:
    return (
        "内部测试命令：\n"
        "- 帮助\n"
        "- 状态\n"
        "- 监控列表\n"
        "- 添加监控 饰品名称\n"
        "- 删除监控 饰品名称\n"
        "- 立即扫描\n"
        "- 测试提醒\n"
        "\n"
        "示例：\n"
        "- 添加监控 AK-47 | 红线 (久经沙场)\n"
        "- 删除监控 AK-47 | 红线 (久经沙场)"
    )


def status_text(storage: Storage) -> str:
    last_scan = storage.read_state("last_scan_time", "未扫描")
    last_error = storage.read_state("last_error", "无")
    last_success = storage.read_state("last_successful_scan_time", "暂无")
    watch_count = storage.count_watch_items()
    recent_alerts = storage.recent_alerts(limit=3)

    lines = [
        "内部测试状态：",
        f"- 数据库: {DB_PATH}",
        f"- 扫描间隔: {SCAN_INTERVAL_SECONDS}s",
        f"- 监控标的数: {watch_count}",
        f"- 最近扫描: {last_scan}",
        f"- 最近成功抓价: {last_success}",
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
        return "用法：添加监控 饰品名称"
    created = storage.add_watch_item(name)
    if created:
        return f"已添加监控饰品：{name}"
    return f"监控饰品已存在：{name}"


def remove_watch_item(storage: Storage, item_name: str) -> str:
    name = item_name.strip()
    if not name:
        return "用法：删除监控 饰品名称"
    removed = storage.remove_watch_item(name)
    if removed:
        return f"已删除监控饰品：{name}"
    return f"未找到监控饰品：{name}"


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

    if lower in {"ping", "测试连通", "连通测试"}:
        return "pong"
    if t == "帮助":
        return help_text()
    if t == "状态":
        return status_text(storage)
    if t == "监控列表":
        return watchlist_text(storage)
    if t == "立即扫描":
        return trigger_scan(storage, scan_callback)
    if t == "测试提醒":
        return trigger_test_alert(storage)
    if t.startswith("添加监控"):
        return add_watch_item(storage, t.removeprefix("添加监控").strip())
    if t.startswith("删除监控"):
        return remove_watch_item(storage, t.removeprefix("删除监控").strip())

    return None

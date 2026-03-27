import re
import unicodedata
from typing import TYPE_CHECKING, Callable, Optional

from .alerts import record_test_alert
from .config import get_db_path, get_dingtalk_webhook_url, get_scan_interval_seconds
from .storage import Storage

if TYPE_CHECKING:
    from .collector import SteamDTCollector


def _format_watch_rows(storage: Storage) -> str:
    rows = storage.list_watch_items()
    if not rows:
        return "当前监控列表为空。可使用“添加监控 饰品名称”添加一个饰品。"

    lines = ["当前监控列表："]
    for idx, row in enumerate(rows, start=1):
        state = "启用" if row["enabled"] else "停用"
        lines.append(f"{idx}. {row['item_name']} [{state}]")
    return "\n".join(lines)


# 钉钉里用户发送「帮助」「命令」「功能」时返回的全文，仅此一处定义（勿在其它文件复制一份）。
# 若线上仍看到旧文案（如「立即扫描」），请确认运行的是本仓库代码并已重启 dingtalk_agent.py。
HELP_TEXT = (
    "内部测试命令：\n"
    "\n"
    "- 帮助\n"
    "- 状态\n"
    "- 监控列表\n"
    "- 添加监控 饰品名称\n"
    "- 删除监控 饰品名称\n"
    "- 深度解析 饰品名称\n"
    "- 大盘\n"
    "- 测试早报\n"
    "- 测试周报\n"
    "- 测试月报\n"
    "- 测试提醒\n"
    "\n"
    "示例：\n"
    "- 添加监控 AK-47 | 红线 (久经沙场)\n"
    "- 深度解析 AK-47 | 红线 (久经沙场)\n"
    "- 删除监控 AK-47 | 红线 (久经沙场)\n"
    "\n"
    "说明：\n"
    "- 群聊请先 @机器人 再发命令；单聊直接发文字即可。\n"
    "- 自选由后台自动扫描（默认约每 5 分钟）；在售价/求购价/在售量/求购量较上次波动 ≥3% 可能推送预警。\n"
    "- 深度解析/测试早报周报月报需配置大模型（如通义 AGENT_LLM_*）；定时推送需 Webhook。详见 README。"
)


def help_text() -> str:
    """返回 HELP_TEXT；与 README「命令列表」一致。"""
    return HELP_TEXT


def status_text(storage: Storage) -> str:
    last_scan = storage.read_state("last_scan_time", "未扫描")
    last_error = storage.read_state("last_error", "无")
    last_success = storage.read_state("last_successful_scan_time", "暂无")
    watch_count = storage.count_watch_items()
    recent_alerts = storage.recent_alerts(limit=3)

    wh = get_dingtalk_webhook_url()
    lines = [
        "当前运行状态：",
        f"- 数据库: {get_db_path()}",
        f"- 扫描间隔: {get_scan_interval_seconds()}s",
        f"- 定时报告 Webhook: {'已配置' if wh else '未配置（早报/周报/月报等无法推送）'}",
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


def trigger_test_alert(storage: Storage) -> str:
    return record_test_alert(storage)


def _normalize_dingtalk_user_text(text: str) -> str:
    """
    群聊里常见「@机器人 帮助」：去掉前置 @提及与零宽/特殊空白，便于与指令匹配。
    """
    if not text:
        return ""
    t = re.sub(r"[\u200b-\u200d\ufeff\u2060]", "", text)
    t = re.sub(r"[\u00a0\u3000]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    while True:
        stripped = re.sub(r"^@[^\s@]+\s*", "", t)
        if stripped == t:
            break
        t = stripped
    t = unicodedata.normalize("NFKC", t).strip()
    return t


def _compact_no_space(t: str) -> str:
    """去掉全部空白，避免「大 盘」「测 试 早 报」等无法命中。"""
    return re.sub(r"\s+", "", t)


def parse_admin_command(
    text: str,
    storage: Storage,
    market_overview_callback: Optional[Callable[[], str]] = None,
    collector: Optional["SteamDTCollector"] = None,
    deep_analysis_callback: Optional[Callable[[str], str]] = None,
) -> Optional[str]:
    t = _normalize_dingtalk_user_text(text or "")
    if not t:
        return None

    tc = _compact_no_space(t)
    lower = t.lower()

    if lower in {"ping", "测试连通", "连通测试"}:
        return "pong"
    if tc in {"帮助", "命令", "功能"}:
        return help_text()
    if tc == "状态":
        return status_text(storage)
    if tc == "监控列表":
        return watchlist_text(storage)
    if tc == "大盘":
        if not market_overview_callback:
            return "大盘功能未初始化。"
        try:
            return market_overview_callback()
        except Exception as e:
            return f"大盘执行失败：{e}"
    if tc == "测试提醒":
        return trigger_test_alert(storage)
    if tc == "测试早报":
        if collector is None:
            return "采集器未初始化。"
        from .reports import build_morning_report

        try:
            return build_morning_report(storage, collector)
        except Exception as e:
            return f"测试早报失败：{e}"
    if tc == "测试周报":
        if collector is None:
            return "采集器未初始化。"
        from .reports import build_weekly_report

        try:
            return build_weekly_report(storage, collector)
        except Exception as e:
            return f"测试周报失败：{e}"
    if tc == "测试月报":
        if collector is None:
            return "采集器未初始化。"
        from .reports import build_monthly_report

        try:
            return build_monthly_report(storage, collector)
        except Exception as e:
            return f"测试月报失败：{e}"
    if t.startswith("添加监控"):
        return add_watch_item(storage, t.removeprefix("添加监控").strip())
    if t.startswith("删除监控"):
        return remove_watch_item(storage, t.removeprefix("删除监控").strip())
    _deep = re.compile(r"^深度\s*解析\s*")
    if _deep.match(t):
        if deep_analysis_callback is None:
            return "深度解析未初始化。"
        return deep_analysis_callback(_deep.sub("", t).strip())

    return (
        "未识别指令。请发送「帮助」查看可用命令。\n"
        "说明：单聊直接发文字即可；群聊需要先 @机器人，再输入命令（例如：@机器人 帮助）。\n"
        "常用：状态、监控列表、深度解析、大盘。"
    )

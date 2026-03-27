from typing import Optional, Sequence

from .storage import Storage


def build_test_alert_message() -> str:
    return (
        "【测试提醒】\n"
        "这是一条内部测试提醒。\n"
        "说明当前钉钉推送链路、命令路由和业务骨架都已经接通。"
    )


def record_test_alert(storage: Storage) -> str:
    message = build_test_alert_message()
    storage.add_alert_event("test_alert", "test_alert_manual", message)
    return message


def build_multimetric_alert_key(item_name: str, platform: str, update_time: int) -> str:
    return f"metric_move::{item_name}::{platform.upper()}::{update_time}"


def build_multimetric_alert_message(
    item_name: str,
    platform_label: str,
    threshold_percent: float,
    detail_lines: Sequence[str],
) -> str:
    lines = [
        f"🚨 指标异动提醒 | {item_name}",
        f"平台：{platform_label}",
        f"触发条件：在售价、求购价、在售量、求购量 任一较上次波动幅度 ≥ {threshold_percent:g}%",
        "",
        "本次满足条件的指标：",
    ]
    for s in detail_lines:
        lines.append(f"  · {s}")
    lines.append("")
    lines.append("说明：数据来自 SteamDT 接口与本地快照；不构成投资建议。")
    return "\n".join(lines)


def record_triggered_alert(storage: Storage, alert_type: str, alert_key: str, message: str, item_name: str = "") -> bool:
    return storage.add_alert_event(alert_type, alert_key, message, item_name)


def build_scan_message(watch_count: int) -> str:
    return (
        "【手动扫描】\n"
        f"当前监控标的数：{watch_count}\n"
        "内部测试版的完整采集与策略引擎还没接入真实市场数据，"
        "本次扫描用于验证命令路由、状态写入与提醒链路。"
    )

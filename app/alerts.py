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

def build_price_alert_message(
    item_name: str,
    platform_label: str,
    current_price: float,
    previous_price: float,
    bidding_price: float,
    sell_count: int,
    change_pct: float,
) -> str:
    delta = current_price - previous_price
    arrow = "🔺" if delta > 0 else "🔻"
    return (
        f"🚨 单品异动提醒 | {item_name}\n"
        f"平台：{platform_label}\n"
        f"当前在售价：¥{current_price:.2f}\n"
        f"上次在售价：¥{previous_price:.2f}\n"
        f"价格变化：{arrow}¥{abs(delta):.2f} ({arrow}{abs(change_pct):.2f}%)\n"
        f"当前求购价：¥{bidding_price:.2f}\n"
        f"当前在售量：{sell_count}\n"
        "触发条件：任意平台较上次涨跌超过 3%"
    )


def build_alert_key(item_name: str, platform: str, update_time: int) -> str:
    return f"price_move::{item_name}::{platform.upper()}::{update_time}"


def record_triggered_alert(storage: Storage, alert_type: str, alert_key: str, message: str, item_name: str = "") -> bool:
    return storage.add_alert_event(alert_type, alert_key, message, item_name)


def build_scan_message(watch_count: int) -> str:
    return (
        "【手动扫描】\n"
        f"当前监控标的数：{watch_count}\n"
        "内部测试版的完整采集与策略引擎还没接入真实市场数据，"
        "本次扫描用于验证命令路由、状态写入与提醒链路。"
    )

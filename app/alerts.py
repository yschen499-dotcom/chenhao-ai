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


def build_scan_message(watch_count: int) -> str:
    return (
        "【手动扫描】\n"
        f"当前监控标的数：{watch_count}\n"
        "内部测试版的完整采集与策略引擎还没接入真实市场数据，"
        "本次扫描用于验证命令路由、状态写入与提醒链路。"
    )

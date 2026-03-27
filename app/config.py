import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def _as_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def get_db_path() -> Path:
    return Path(os.getenv("AGENT_DB_PATH", str(DATA_DIR / "app.db")))


def get_steamdt_base_cache_path() -> Path:
    return Path(os.getenv("AGENT_STEAMDT_BASE_CACHE_PATH", str(DATA_DIR / "steamdt_base.json")))


def get_max_reply_chars() -> int:
    return int(os.getenv("AGENT_MAX_REPLY_CHARS", "3000"))


def get_log_level() -> str:
    return os.getenv("DINGTALK_AGENT_LOG_LEVEL", "INFO").upper()


def get_scan_interval_seconds() -> int:
    """后台轮询间隔（秒）；默认 300=5 分钟，可用 AGENT_SCAN_INTERVAL_SECONDS 覆盖。"""
    return int(os.getenv("AGENT_SCAN_INTERVAL_SECONDS", "300"))


def get_alert_threshold_percent() -> float:
    return float(os.getenv("AGENT_ALERT_THRESHOLD_PERCENT", "3"))


def get_volatility_lookback_count() -> int:
    """用于异常波动：取最近 N 条同平台历史在售价（含后台扫描）。"""
    return max(4, int(os.getenv("AGENT_VOLATILITY_LOOKBACK", "12")))


def get_volatility_z_threshold() -> float:
    """|现价 - 历史均值| / 标准差 超过该值则视为异常（在满足最小幅变化的前提下）。"""
    return float(os.getenv("AGENT_VOLATILITY_Z_THRESHOLD", "2.5"))


def get_volatility_min_change_pct() -> float:
    """与上一快照的涨跌幅绝对值下限，避免横盘微小抖动误报。"""
    return float(os.getenv("AGENT_VOLATILITY_MIN_CHANGE_PCT", "1.5"))


def get_volatility_min_std_ratio() -> float:
    """标准差 / 均值 低于该比例时认为样本几乎横盘，不做 z-score 异动。"""
    return float(os.getenv("AGENT_VOLATILITY_MIN_STD_RATIO", "0.001"))


def get_volatility_min_samples() -> int:
    """参与均值/标准差计算的最少历史点数（不含当前价）。"""
    return max(3, int(os.getenv("AGENT_VOLATILITY_MIN_SAMPLES", "4")))


def is_background_scan_enabled() -> bool:
    return _as_bool("AGENT_ENABLE_BACKGROUND_SCAN", "true")


def get_admin_sender_id() -> str:
    return os.getenv("AGENT_ADMIN_SENDER_ID", "").strip()


def is_local_commands_enabled() -> bool:
    return _as_bool("AGENT_ENABLE_LOCAL_COMMANDS", "false")


def get_steamdt_api_base() -> str:
    """
    SteamDT 开放平台 API 根地址。官方文档写为「国内外通用」的 open.steamdt.com。
    若仅不开 VPN 时抓价失败，多为本地网络/运营商对该域名的路由或策略问题，可尝试代理或在系统层配置 VPN 分流。
    """
    return os.getenv("AGENT_STEAMDT_API_BASE", "https://open.steamdt.com").rstrip("/")


def get_steamdt_api_key() -> str:
    return os.getenv("AGENT_STEAMDT_API_KEY", "").strip()


def get_steamdt_price_platform() -> str:
    return os.getenv("AGENT_STEAMDT_PRICE_PLATFORM", "BUFF").strip().upper()


def get_steamdt_request_timeout_seconds() -> int:
    return int(os.getenv("AGENT_STEAMDT_REQUEST_TIMEOUT_SECONDS", "15"))


def get_steamdt_section_broad_url() -> str:
    """
    SteamDT 网页「综合大盘」SSR 页。
    默认使用备案主站入口 steamdt.cn（与 steamdt.com 同源，部分网络下走 .cn 更稳）。
    若你环境必须固定某一域名，可设环境变量 AGENT_STEAMDT_SECTION_BROAD_URL。
    """
    return os.getenv(
        "AGENT_STEAMDT_SECTION_BROAD_URL",
        "https://steamdt.cn/section?type=BROAD",
    ).strip()


def get_steamdt_home_url() -> str:
    """
    SteamDT 官网首页（默认 https://steamdt.com/）。
    SSR 内嵌的 todayStatistics / yesterdayStatistics 含饰品成交量、成交额及环比，与首页卡片一致。
    可通过 AGENT_STEAMDT_HOME_URL 覆盖（例如网络对 .com 不通时换镜像域名）。
    """
    return os.getenv("AGENT_STEAMDT_HOME_URL", "https://steamdt.com/").strip()


def get_scheduler_timezone() -> str:
    return os.getenv("AGENT_SCHEDULER_TIMEZONE", "Asia/Shanghai").strip()


def get_dingtalk_webhook_url() -> str:
    """自定义机器人 Webhook，用于定时早报/周报/月报推送。"""
    return (
        os.getenv("AGENT_DINGTALK_WEBHOOK_URL", "").strip()
        or os.getenv("DINGTALK_CUSTOM_ROBOT_WEBHOOK", "").strip()
    )


def is_scheduler_enabled() -> bool:
    return _as_bool("AGENT_SCHEDULER_ENABLED", "true")


def get_signal_sell_drop_for_bid_signal() -> float:
    """在售相对上轮减少比例达到该值（正数），且求购走强时触发「扫货」类信号。"""
    return float(os.getenv("AGENT_SIGNAL_SELL_DROP_FOR_BID", "0.05"))


def get_signal_bid_up_min_ratio() -> float:
    """求购笔数相对上轮增加比例下限。"""
    return float(os.getenv("AGENT_SIGNAL_BID_UP_MIN_RATIO", "0.08"))


def get_signal_suppress_price_max_pct() -> float:
    """在售价跌幅超过该百分点（如 3 表示 3%）且在售同步减少时，提示「压价吸货」类信号。"""
    return float(os.getenv("AGENT_SIGNAL_SUPPRESS_PRICE_MAX_PCT", "3"))


def get_signal_suppress_sell_drop_ratio() -> float:
    """与「压价」信号联动的在售减少比例阈值（正数）。"""
    return float(os.getenv("AGENT_SIGNAL_SUPPRESS_SELL_DROP_RATIO", "0.03"))


def get_signal_sell_vol_shock_abs_ratio() -> float:
    """在售量相对上轮变化比例绝对值超过该值时提示「剧烈挂单」。"""
    return float(os.getenv("AGENT_SIGNAL_SELL_VOL_SHOCK_RATIO", "0.25"))


def get_signal_sell_vol_shock_min_delta() -> int:
    """在售量绝对变动超过该件数也视为剧烈（防低基数比例失真）。"""
    return max(5, int(os.getenv("AGENT_SIGNAL_SELL_VOL_SHOCK_DELTA", "40")))


def get_signal_flat_price_max_pct() -> float:
    """在售剧变但价格涨跌幅低于该值（%）时提示「假挂单/画线」嫌疑。"""
    return float(os.getenv("AGENT_SIGNAL_FLAT_PRICE_MAX_PCT", "0.6"))


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_llm_api_key() -> str:
    return os.getenv("AGENT_LLM_API_KEY", "").strip()


def get_llm_base_url() -> str:
    """
    OpenAI 兼容根路径（勿含 /chat/completions）。
    通义百炼：AGENT_LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
    """
    return os.getenv("AGENT_LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")


def get_llm_model() -> str:
    """通义示例：qwen-plus、qwen-turbo；OpenAI 示例：gpt-4o-mini。"""
    return os.getenv("AGENT_LLM_MODEL", "gpt-4o-mini").strip()


def get_llm_timeout_seconds() -> int:
    return int(os.getenv("AGENT_LLM_TIMEOUT_SECONDS", "120"))


def is_llm_configured() -> bool:
    return bool(get_llm_api_key())

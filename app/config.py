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
    return int(os.getenv("AGENT_SCAN_INTERVAL_SECONDS", "60"))


def get_alert_threshold_percent() -> float:
    return float(os.getenv("AGENT_ALERT_THRESHOLD_PERCENT", "3"))


def is_background_scan_enabled() -> bool:
    return _as_bool("AGENT_ENABLE_BACKGROUND_SCAN", "true")


def get_admin_sender_id() -> str:
    return os.getenv("AGENT_ADMIN_SENDER_ID", "").strip()


def is_local_commands_enabled() -> bool:
    return _as_bool("AGENT_ENABLE_LOCAL_COMMANDS", "false")


def get_steamdt_api_base() -> str:
    return os.getenv("AGENT_STEAMDT_API_BASE", "https://open.steamdt.com").rstrip("/")


def get_steamdt_api_key() -> str:
    return os.getenv("AGENT_STEAMDT_API_KEY", "").strip()


def get_steamdt_price_platform() -> str:
    return os.getenv("AGENT_STEAMDT_PRICE_PLATFORM", "BUFF").strip().upper()


def get_steamdt_request_timeout_seconds() -> int:
    return int(os.getenv("AGENT_STEAMDT_REQUEST_TIMEOUT_SECONDS", "15"))


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

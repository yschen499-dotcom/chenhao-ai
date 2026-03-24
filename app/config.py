import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.getenv("AGENT_DB_PATH", str(DATA_DIR / "app.db")))
STEAMDT_BASE_CACHE_PATH = Path(os.getenv("AGENT_STEAMDT_BASE_CACHE_PATH", str(DATA_DIR / "steamdt_base.json")))
MAX_REPLY_CHARS = int(os.getenv("AGENT_MAX_REPLY_CHARS", "3000"))
LOG_LEVEL = os.getenv("DINGTALK_AGENT_LOG_LEVEL", "INFO").upper()
SCAN_INTERVAL_SECONDS = int(os.getenv("AGENT_SCAN_INTERVAL_SECONDS", "60"))
ENABLE_LOCAL_COMMANDS = os.getenv("AGENT_ENABLE_LOCAL_COMMANDS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
STEAMDT_API_BASE = os.getenv("AGENT_STEAMDT_API_BASE", "https://open.steamdt.com").rstrip("/")
STEAMDT_API_KEY = os.getenv("AGENT_STEAMDT_API_KEY", "").strip()
STEAMDT_PRICE_PLATFORM = os.getenv("AGENT_STEAMDT_PRICE_PLATFORM", "BUFF").strip().upper()
STEAMDT_REQUEST_TIMEOUT_SECONDS = int(os.getenv("AGENT_STEAMDT_REQUEST_TIMEOUT_SECONDS", "15"))


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

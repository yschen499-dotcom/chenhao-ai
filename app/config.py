import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = Path(os.getenv("AGENT_DB_PATH", str(DATA_DIR / "app.db")))
MAX_REPLY_CHARS = int(os.getenv("AGENT_MAX_REPLY_CHARS", "3000"))
LOG_LEVEL = os.getenv("DINGTALK_AGENT_LOG_LEVEL", "INFO").upper()
SCAN_INTERVAL_SECONDS = int(os.getenv("AGENT_SCAN_INTERVAL_SECONDS", "60"))
ENABLE_LOCAL_COMMANDS = os.getenv("AGENT_ENABLE_LOCAL_COMMANDS", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

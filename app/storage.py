import sqlite3
from datetime import datetime
from typing import Iterable, List

from .config import DB_PATH, ensure_data_dir


def _utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


class Storage:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        ensure_data_dir()
        self.init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS watchlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL UNIQUE,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    category TEXT NOT NULL DEFAULT 'manual',
                    target_price REAL,
                    upper_threshold REAL,
                    lower_threshold REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS price_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    price REAL NOT NULL,
                    volume REAL,
                    source TEXT,
                    captured_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alert_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    alert_type TEXT NOT NULL,
                    item_name TEXT,
                    alert_key TEXT NOT NULL UNIQUE,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )

    def list_watch_items(self) -> List[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, item_name, enabled, category, target_price, upper_threshold,
                       lower_threshold, created_at, updated_at
                FROM watchlists
                ORDER BY item_name COLLATE NOCASE
                """
            ).fetchall()
        return rows

    def list_enabled_watch_item_names(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT item_name
                FROM watchlists
                WHERE enabled = 1
                ORDER BY item_name COLLATE NOCASE
                """
            ).fetchall()
        return [row["item_name"] for row in rows]

    def add_watch_item(self, item_name: str, category: str = "manual") -> bool:
        now = _utcnow()
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO watchlists (
                        item_name, enabled, category, created_at, updated_at
                    ) VALUES (?, 1, ?, ?, ?)
                    """,
                    (item_name, category, now, now),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def remove_watch_item(self, item_name: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute("DELETE FROM watchlists WHERE item_name = ?", (item_name,))
            return cur.rowcount > 0

    def write_state(self, key: str, value: str) -> None:
        now = _utcnow()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO system_state (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (key, value, now),
            )

    def read_state(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM system_state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def list_state(self) -> List[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT key, value, updated_at FROM system_state ORDER BY key COLLATE NOCASE"
            ).fetchall()
        return rows

    def add_alert_event(self, alert_type: str, alert_key: str, message: str, item_name: str = "") -> bool:
        now = _utcnow()
        with self._connect() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO alert_events (alert_type, item_name, alert_key, message, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (alert_type, item_name, alert_key, message, now),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def recent_alerts(self, limit: int = 5) -> List[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT alert_type, item_name, message, created_at
                FROM alert_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return rows

    def save_price_snapshot(self, item_name: str, price: float, volume: float = 0.0, source: str = "manual") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO price_snapshots (item_name, price, volume, source, captured_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (item_name, price, volume, source, _utcnow()),
            )

    def latest_price_snapshot(self, item_name: str):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT item_name, price, volume, source, captured_at
                FROM price_snapshots
                WHERE item_name = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (item_name,),
            ).fetchone()
        return row

    def count_watch_items(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM watchlists").fetchone()
        return int(row["count"]) if row else 0

    def seed_watch_items(self, item_names: Iterable[str]) -> int:
        inserted = 0
        for item_name in item_names:
            if self.add_watch_item(item_name.strip()):
                inserted += 1
        return inserted

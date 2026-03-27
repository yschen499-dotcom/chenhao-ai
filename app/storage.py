import sqlite3
from datetime import datetime
from typing import Iterable, List, Optional

from .config import ensure_data_dir, get_db_path


def _utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


class Storage:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path) if db_path else str(get_db_path())
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
                    captured_at TEXT NOT NULL,
                    scan_channel TEXT NOT NULL DEFAULT 'background'
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
            self._migrate_price_snapshots_scan_channel()
            self._migrate_price_snapshots_bid_volume()
            self._migrate_price_snapshots_bid_price()
            self._migrate_market_snapshots()

    def _migrate_market_snapshots(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    trade_date TEXT NOT NULL,
                    slot TEXT NOT NULL,
                    index_value REAL NOT NULL,
                    yesterday_close REAL,
                    high_price REAL,
                    low_price REAL,
                    rise_fall_pct REAL,
                    up_num INTEGER,
                    flat_num INTEGER,
                    down_num INTEGER,
                    captured_at TEXT NOT NULL,
                    PRIMARY KEY (trade_date, slot)
                )
                """
            )

    def upsert_market_snapshot(
        self,
        trade_date: str,
        slot: str,
        *,
        index_value: float,
        yesterday_close: float,
        high_price: float,
        low_price: float,
        rise_fall_pct: float,
        up_num: int,
        flat_num: int,
        down_num: int,
    ) -> None:
        now = _utcnow()
        td = (trade_date or "").strip()
        sl = (slot or "").strip().lower()
        if not td or sl not in {"morning", "evening"}:
            raise ValueError("trade_date 或 slot 无效")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO market_snapshots (
                    trade_date, slot, index_value, yesterday_close, high_price, low_price,
                    rise_fall_pct, up_num, flat_num, down_num, captured_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(trade_date, slot) DO UPDATE SET
                    index_value = excluded.index_value,
                    yesterday_close = excluded.yesterday_close,
                    high_price = excluded.high_price,
                    low_price = excluded.low_price,
                    rise_fall_pct = excluded.rise_fall_pct,
                    up_num = excluded.up_num,
                    flat_num = excluded.flat_num,
                    down_num = excluded.down_num,
                    captured_at = excluded.captured_at
                """,
                (
                    td,
                    sl,
                    float(index_value),
                    float(yesterday_close),
                    float(high_price),
                    float(low_price),
                    float(rise_fall_pct),
                    int(up_num),
                    int(flat_num),
                    int(down_num),
                    now,
                ),
            )

    def get_market_snapshot(self, trade_date: str, slot: str):
        td = (trade_date or "").strip()
        sl = (slot or "").strip().lower()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM market_snapshots WHERE trade_date = ? AND slot = ?",
                (td, sl),
            ).fetchone()
        return row

    def list_market_snapshots_in_range(self, start_date: str, end_date: str) -> List[sqlite3.Row]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM market_snapshots
                WHERE trade_date >= ? AND trade_date <= ?
                ORDER BY trade_date ASC, slot ASC
                """,
                (start_date.strip(), end_date.strip()),
            ).fetchall()
        return rows

    def _migrate_price_snapshots_scan_channel(self) -> None:
        with self._connect() as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(price_snapshots)").fetchall()}
            if "scan_channel" not in cols:
                conn.execute(
                    "ALTER TABLE price_snapshots ADD COLUMN scan_channel TEXT NOT NULL DEFAULT 'background'"
                )

    def _migrate_price_snapshots_bid_volume(self) -> None:
        """求购笔数（与在售量对照，用于扫货/压价等启发式信号）。"""
        with self._connect() as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(price_snapshots)").fetchall()}
            if "bid_volume" not in cols:
                conn.execute("ALTER TABLE price_snapshots ADD COLUMN bid_volume REAL NOT NULL DEFAULT 0")

    def _migrate_price_snapshots_bid_price(self) -> None:
        """求购价（与在售价对照，用于异动预警）。"""
        with self._connect() as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(price_snapshots)").fetchall()}
            if "bid_price" not in cols:
                conn.execute("ALTER TABLE price_snapshots ADD COLUMN bid_price REAL NOT NULL DEFAULT 0")

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

    def save_price_snapshot(
        self,
        item_name: str,
        price: float,
        volume: float = 0.0,
        source: str = "manual",
        *,
        bid_volume: float = 0.0,
        bid_price: float = 0.0,
        scan_channel: str = "background",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO price_snapshots (
                    item_name, price, volume, bid_volume, bid_price, source, captured_at, scan_channel
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_name,
                    price,
                    volume,
                    float(bid_volume),
                    float(bid_price),
                    source,
                    _utcnow(),
                    scan_channel,
                ),
            )

    def previous_price_snapshot(
        self,
        item_name: str,
        source: Optional[str] = None,
        *,
        scan_channel: Optional[str] = None,
    ):
        """
        Second-latest row for optional (item, source, scan_channel) filter.
        scan_channel=None: consider all channels (legacy / 后台摘要).
        """
        with self._connect() as conn:
            if source:
                if scan_channel is not None:
                    row = conn.execute(
                        """
                        SELECT item_name, price, volume, COALESCE(bid_volume, 0) AS bid_volume,
                               COALESCE(bid_price, 0) AS bid_price,
                               source, captured_at, scan_channel
                        FROM price_snapshots
                        WHERE item_name = ? AND source = ? AND scan_channel = ?
                        ORDER BY id DESC
                        LIMIT 1 OFFSET 1
                        """,
                        (item_name, source, scan_channel),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT item_name, price, volume, COALESCE(bid_volume, 0) AS bid_volume,
                               COALESCE(bid_price, 0) AS bid_price,
                               source, captured_at, scan_channel
                        FROM price_snapshots
                        WHERE item_name = ? AND source = ?
                        ORDER BY id DESC
                        LIMIT 1 OFFSET 1
                        """,
                        (item_name, source),
                    ).fetchone()
            else:
                if scan_channel is not None:
                    row = conn.execute(
                        """
                        SELECT item_name, price, volume, COALESCE(bid_volume, 0) AS bid_volume,
                               COALESCE(bid_price, 0) AS bid_price,
                               source, captured_at, scan_channel
                        FROM price_snapshots
                        WHERE item_name = ? AND scan_channel = ?
                        ORDER BY id DESC
                        LIMIT 1 OFFSET 1
                        """,
                        (item_name, scan_channel),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT item_name, price, volume, COALESCE(bid_volume, 0) AS bid_volume,
                               COALESCE(bid_price, 0) AS bid_price,
                               source, captured_at, scan_channel
                        FROM price_snapshots
                        WHERE item_name = ?
                        ORDER BY id DESC
                        LIMIT 1 OFFSET 1
                        """,
                        (item_name,),
                    ).fetchone()
        return row

    def recent_sell_prices_for_source(
        self,
        item_name: str,
        source: str,
        limit: int,
        *,
        scan_channel: Optional[str] = None,
    ) -> List[float]:
        """
        按 id 从旧到新返回在售价序列（用于波动率统计）。不含本次尚未写入的快照。
        """
        src = source.upper()
        lim = max(1, int(limit))
        with self._connect() as conn:
            if scan_channel is not None:
                rows = conn.execute(
                    """
                    SELECT price FROM price_snapshots
                    WHERE item_name = ? AND UPPER(source) = ? AND scan_channel = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (item_name, src, scan_channel, lim),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT price FROM price_snapshots
                    WHERE item_name = ? AND UPPER(source) = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (item_name, src, lim),
                ).fetchall()
        return [float(r["price"]) for r in reversed(rows)]

    def latest_price_snapshot(
        self,
        item_name: str,
        source: Optional[str] = None,
        *,
        scan_channel: Optional[str] = None,
    ):
        with self._connect() as conn:
            if source:
                if scan_channel is not None:
                    row = conn.execute(
                        """
                        SELECT item_name, price, volume, COALESCE(bid_volume, 0) AS bid_volume,
                               COALESCE(bid_price, 0) AS bid_price,
                               source, captured_at, scan_channel
                        FROM price_snapshots
                        WHERE item_name = ? AND source = ? AND scan_channel = ?
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (item_name, source, scan_channel),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT item_name, price, volume, COALESCE(bid_volume, 0) AS bid_volume,
                               COALESCE(bid_price, 0) AS bid_price,
                               source, captured_at, scan_channel
                        FROM price_snapshots
                        WHERE item_name = ? AND source = ?
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (item_name, source),
                    ).fetchone()
            else:
                if scan_channel is not None:
                    row = conn.execute(
                        """
                        SELECT item_name, price, volume, COALESCE(bid_volume, 0) AS bid_volume,
                               COALESCE(bid_price, 0) AS bid_price,
                               source, captured_at, scan_channel
                        FROM price_snapshots
                        WHERE item_name = ? AND scan_channel = ?
                        ORDER BY id DESC
                        LIMIT 1
                        """,
                        (item_name, scan_channel),
                    ).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT item_name, price, volume, COALESCE(bid_volume, 0) AS bid_volume,
                               COALESCE(bid_price, 0) AS bid_price,
                               source, captured_at, scan_channel
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
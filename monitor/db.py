"""
价格监控 — SQLite 存储层

表结构：
  products        — 商品主表（URL 去重）
  ingestion_runs  — 每次入库记录
  snapshots       — 每次入库时每个商品的价格/销量快照

用法：
    db = MonitorDB("path/to/monitor.db")
    db.ensure_schema()
    db.add_run(...) / db.get_all_products(...)
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY,
    platform    TEXT    NOT NULL,
    product_id  TEXT,                -- 平台 SKU / offer ID
    title       TEXT,
    brand       TEXT,
    url         TEXT    NOT NULL UNIQUE,
    first_seen  TEXT    NOT NULL,
    last_seen   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id             INTEGER PRIMARY KEY,
    platform       TEXT    NOT NULL,
    category       TEXT,
    source_dir     TEXT,               -- CSV 来源目录
    ingested_at    TEXT    NOT NULL,
    product_count  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS snapshots (
    id            INTEGER PRIMARY KEY,
    run_id        INTEGER NOT NULL REFERENCES ingestion_runs(id),
    product_id    INTEGER NOT NULL REFERENCES products(id),
    price         REAL,
    sales         INTEGER,
    rank          INTEGER,
    strategy      TEXT,               -- 🔥 必上 / 👍 推荐 / 💡 暗马 / 📌 关注
    extra_data    TEXT,               -- JSON: 平台扩展字段
    snapshot_at   TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_run     ON snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_product ON snapshots(product_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_at      ON snapshots(snapshot_at);
CREATE INDEX IF NOT EXISTS idx_products_url      ON products(url);
"""


class MonitorDB:
    """SQLite 存储层封装"""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None

    # ── 连接管理 ──

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ── Schema ──

    def ensure_schema(self):
        """创建表（幂等）"""
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    # ── 商品 ──

    def upsert_product(self, platform: str, url: str, title: str = "",
                       brand: str = "", product_id: str = "") -> int:
        """插入或更新商品，返回 product.id"""
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute("""
            INSERT INTO products (platform, product_id, title, brand, url, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title       = COALESCE(NULLIF(?, ''), title),
                brand       = COALESCE(NULLIF(?, ''), brand),
                product_id  = COALESCE(NULLIF(?, ''), product_id),
                last_seen   = ?
        """, (platform, product_id, title, brand, url, now, now,
              title, brand, product_id, now))
        self.conn.commit()
        # 返回 id（ON CONFLICT 后 last_insert_rowid 不准，需 re-query）
        row = self.conn.execute("SELECT id FROM products WHERE url = ?", (url,)).fetchone()
        return row["id"] if row else cur.lastrowid

    # ── 入库记录 ──

    def create_run(self, platform: str, category: str = "",
                   source_dir: str = "") -> int:
        """创建一次入库记录，返回 run.id"""
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute("""
            INSERT INTO ingestion_runs (platform, category, source_dir, ingested_at)
            VALUES (?, ?, ?, ?)
        """, (platform, category, source_dir, now))
        self.conn.commit()
        return cur.lastrowid

    def update_run_count(self, run_id: int, count: int):
        self.conn.execute("UPDATE ingestion_runs SET product_count = ? WHERE id = ?",
                          (count, run_id))
        self.conn.commit()

    # ── 快照 ──

    def add_snapshot(self, run_id: int, product_db_id: int,
                     price: float, sales: int = None, rank: int = None,
                     strategy: str = "", extra: dict = None):
        """写入一条快照"""
        now = datetime.now(timezone.utc).isoformat()
        extra_json = json.dumps(extra, ensure_ascii=False) if extra else None
        self.conn.execute("""
            INSERT INTO snapshots (run_id, product_id, price, sales, rank, strategy, extra_data, snapshot_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (run_id, product_db_id, price, sales, rank, strategy, extra_json, now))
        self.conn.commit()

    # ── 查询 ──

    def get_all_products(self, platform: str = None) -> list[sqlite3.Row]:
        if platform:
            return self.conn.execute(
                "SELECT * FROM products WHERE platform = ? ORDER BY id", (platform,)
            ).fetchall()
        return self.conn.execute("SELECT * FROM products ORDER BY platform, id").fetchall()

    def get_runs(self, platform: str = None, limit: int = 20) -> list[sqlite3.Row]:
        if platform:
            return self.conn.execute(
                "SELECT * FROM ingestion_runs WHERE platform = ? ORDER BY id DESC LIMIT ?",
                (platform, limit)
            ).fetchall()
        return self.conn.execute(
            "SELECT * FROM ingestion_runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def get_snapshots_for_product(self, product_db_id: int) -> list[sqlite3.Row]:
        """获取某个商品的全部快照（按时间升序）"""
        return self.conn.execute("""
            SELECT s.*, r.ingested_at
            FROM snapshots s
            JOIN ingestion_runs r ON r.id = s.run_id
            WHERE s.product_id = ?
            ORDER BY s.snapshot_at
        """, (product_db_id,)).fetchall()

    def get_latest_snapshots(self, run_id: int = None) -> list[sqlite3.Row]:
        """获取某次入库或最新一次的快照"""
        if run_id:
            return self.conn.execute("""
                SELECT s.*, p.platform, p.url, p.title, p.brand
                FROM snapshots s
                JOIN products p ON p.id = s.product_id
                WHERE s.run_id = ?
                ORDER BY s.strategy, s.rank
            """, (run_id,)).fetchall()
        # 最新一次入库
        last = self.conn.execute(
            "SELECT MAX(id) as mid FROM ingestion_runs"
        ).fetchone()
        if not last or not last["mid"]:
            return []
        return self.get_latest_snapshots(last["mid"])

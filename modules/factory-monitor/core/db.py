"""
1688 Factory Monitor — SQLite 存储层

表设计见 docs/spec.md 第五章。
"""

import sqlite3
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS factories (
    id              INTEGER PRIMARY KEY,
    shop_name       TEXT    NOT NULL,
    shop_url        TEXT    NOT NULL UNIQUE,
    card_url        TEXT,
    catalog_url     TEXT,
    cert_level      TEXT,
    has_yellow_tag  INTEGER DEFAULT 0,
    location        TEXT,
    years_on_1688   INTEGER,
    gold_medal_rank TEXT,
    labels_json     TEXT,
    area_sqm        INTEGER,
    employees       TEXT,
    product_tags    TEXT,
    status          TEXT    NOT NULL DEFAULT 'active',
    first_seen      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS factory_snapshots (
    id               INTEGER PRIMARY KEY,
    factory_id       INTEGER NOT NULL REFERENCES factories(id),
    total_products   INTEGER,
    response_rate    REAL,
    fulfillment_rate REAL,
    repurchase_rate  REAL,
    top10_avg_sales  REAL,
    snapshot_time    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS product_snapshots (
    id             INTEGER PRIMARY KEY,
    factory_id     INTEGER NOT NULL REFERENCES factories(id),
    product_id     TEXT,
    title          TEXT,
    price          REAL,
    sales_30d      INTEGER,
    sales_tag      TEXT,
    category_tags  TEXT,
    snapshot_time  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    id            INTEGER PRIMARY KEY,
    factory_id    INTEGER NOT NULL REFERENCES factories(id),
    alert_level   TEXT    NOT NULL,
    alert_type    TEXT    NOT NULL,
    message       TEXT,
    triggered_at  TEXT    NOT NULL,
    resolved      INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_factory_snapshots_factory ON factory_snapshots(factory_id);
CREATE INDEX IF NOT EXISTS idx_factory_snapshots_time   ON factory_snapshots(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_product_snapshots_factory ON product_snapshots(factory_id);
CREATE INDEX IF NOT EXISTS idx_alerts_factory           ON alerts(factory_id);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved          ON alerts(resolved);
"""


class MonitorDB:
    """SQLite 存储层"""

    def __init__(self, db_path: str | Path = "data/monitor.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

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
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    # ── 工厂 ──

    def upsert_factory(self, shop_name: str, shop_url: str,
                       card_url: str = "", catalog_url: str = "",
                       cert_level: str = "", has_yellow_tag: bool = False,
                       location: str = "", years_on_1688: int = 0,
                       gold_medal_rank: str = "",
                       labels: list[str] = None,
                       area_sqm: int = 0, employees: str = "",
                       product_tags: str = "") -> int:
        """插入或更新工厂，返回 factory.id"""
        now = datetime.now(timezone.utc).isoformat()
        labels_json = json.dumps(labels, ensure_ascii=False) if labels else None
        self.conn.execute("""
            INSERT INTO factories
                (shop_name, shop_url, card_url, catalog_url,
                 cert_level, has_yellow_tag,
                 location, years_on_1688, gold_medal_rank, labels_json,
                 area_sqm, employees, product_tags, status, first_seen)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, 'active', ?)
            ON CONFLICT(shop_url) DO UPDATE SET
                shop_name      = COALESCE(NULLIF(?,''), shop_name),
                card_url       = COALESCE(NULLIF(?,''), card_url),
                catalog_url    = COALESCE(NULLIF(?,''), catalog_url),
                cert_level     = COALESCE(NULLIF(?,''), cert_level),
                has_yellow_tag = COALESCE(?, has_yellow_tag),
                location       = COALESCE(NULLIF(?,''), location),
                years_on_1688  = COALESCE(?, years_on_1688),
                labels_json    = COALESCE(NULLIF(?,''), labels_json),
                area_sqm       = COALESCE(?, area_sqm),
                employees      = COALESCE(NULLIF(?,''), employees),
                product_tags   = COALESCE(NULLIF(?,''), product_tags)
        """, (shop_name, shop_url, card_url, catalog_url,
              cert_level, int(has_yellow_tag),
              location, years_on_1688, gold_medal_rank, labels_json,
              area_sqm, employees, product_tags, now,
              shop_name, card_url, catalog_url,
              cert_level, int(has_yellow_tag),
              location, years_on_1688, labels_json,
              area_sqm, employees, product_tags))
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM factories WHERE shop_url = ?", (shop_url,)
        ).fetchone()
        return row["id"] if row else -1

    def get_active_factories(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM factories WHERE status = 'active' ORDER BY id"
        ).fetchall()

    def get_factories_without_catalog_url(self) -> list[sqlite3.Row]:
        """返回 card_url 有值但 catalog_url 为空的工厂"""
        return self.conn.execute("""
            SELECT * FROM factories
            WHERE card_url IS NOT NULL AND card_url != ''
              AND (catalog_url IS NULL OR catalog_url = '')
            ORDER BY id
        """).fetchall()

    def get_factories_with_catalog_url(self) -> list[sqlite3.Row]:
        """返回有 catalog_url 的 active 工厂"""
        return self.conn.execute("""
            SELECT * FROM factories
            WHERE status = 'active'
              AND catalog_url IS NOT NULL AND catalog_url != ''
            ORDER BY id
        """).fetchall()

    def get_all_factories(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM factories ORDER BY id"
        ).fetchall()

    def update_factory_status(self, factory_id: int, status: str):
        self.conn.execute(
            "UPDATE factories SET status = ? WHERE id = ?",
            (status, factory_id)
        )
        self.conn.commit()

    # ── 快照 ──

    def add_factory_snapshot(self, factory_id: int,
                             total_products: int = None,
                             response_rate: float = None,
                             fulfillment_rate: float = None,
                             repurchase_rate: float = None,
                             top10_avg_sales: float = None) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute("""
            INSERT INTO factory_snapshots
                (factory_id, total_products, response_rate, fulfillment_rate,
                 repurchase_rate, top10_avg_sales, snapshot_time)
            VALUES (?,?,?,?,?,?,?)
        """, (factory_id, total_products, response_rate,
              fulfillment_rate, repurchase_rate,
              top10_avg_sales, now))
        self.conn.commit()
        return cur.lastrowid

    def add_product_snapshots(self, factory_id: int,
                              products: list[dict]) -> int:
        """批量写入商品快照。products: [{product_id, title, price, sales_30d, sales_tag, category_tags}]"""
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (factory_id, p.get("product_id"), p.get("title"),
             p.get("price"), p.get("sales_30d"), p.get("sales_tag"),
             p.get("category_tags"), now)
            for p in products
        ]
        self.conn.executemany("""
            INSERT INTO product_snapshots
                (factory_id, product_id, title, price, sales_30d,
                 sales_tag, category_tags, snapshot_time)
            VALUES (?,?,?,?,?,?,?,?)
        """, rows)
        self.conn.commit()
        return len(rows)

    # ── 预警 ──

    def add_alert(self, factory_id: int, alert_level: str,
                  alert_type: str, message: str = ""):
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute("""
            INSERT INTO alerts
                (factory_id, alert_level, alert_type, message, triggered_at)
            VALUES (?,?,?,?,?)
        """, (factory_id, alert_level, alert_type, message, now))
        self.conn.commit()

    def get_unresolved_alerts(self) -> list[sqlite3.Row]:
        return self.conn.execute("""
            SELECT a.*, f.shop_name
            FROM alerts a
            JOIN factories f ON f.id = a.factory_id
            WHERE a.resolved = 0
            ORDER BY a.triggered_at DESC
        """).fetchall()

    # ── 查询 ──

    def get_latest_factory_snapshot(self, factory_id: int) -> sqlite3.Row | None:
        return self.conn.execute("""
            SELECT * FROM factory_snapshots
            WHERE factory_id = ?
            ORDER BY snapshot_time DESC LIMIT 1
        """, (factory_id,)).fetchone()

    def get_factory_snapshots(self, factory_id: int) -> list[sqlite3.Row]:
        return self.conn.execute("""
            SELECT * FROM factory_snapshots
            WHERE factory_id = ?
            ORDER BY snapshot_time
        """, (factory_id,)).fetchall()

    def get_latest_product_snapshots(self, factory_id: int) -> list[sqlite3.Row]:
        """获取某工厂最新一次商品快照的 Top10"""
        last_ts = self.conn.execute("""
            SELECT MAX(snapshot_time) as ts FROM product_snapshots
            WHERE factory_id = ?
        """, (factory_id,)).fetchone()["ts"]
        if not last_ts:
            return []
        return self.conn.execute("""
            SELECT * FROM product_snapshots
            WHERE factory_id = ? AND snapshot_time = ?
            ORDER BY sales_30d DESC
        """, (factory_id, last_ts)).fetchall()

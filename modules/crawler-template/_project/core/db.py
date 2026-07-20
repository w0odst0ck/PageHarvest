"""
Crawler Template — SQLite 存储层

职责：
  - 建表 schema 管理
  - 条目 CRUD（upsert / 批量写入）
  - 快照管理（时序数据）
  - 预警记录

使用前：
  1. 修改 SCHEMA_SQL 中的表定义以匹配你的业务数据
  2. 根据需要添加或修改 CRUD 方法
  3. DB_PATH 可在 __init__() 中覆盖

用法：
    db = ProjectDB("data/mydb.db")
    db.ensure_schema()
    db.upsert_item(name="xxx", url="yyy")
    items = db.get_active_items()
"""

import sqlite3
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# 【修改点】按你的业务修改此 Schema
#  - 条目表：待采集的条目列表（搜索页/列表页提取的结果）
#  - 快照表：每次采集的快照数据（时序型）
#  - 预警表：变化检测产生的告警
# ═══════════════════════════════════════════════════════

SCHEMA_SQL = """
-- 条目主表：搜索页/列表页提取的条目
CREATE TABLE IF NOT EXISTS items (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    url             TEXT    NOT NULL UNIQUE,  -- 用唯一字段做 UNIQUE 防止重复插入
    detail_url      TEXT    DEFAULT '',
    status          TEXT    NOT NULL DEFAULT 'active',
    first_seen      TEXT    NOT NULL
);

-- 快照表：每次采集的时序快照
CREATE TABLE IF NOT EXISTS snapshots (
    id               INTEGER PRIMARY KEY,
    item_id          INTEGER NOT NULL REFERENCES items(id),
    field_a          REAL,       -- 数值型字段（如价格）
    field_b          INTEGER,    -- 整数型字段（如销量）
    field_c          TEXT,       -- 文本型字段（如标签）
    description      TEXT,       -- 状态描述
    snapshot_time    TEXT    NOT NULL
);

-- 预警表
CREATE TABLE IF NOT EXISTS alerts (
    id            INTEGER PRIMARY KEY,
    item_id       INTEGER NOT NULL REFERENCES items(id),
    alert_level   TEXT    NOT NULL,      -- red / yellow / blue
    alert_type    TEXT    NOT NULL,      -- drop / surge / new
    message       TEXT,
    triggered_at  TEXT    NOT NULL,
    resolved      INTEGER DEFAULT 0
);

-- 索引（查询性能）
CREATE INDEX IF NOT EXISTS idx_snapshots_item   ON snapshots(item_id);
CREATE INDEX IF NOT EXISTS idx_snapshots_time   ON snapshots(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_alerts_item      ON alerts(item_id);
CREATE INDEX IF NOT EXISTS idx_alerts_resolved  ON alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_items_status     ON items(status);
"""


class ProjectDB:
    """SQLite 存储层

    使用 WAL 模式支持读写并发，row_factory 按列名取值。
    """

    def __init__(self, db_path: str | Path = "data/monitor.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    # ── 连接管理 ────────

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

    # ── Schema ────────

    def ensure_schema(self):
        """建表 + 索引（幂等）"""
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── 条目 CRUD ────────
    # 【修改点】按业务字段调整

    def upsert_item(self, name: str, url: str,
                    detail_url: str = "") -> int:
        """插入或更新条目，返回 id

        ON CONFLICT 需要匹配 UNIQUE 列。
        COALESCE(NULLIF(?,''), ...) 模式：只在新值非空时覆盖旧值。
        """
        now = self._now()
        self.conn.execute("""
            INSERT INTO items (name, url, detail_url, status, first_seen)
            VALUES (?, ?, ?, 'active', ?)
            ON CONFLICT(url) DO UPDATE SET
                name        = COALESCE(NULLIF(?,''), name),
                detail_url  = COALESCE(NULLIF(?,''), detail_url),
                status      = 'active'
        """, (name, url, detail_url, now,
              name, detail_url))
        self.conn.commit()
        row = self.conn.execute(
            "SELECT id FROM items WHERE url = ?", (url,)
        ).fetchone()
        return row["id"] if row else -1

    def get_active_items(self) -> list[sqlite3.Row]:
        """获取所有 active 条目"""
        return self.conn.execute(
            "SELECT * FROM items WHERE status = 'active' ORDER BY id"
        ).fetchall()

    def get_items_without_detail(self) -> list[sqlite3.Row]:
        """获取尚需采集详情的条目（url 有值但 detail_url 为空）"""
        return self.conn.execute("""
            SELECT * FROM items
            WHERE url IS NOT NULL AND url != ''
              AND (detail_url IS NULL OR detail_url = '')
            ORDER BY id
        """).fetchall()

    def get_items_with_detail(self) -> list[sqlite3.Row]:
        """获取已有详情 URL 的 active 条目"""
        return self.conn.execute("""
            SELECT * FROM items
            WHERE status = 'active'
              AND detail_url IS NOT NULL AND detail_url != ''
            ORDER BY id
        """).fetchall()

    def get_all_items(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM items ORDER BY id"
        ).fetchall()

    def update_item_status(self, item_id: int, status: str):
        self.conn.execute(
            "UPDATE items SET status = ? WHERE id = ?",
            (status, item_id)
        )
        self.conn.commit()

    # ── 快照 ────────
    # 【修改点】按业务字段调整

    def add_snapshot(self, item_id: int, **fields) -> int:
        """写入一条快照记录

        fields 中的键值对会动态映射到 snapshots 表列。
        默认填充 field_a / field_b / field_c / description。

        传入示例：
            db.add_snapshot(item_id=1, field_a=99.5, field_b=100, description="ok")
        """
        now = self._now()
        cur = self.conn.execute("""
            INSERT INTO snapshots
                (item_id, field_a, field_b, field_c, description, snapshot_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            item_id,
            fields.get("field_a"),
            fields.get("field_b"),
            fields.get("field_c"),
            fields.get("description", ""),
            now,
        ))
        self.conn.commit()
        return cur.lastrowid

    def add_snapshots_batch(self, item_id: int,
                            records: list[dict]) -> int:
        """批量写入快照。records: [{field_a, field_b, field_c, description}, ...]"""
        now = self._now()
        rows = [
            (item_id, r.get("field_a"), r.get("field_b"),
             r.get("field_c"), r.get("description", ""), now)
            for r in records
        ]
        self.conn.executemany("""
            INSERT INTO snapshots (item_id, field_a, field_b, field_c, description, snapshot_time)
            VALUES (?,?,?,?,?,?)
        """, rows)
        self.conn.commit()
        return len(rows)

    def get_latest_snapshot(self, item_id: int) -> sqlite3.Row | None:
        return self.conn.execute("""
            SELECT * FROM snapshots
            WHERE item_id = ?
            ORDER BY snapshot_time DESC LIMIT 1
        """, (item_id,)).fetchone()

    def get_snapshots(self, item_id: int) -> list[sqlite3.Row]:
        return self.conn.execute("""
            SELECT * FROM snapshots
            WHERE item_id = ?
            ORDER BY snapshot_time
        """, (item_id,)).fetchall()

    # ── 预警 ────────

    def add_alert(self, item_id: int, alert_level: str,
                  alert_type: str, message: str = ""):
        now = self._now()
        self.conn.execute("""
            INSERT INTO alerts
                (item_id, alert_level, alert_type, message, triggered_at)
            VALUES (?,?,?,?,?)
        """, (item_id, alert_level, alert_type, message, now))
        self.conn.commit()

    def get_unresolved_alerts(self) -> list[sqlite3.Row]:
        return self.conn.execute("""
            SELECT a.*, i.name as item_name
            FROM alerts a
            JOIN items i ON i.id = a.item_id
            WHERE a.resolved = 0
            ORDER BY a.triggered_at DESC
        """).fetchall()

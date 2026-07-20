"""
【模板】预警引擎 — 对比快照差异 → 触发告警

功能：
  - 读取最新两次快照
  - 按规则检测变化（数据骤降 / 增长信号）
  - 写入 alerts 表

使用前：
  1. 修改阈值常量
  2. 修改检测规则逻辑
  3. 修改 add_alert 参数匹配你的业务

用法：
    python -m engine.alerter
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import ProjectDB

logger = logging.getLogger(__name__)

DB_PATH = "data/monitor.db"

# ═══════════════════════════════════════════════════════
# 【修改点】预警阈值
# ═══════════════════════════════════════════════════════

THRESHOLD_DROP = 0.30    # 数据减少 ≥30% → 红色预警
THRESHOLD_SURGE = 0.50   # 数据增长 ≥50% → 蓝色预警


def run_alerts(db: ProjectDB) -> int:
    """遍历所有 active 条目，检测预警规则，返回新增预警数"""
    items = db.get_active_items()
    alerted = 0

    for item in items:
        item_id = item["id"]

        # 获取最近两次快照
        rows = db.conn.execute("""
            SELECT * FROM snapshots
            WHERE item_id = ?
            ORDER BY snapshot_time DESC LIMIT 2
        """, (item_id,)).fetchall()

        if len(rows) < 2:
            continue  # 快照不足，跳过

        current, previous = rows[0], rows[1]

        # ── 【修改点】你的预警规则 ──
        # 示例：前次 field_b（整数型如产品数）与本次对比
        # 移除 pydantic 式的 . 属性访问（sqlite3.Row 用 []
        prev_val = previous["field_b"]
        curr_val = current["field_b"]

        if prev_val and curr_val and prev_val > 0:
            # 数据骤降
            drop = (prev_val - curr_val) / prev_val
            if drop >= THRESHOLD_DROP:
                msg = f"field_b 从 {prev_val} 降至 {curr_val}（-{drop*100:.0f}%）"
                db.add_alert(item_id, "red", "data_drop", msg)
                alerted += 1

            # 增长信号
            surge = (curr_val - prev_val) / prev_val
            if surge >= THRESHOLD_SURGE:
                msg = f"field_b 从 {prev_val} 涨至 {curr_val}（+{surge*100:.0f}%）"
                db.add_alert(item_id, "blue", "data_surge", msg)
                alerted += 1

    return alerted


def main():
    db = ProjectDB(DB_PATH)
    db.ensure_schema()
    n = run_alerts(db)
    unresolved = db.get_unresolved_alerts()
    print(f"\n🔔 新增预警: {n} 条")
    print(f"  未处理: {len(unresolved)} 条")
    if unresolved:
        for a in unresolved[:10]:
            print(f"  [{a['alert_level']}] {a['item_name']}: {a['message']}")
    db.close()


if __name__ == "__main__":
    main()

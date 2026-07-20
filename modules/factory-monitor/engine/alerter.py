"""
预警引擎 — 对比最新两次快照，写入 alerts 表。

规则（四类）：
  🔴 数据异常   — 商品数减少 ≥30%
  🟡 评分波动   — 响应率/回头率/履约率降幅 ≥5%（暂缺，待搜索页集成）
  🔵 黑马发现   — 新入库工厂综合评分进入前 20%（需累计数据）
  🔵 增长信号   — Top10 总销量增幅 ≥50%
"""

import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import MonitorDB

logger = logging.getLogger(__name__)

DB_PATH = "data/monitor.db"

# 可配置阈值
THRESHOLD_PRODUCT_DROP = 0.30       # 商品数减少 ≥30%
THRESHOLD_SALES_SURGE = 0.50        # Top10 总销量增幅 ≥50%
THRESHOLD_BLACK_HORSE_PCT = 0.20   # 前 20%


def run_alerts(db: MonitorDB) -> int:
    """遍历所有工厂，检测预警规则，返回新增预警数"""
    factories = db.get_active_factories()
    alerted = 0

    for f in factories:
        fid = f["id"]

        # 获取最近两次快照
        rows = db.conn.execute("""
            SELECT * FROM factory_snapshots
            WHERE factory_id = ?
            ORDER BY snapshot_time DESC LIMIT 2
        """, (fid,)).fetchall()

        if len(rows) < 2:
            continue  # 快照不足，跳过

        current, previous = rows[0], rows[1]

        # ── 🔴 数据异常：商品数骤降 ──
        if (previous["total_products"]
                and current["total_products"]
                and previous["total_products"] > 0):
            drop = (previous["total_products"] - current["total_products"]) / previous["total_products"]
            if drop >= THRESHOLD_PRODUCT_DROP:
                msg = f"商品数从 {previous['total_products']} 降至 {current['total_products']}（{-drop*100:.0f}%）"
                db.add_alert(fid, "red", "product_drop", msg)
                alerted += 1

        # ── 🔵 增长信号：Top10 总销量增幅 ──
        if (previous["top10_avg_sales"]
                and current["top10_avg_sales"]
                and previous["top10_avg_sales"] > 0):
            surge = (current["top10_avg_sales"] - previous["top10_avg_sales"]) / previous["top10_avg_sales"]
            if surge >= THRESHOLD_SALES_SURGE:
                msg = f"Top10 均销从 {previous['top10_avg_sales']:.0f} 涨至 {current['top10_avg_sales']:.0f}（+{surge*100:.0f}%）"
                db.add_alert(fid, "blue", "sales_surge", msg)
                alerted += 1

    return alerted


def main():
    db = MonitorDB(DB_PATH)
    db.ensure_schema()
    n = run_alerts(db)
    unresolved = db.get_unresolved_alerts()
    print(f"\n🔔 新增预警: {n} 条")
    print(f"  未处理: {len(unresolved)} 条")
    if unresolved:
        for a in unresolved:
            print(f"  [{a['alert_level']}] {a['shop_name']}: {a['message']}")
    db.close()


if __name__ == "__main__":
    main()

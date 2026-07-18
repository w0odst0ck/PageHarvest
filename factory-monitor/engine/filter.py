"""
商品级过滤 — 按 Top10 商品标题判断工厂是否属于目标品类。

规则：最新快照 Top10 中 ≥2 个商品标题含任意灯具关键词 → active，否则 paused。

用法：
  python -m engine.filter
"""

import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import MonitorDB

logger = logging.getLogger(__name__)

DB_PATH = "data/monitor.db"

# 灯具类关键词（商品标题匹配用）
LIGHTING_KEYWORDS = [
    "灯", "照明", "灯具", "LED", "光源",
    "光", "护眼", "夜灯", "台灯", "灯泡",
    "吸顶", "射灯", "筒灯", "灯带", "灯管",
    "烛灯", "吊灯", "壁灯", "路灯", "头灯",
    "手电", "应急灯", "感应灯", "氛围灯",
]


def _is_lighting_product(title: str) -> bool:
    """判断商品标题是否与灯具相关"""
    if not title:
        return False
    return any(kw in title for kw in LIGHTING_KEYWORDS)


def run_filter(db: MonitorDB, threshold: int = 2) -> dict:
    """
    按 Top10 商品标题过滤工厂。

    Args:
        db: MonitorDB 实例
        threshold: 含灯类关键词的商品数达到此值才保留 (default=2)

    Returns:
        {"active": int, "paused": int, "details": [(shop_name, hits, total, verdict)]}
    """
    details = []
    active_count = 0
    paused_count = 0

    factories = db.get_active_factories()
    for f in factories:
        fid = f["id"]
        products = db.get_latest_product_snapshots(fid)
        if not products:
            continue

        total = len(products)
        hits = sum(1 for p in products if _is_lighting_product(p["title"] or ""))
        verdict = "active" if hits >= threshold else "paused"

        if verdict == "paused":
            db.update_factory_status(fid, "paused")
            paused_count += 1
        else:
            active_count += 1

        details.append((f["shop_name"], hits, total, verdict))
        logger.debug("%s: %d/%d → %s", f["shop_name"], hits, total, verdict)

    return {"active": active_count, "paused": paused_count, "details": details}


def main():
    db = MonitorDB(DB_PATH)
    db.ensure_schema()
    result = run_filter(db)
    db.close()

    print(f"\n🔍 商品过滤结果")
    print(f"  active: {result['active']} 家")
    print(f"  paused: {result['paused']} 家")
    print()
    for name, hits, total, verdict in result["details"]:
        if verdict == "paused":
            print(f"  ⏸️  {name} ({hits}/{total})")
    if result["active"]:
        print()
        for name, hits, total, verdict in result["details"]:
            if verdict == "active":
                print(f"  ✅ {name} ({hits}/{total})")


if __name__ == "__main__":
    main()

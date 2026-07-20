"""
【模板】过滤引擎 — 按规则筛选入库数据

功能：
  - 从快照中读取数据
  - 按关键词/数值阈值过滤
  - 标记 active/paused

使用前：
  1. 修改过滤关键词 KEYWORDS
  2. 修改 `_matches_filter()` 规则
  3. 修改判活阈值 threshold

用法：
    python -m engine.filter
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import ProjectDB

logger = logging.getLogger(__name__)

DB_PATH = "data/monitor.db"

# ═══════════════════════════════════════════════════════
# 【修改点】过滤规则
# ═══════════════════════════════════════════════════════

# 用 field_c（标题文本）匹配的关键词
KEYWORDS = ["关键词1", "关键词2"]

# 至少匹配到几个关键词才判 active
THRESHOLD = 2


def _matches_filter(field_c: str) -> bool:
    """判断单条记录是否匹配过滤规则"""
    if not field_c:
        return False
    return any(kw in field_c for kw in KEYWORDS)


def run_filter(db: ProjectDB) -> dict:
    """
    按快照数据过滤条目。

    Args:
        db: ProjectDB 实例

    Returns:
        {"active": int, "paused": int, "details": [(name, hits, total, verdict)]}
    """
    details = []
    active_count = 0
    paused_count = 0

    items = db.get_active_items()
    for item in items:
        item_id = item["id"]
        snapshots = db.get_latest_snapshot(item_id)
        if not snapshots:
            continue

        # 【修改点】按你的快照字段调整
        field_c = snapshots["field_c"] or ""

        # 简单规则：field_c 对关键字匹配
        hits = sum(1 for kw in KEYWORDS if kw in field_c)
        total = 1
        verdict = "active" if hits >= THRESHOLD else "paused"

        if verdict == "paused":
            db.update_item_status(item_id, "paused")
            paused_count += 1
        else:
            active_count += 1

        details.append((item["name"], hits, total, verdict))

    return {"active": active_count, "paused": paused_count, "details": details}


def main():
    db = ProjectDB(DB_PATH)
    db.ensure_schema()
    result = run_filter(db)
    db.close()
    print(f"\n🔍 过滤结果: {result['active']} active, {result['paused']} paused")
    for name, hits, total, verdict in result["details"]:
        icon = "✅" if verdict == "active" else "⏸️"
        print(f"  {icon}  {name} ({hits}/{total})")


if __name__ == "__main__":
    main()

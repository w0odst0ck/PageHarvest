"""
数据清理 CLI — 清理旧快照和运行日志

用法：
    python -m cli.cleanup                           # 预览
    python -m cli.cleanup --keep 5                   # 保留最近5次
    python -m cli.cleanup --keep 3 --dry-run          # 只看不删
    python -m cli.cleanup --keep 10 --export          # 先导出再删
    python -m cli.cleanup --keep 5 --category-keyword 小夜灯
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DB_PATH
from core.db import MonitorDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _resolve_category(db, category_id, category_keyword):
    if category_keyword:
        c = db.get_category_by_keyword(category_keyword)
        if not c:
            print(f"  未找到品类: {category_keyword}")
            return None
        return c["id"]
    return category_id


def cmd_cleanup(args):
    db = MonitorDB(DB_PATH)
    db.ensure_schema()

    cid = _resolve_category(db, args.category, args.category_keyword)
    keep = args.keep

    print(f"\n  保留策略：每家工厂最近 {keep} 次快照，run_log 保留 30 条")
    if cid:
        cat = db.get_category(cid)
        label = f"品类: {cat['keyword']}" if cat else f"品类 id={cid}"
        print(f"  范围: {label}")
    else:
        print(f"  范围: 全部品类")

    # ── 预览 ──
    to_delete = db.count_old_snapshots(keep=keep)
    total = sum(to_delete.values())
    print(f"\n  📊 待清理数据:")
    for table, count in to_delete.items():
        print(f"    {table:<20} {count:>6} 条")
    print(f"    {'─'*27}")
    print(f"    {'合计':<20} {total:>6} 条")

    if total == 0:
        print("\n  ✅ 无需清理")
        db.close()
        return

    if args.dry_run:
        print("\n  👁️  --dry-run 模式，未执行删除")
        db.close()
        return

    # ── 导出 ──
    if args.export:
        export_dir = Path(f"data/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        export_dir.mkdir(parents=True, exist_ok=True)
        for table in ["factory_snapshots", "product_snapshots", "run_log"]:
            rows = db.conn.execute(f"SELECT * FROM {table}").fetchall()
            data = [dict(r) for r in rows]
            path = export_dir / f"{table}.json"
            with open(path, "w") as f:
                json.dump(data, f, ensure_ascii=False, default=str, indent=2)
            print(f"  📦 已导出: {path} ({len(data)} 条)")
        print()

    # ── 执行清理 ──
    print(f"  清理中...")
    deleted = db.cleanup_old_snapshots(keep=keep)
    print(f"  ✅ 清理完成")
    for table, count in deleted.items():
        print(f"    删除了 {count} 条 {table}")

    db.close()


def main():
    parser = argparse.ArgumentParser(description="数据清理")
    parser.add_argument("--keep", type=int, default=5,
                        help="保留最近 N 次快照（默认 5）")
    parser.add_argument("--dry-run", action="store_true",
                        help="预览，不执行删除")
    parser.add_argument("--export", action="store_true",
                        help="删除前先导出 JSON 备份")
    parser.add_argument("--category", type=int, default=None)
    parser.add_argument("--category-keyword", default=None)
    args = parser.parse_args()

    cmd_cleanup(args)


if __name__ == "__main__":
    main()

"""
【模板】查询 CLI

功能：
  - list       — 列出所有条目
  - item <id>  — 看单项详情 + 快照历史

用法：
    python -m cli.query list
    python -m cli.query item 1
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import ProjectDB

DB_PATH = "data/monitor.db"


def cmd_list():
    db = ProjectDB(DB_PATH)
    db.ensure_schema()
    items = db.get_all_items()
    if not items:
        print("  (空)")
        db.close()
        return
    print(f"{'ID':>3} {'状态':>8}  名称")
    print(f"{'-'*3} {'-'*8}  {'-'*40}")
    for item in items:
        print(f"{item['id']:>3} {item['status']:>8}  {item['name'][:40]}")
    db.close()


def cmd_item(item_id: int):
    db = ProjectDB(DB_PATH)
    db.ensure_schema()
    items = db.get_all_items()
    item = next((x for x in items if x["id"] == item_id), None)
    if not item:
        print(f"  未找到 ID={item_id}")
        db.close()
        return

    print(f"\n  条目 #{item['id']}")
    for k in item.keys():
        print(f"    {k}: {item[k]}")

    snapshots = db.get_snapshots(item_id)
    if snapshots:
        print(f"\n  快照历史 ({len(snapshots)} 次):")
        for s in snapshots:
            print(f"    {s['snapshot_time'][:19]}  "
                  f"field_a={s['field_a']}  "
                  f"field_b={s['field_b']}  "
                  f"{s['description']}")
    db.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("用法: python -m cli.query list | item <id>")
        sys.exit(1)

    if args[0] == "list":
        cmd_list()
    elif args[0] == "item" and len(args) >= 2:
        cmd_item(int(args[1]))
    else:
        print("未知命令")
        sys.exit(1)

"""
查询 CLI — 查看 verify.db 内容

用法：
  python -m cli.query list         — 列出所有工厂
  python -m cli.query factory <id> — 看单厂详情
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import MonitorDB

DB_PATH = "data/monitor.db"


def cmd_list():
    db = MonitorDB(DB_PATH)
    db.ensure_schema()
    factories = db.get_all_factories()
    if not factories:
        print("  (空)")
        return
    print(f"{'ID':>3} {'状态':>8}  店铺名")
    print(f"{'-'*3} {'-'*8}  {'-'*30}")
    for f in factories:
        print(f"{f['id']:>3} {f['status']:>8}  {f['shop_name']}")
    db.close()


def cmd_factory(factory_id: int):
    db = MonitorDB(DB_PATH)
    db.ensure_schema()
    factories = db.get_all_factories()
    f = next((x for x in factories if x["id"] == factory_id), None)
    if not f:
        print(f"  未找到工厂 ID={factory_id}")
        db.close()
        return

    print(f"\n  工厂信息 #{f['id']}")
    for k in f.keys():
        print(f"    {k}: {f[k]}")

    latest = db.get_latest_factory_snapshot(factory_id)
    if latest:
        print(f"\n  最新快照:")
        for k in latest.keys():
            if k != "id":
                print(f"    {k}: {latest[k]}")

    products = db.get_latest_product_snapshots(factory_id)
    if products:
        print(f"\n  最新 Top10 商品:")
        print(f"  {'销量':>5}  {'价格':>8}  标题")
        for p in products:
            print(f"  {p['sales_30d'] or 0:>5}  ¥{p['price'] or 0:>6.2f}  {p['title'][:40]}")
    db.close()


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("用法: python -m cli.query list | factory <id>")
        sys.exit(1)

    if args[0] == "list":
        cmd_list()
    elif args[0] == "factory" and len(args) >= 2:
        cmd_factory(int(args[1]))
    else:
        print("未知命令")
        sys.exit(1)

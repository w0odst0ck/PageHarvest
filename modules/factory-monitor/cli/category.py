"""
品类管理 CLI — 增删改查品类配置

用法：
    python -m cli.category add --keyword 小夜灯 --tags "灯,LED,照明,光源"
    python -m cli.category add --keyword 吸顶灯 --tags "吸顶灯,面板灯,厨卫灯,平板灯"

    python -m cli.category list                  # 列出所有品类
    python -m cli.category get 小夜灯             # 查看品类详情

    python -m cli.category enable 吸顶灯          # 启用
    python -m cli.category disable 小夜灯          # 停用
    python -m cli.category delete 小夜灯           # 删除（同时删关联）
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import MonitorDB
from config import DB_PATH, DEFAULT_FILTER_TAGS

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def cmd_add(args):
    db = MonitorDB(DB_PATH)
    db.ensure_schema()
    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    cid = db.upsert_category(
        keyword=args.keyword,
        label=args.label or args.keyword,
        filter_tags=tags or DEFAULT_FILTER_TAGS,
        encoding=args.encoding or "gbk",
    )
    print(f"  ✅ 品类已创建: {args.keyword} (id={cid})")
    print(f"     过滤词: {tags}")
    print(f"     编码: {args.encoding or 'gbk'}")
    db.close()


def cmd_list(args):
    db = MonitorDB(DB_PATH)
    db.ensure_schema()
    cats = db.get_all_categories()
    if not cats:
        print("  (空)")
        db.close()
        return
    print(f"{'ID':>2} {'启用':>4}  关键词 {'标签':>20} {'工厂数':>6}  最近运行")
    print(f"{'--':>2} {'----':>4}  {'------':>20} {'------':>6}  {'--------'}")
    for c in cats:
        tags = json.loads(c["filter_tags"] or "[]")
        tag_str = ",".join(tags[:3])
        if len(tags) > 3:
            tag_str += "..."
        # 统计该品类下的 active 工厂数
        factories = db.get_active_factories(category_id=c["id"])
        enabled = "✅" if c["enabled"] else "⏸️"
        last_run = (c["last_run"] or "-")[:16]
        print(f"  {c['id']:>2}  {enabled:>4}  {c['keyword']:<12} "
              f"{tag_str:<20} {len(factories):>6}  {last_run}")
    db.close()


def cmd_get(args):
    db = MonitorDB(DB_PATH)
    db.ensure_schema()
    c = db.get_category_by_keyword(args.keyword)
    if not c:
        print(f"  ❌ 未找到品类: {args.keyword}")
        db.close()
        return
    tags = json.loads(c["filter_tags"] or "[]")
    cfg = json.loads(c["alert_config"] or "{}")
    factories = db.get_active_factories(category_id=c["id"])
    print(f"\n  品类: {c['keyword']} (#{c['id']})")
    print(f"    标签: {c['label']}")
    print(f"    状态: {'✅ 启用' if c['enabled'] else '⏸️ 停用'}")
    print(f"    编码: {c['encoding']}")
    print(f"    过滤词: {tags}")
    print(f"    预警配置: {cfg}")
    print(f"    创建: {c['created_at'][:19]}")
    print(f"    最近运行: {c['last_run'] or '-'}")
    print(f"    关联工厂: {len(factories)} 家 active")
    if factories:
        for f in factories[:5]:
            print(f"      · {f['shop_name']}")
        if len(factories) > 5:
            print(f"      ... 还有 {len(factories)-5} 家")
    db.close()


def cmd_enable(args):
    db = MonitorDB(DB_PATH)
    db.ensure_schema()
    c = db.get_category_by_keyword(args.keyword)
    if not c:
        print(f"  ❌ 未找到品类: {args.keyword}")
    else:
        db.set_category_enabled(c["id"], args.action == "enable")
        print(f"  ✅ {'启用' if args.action == 'enable' else '停用'}品类: {args.keyword}")
    db.close()


def cmd_delete(args):
    db = MonitorDB(DB_PATH)
    db.ensure_schema()
    c = db.get_category_by_keyword(args.keyword)
    if not c:
        print(f"  ❌ 未找到品类: {args.keyword}")
        db.close()
        return
    factories = db.get_active_factories(category_id=c["id"])
    if factories:
        print(f"  ⚠️  该品类下有 {len(factories)} 家关联工厂")
        resp = input("  确认删除？(y/N): ").strip().lower()
        if resp != "y":
            print("  ❌ 取消")
            db.close()
            return
    db.delete_category(c["id"])
    print(f"  ✅ 已删除品类: {args.keyword} (关联已清理)")
    db.close()


def main():
    parser = argparse.ArgumentParser(description="品类管理")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="新增品类")
    p_add.add_argument("--keyword", required=True, help="搜索关键词")
    p_add.add_argument("--label", help="显示标签（默认同 keyword）")
    p_add.add_argument("--tags", help="过滤词，逗号分隔")
    p_add.add_argument("--encoding", default="gbk", help="URL 编码 (gbk/utf-8)")

    sub.add_parser("list", help="列出所有品类")

    p_get = sub.add_parser("get", help="查看品类详情")
    p_get.add_argument("keyword", help="品类关键词")

    for name in ("enable", "disable"):
        p = sub.add_parser(name, help=f"{'启用' if name=='enable' else '停用'}品类")
        p.add_argument("keyword", help="品类关键词")
        p.set_defaults(action=name)

    p_del = sub.add_parser("delete", help="删除品类")
    p_del.add_argument("keyword", help="品类关键词")

    args = parser.parse_args()

    if args.cmd == "add":
        cmd_add(args)
    elif args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "get":
        cmd_get(args)
    elif args.cmd in ("enable", "disable"):
        cmd_enable(args)
    elif args.cmd == "delete":
        cmd_delete(args)


if __name__ == "__main__":
    main()

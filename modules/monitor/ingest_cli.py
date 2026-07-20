#!/usr/bin/env python3
"""
价格监控 — CLI 入口

将已有选品结果导入 SQLite，为后续比较和时机判断积累数据。

用法：
    # 1688 灯具选品入库
    python -m monitor.ingest_cli --platform 1688 --dir output/1688/灯具

    # 所有平台一键入库
    python -m monitor.ingest_cli --all

    # 查看入库历史
    python -m monitor.ingest_cli --status

    # 查看最新快照
    python -m monitor.ingest_cli --snapshots
"""

import argparse
import logging
import sys
from pathlib import Path

from monitor.db import MonitorDB
from monitor.ingester import ingest_selection
from monitor.alerter import run_alert, write_alert_csv, write_alert_txt

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent          # 项目根
DEFAULT_DB = ROOT / "data" / "monitor.db"
OUTPUT_DIR = ROOT / "output"


# ── 预警输出目录（与选品结果同级） ──

def _alert_output_dir(platform: str, category: str) -> Path:
    """预警文件写入选品输出目录，与报告文件同位置"""
    dir_map = {"zkh": "ZKH", "jd": "JD", "1688": "1688"}
    return OUTPUT_DIR / dir_map.get(platform, platform) / category / "搜索页"


def _run_alerts_for_ingest(result: dict, platform: str, db_path: str,
                           threshold: float = 10.0,
                           window: int = 5,
                           min_samples: int = 3):
    """入库完成后自动跑预警比对（移动平均版）"""
    from monitor.alerter import run_alert

    run_ids = result["run_id"]
    categories = result["categories"]
    if not isinstance(run_ids, list):
        run_ids = [run_ids]

    db = MonitorDB(db_path)
    db.ensure_schema()

    all_alerts = []
    for rid, cat in zip(run_ids, categories):
        alerts = run_alert(
            platform, cat, rid, db,
            threshold_below_ma=threshold,
            ma_window=window,
            min_samples=min_samples,
        )
        if alerts:
            all_alerts.extend(alerts)
            # 写入选品输出目录
            out_dir = _alert_output_dir(platform, cat)
            write_alert_csv(alerts, out_dir / "📋-价格预警.csv")
            write_alert_txt(alerts, out_dir / "📋-价格预警.txt",
                            platform=platform, category=cat)

    db.close()
    return all_alerts


def _find_categories(platform: str) -> list[Path]:
    """扫描 output/{platform}/ 下所有品类目录"""
    base = OUTPUT_DIR / _platform_dir(platform)
    if not base.is_dir():
        return []
    cats = []
    for child in sorted(base.iterdir()):
        if child.is_dir() and (child / "搜索页").is_dir():
            selection_dir = child / "搜索页"
        elif child.is_dir():
            selection_dir = child
        else:
            continue
        # 确认含 CSV
        if any(f.name == "00-选品推荐合集.csv" for f in selection_dir.iterdir()):
            cats.append(selection_dir)
    return cats


def _platform_dir(platform: str) -> str:
    return {"zkh": "ZKH", "jd": "JD", "1688": "1688"}.get(platform, platform)


def _ingest_one_category(platform: str, cat_dir: Path, args) -> tuple:
    """入库单个品类，返回 (商品数, 预警列表)"""
    cat_name = cat_dir.parent.name if cat_dir.name == "搜索页" else cat_dir.name
    platform_name = {"ZKH": "zkh", "JD": "jd", "1688": "1688"}.get(platform, platform.lower())
    result = ingest_selection(
        platform=platform_name,
        selection_dir=cat_dir,
        db_path=args.db,
    )
    alert_args = dict(
        threshold=args.threshold, window=args.window,
        min_samples=args.min_samples,
    )
    alerts = _run_alerts_for_ingest(result, platform_name, args.db, **alert_args)
    return result["products"], alerts, cat_name, result


def cmd_ingest(args):
    platform = args.platform.lower()
    if platform == "all":
        return cmd_ingest_all(args)

    # 构建 output/ 路径
    pdir = _platform_dir(platform)
    base = OUTPUT_DIR / pdir

    # 优先用 --dir；未指定时扫描 output/{platform}/ 下所有品类
    cats = []
    if args.dir:
        sel_dir = Path(args.dir)
        if not sel_dir.is_dir():
            logger.error("目录不存在: %s", args.dir)
            sys.exit(1)
        cats = [sel_dir]
    elif base.is_dir():
        plat_cats = _find_categories(pdir)
        if plat_cats:
            cats = plat_cats
        else:
            logger.error("平台 %s 下无数据, 用 --dir 指定目录", platform)
            sys.exit(1)
    else:
        logger.error("目录不存在: %s", base)
        sys.exit(1)

    total_products = 0
    all_alerts = []
    for cat_dir in cats:
        products, alerts, cat_name, result = _ingest_one_category(pdir, cat_dir, args)
        total_products += products
        all_alerts.extend(alerts)
        alert_tag = f" 🔔{len(alerts)}" if alerts else ""
        print(f"  {pdir}/{cat_name}: {products} 商品 → run_id={result['run_id']}{alert_tag}")

    print(f"✅ 入库完成: {total_products} 商品")
    if all_alerts:
        print(f"🔔 价格预警: {len(all_alerts)} 条")
        for a in all_alerts[:5]:
            dev = f" {a.deviation_pct:.1f}%" if a.deviation_pct is not None else ""
            print(f"  {a.label}{dev}  {a.title[:50] or a.url[:50]}")
        if len(all_alerts) > 5:
            print(f"  ... 还有 {len(all_alerts) - 5} 条")
    else:
        print("  无价格预警")


def cmd_ingest_all(args):
    """扫描 output/ 下所有平台的选品结果入库"""
    platforms = ["1688", "ZKH", "JD"]
    total_p = 0
    all_alerts = []
    for p in platforms:
        cats = _find_categories(p)
        if not cats:
            logger.info("平台 %s 无可导入的选品数据", p)
            continue
        for cat_dir in cats:
            cat_name = cat_dir.parent.name if cat_dir.name == "搜索页" else cat_dir.name
            try:
                products, alerts, cn, result = _ingest_one_category(p, cat_dir, args)
                total_p += products
                all_alerts.extend(alerts)
                alert_tag = f" 🔔{len(alerts)}" if alerts else ""
                print(f"  {p}/{cat_name}: {products} 商品 → run_id={result['run_id']}{alert_tag}")
            except Exception as e:
                logger.error("导入失败 %s/%s: %s", p, cat_name, e)
    print(f"✅ 全部完成: {total_p} 商品")
    if all_alerts:
        print(f"🔔 共 {len(all_alerts)} 条价格预警")
        for a in all_alerts[:5]:
            dev = f" {a.deviation_pct:.1f}%" if a.deviation_pct is not None else ""
            print(f"  {a.label}{dev}  {a.title[:50] or a.url[:50]}")
        if len(all_alerts) > 5:
            print(f"  ... 还有 {len(all_alerts) - 5} 条")
    else:
        print("  无价格预警")


def cmd_status(args):
    db = MonitorDB(args.db)
    db.ensure_schema()
    runs = db.get_runs(limit=50)

    if not runs:
        print("暂无入库记录")
        return

    print(f"{'ID':<5} {'平台':<8} {'品类':<10} {'商品数':<8} {'入库时间'}")
    print("-" * 60)
    for r in runs:
        print(f"{r['id']:<5} {r['platform']:<8} {r['category'] or '-':<10} "
              f"{r['product_count'] or 0:<8} {r['ingested_at'][:19]}")

    # 按平台统计
    db.conn.row_factory = None
    for row in db.conn.execute("""
        SELECT platform, COUNT(DISTINCT product_id) as total
        FROM snapshots s
        JOIN ingestion_runs r ON r.id = s.run_id
        GROUP BY platform
    """).fetchall():
        print(f"  平台 {row[0]}: {row[1]} 商品")
    db.close()


def cmd_snapshots(args):
    db = MonitorDB(args.db)
    db.ensure_schema()
    latest = db.get_latest_snapshots()
    if not latest:
        print("暂无快照数据")
        return

    print(f"{'平台':<8} {'品牌':<12} {'标题':<40} {'价格':<10} {'策略':<8}")
    print("-" * 90)
    for s in latest:
        t = s["title"] or ""
        title = t[:38] + "…" if len(t) > 38 else t
        print(f"{s['platform']:<8} {(s['brand'] or '-'):<12} {title:<40} "
              f"{str(s['price'] or '-'):<10} {(s['strategy'] or '-'):<8}")
    print(f"\n共 {len(latest)} 条快照")
    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="PageHarvest 价格监控 — 选品结果入库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--db", default=str(DEFAULT_DB),
                        help=f"SQLite 路径 (默认: {DEFAULT_DB})")

    sub = parser.add_subparsers(dest="command", required=True)

    # ingest
    p_ingest = sub.add_parser("ingest", help="导入选品结果 + 自动价格预警")
    p_ingest.add_argument("--platform", "-p", required=True,
                          help="平台: zkh | jd | 1688 | all")
    p_ingest.add_argument("--dir", default="",
                          help="选品目录路径（默认 output/{platform}/）")
    p_ingest.add_argument("--category", default="",
                          help="品类名（自动检测时留空）")
    p_ingest.add_argument("--threshold", type=float, default=10.0,
                          help="价格低于均线告警阈值, 百分比 (默认 10.0)")
    p_ingest.add_argument("--window", type=int, default=5,
                          help="移动平均窗口, 最近N次快照 (默认 5)")
    p_ingest.add_argument("--min-samples", type=int, default=3,
                          help="冷启动最少快照数 (默认 3)")
    p_ingest.set_defaults(func=cmd_ingest)

    # status
    p_status = sub.add_parser("status", help="查看入库历史")
    p_status.set_defaults(func=cmd_status)

    # snapshots
    p_snap = sub.add_parser("snapshots", help="查看最新快照")
    p_snap.set_defaults(func=cmd_snapshots)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

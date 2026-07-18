"""
一键运行：搜索 → 采集 → 过滤 → 预警

用法：
  python -m cli.run                     # 默认关键词: 小夜灯
  python -m cli.run --keyword 灯具      # 指定关键词
  python -m cli.run --pages 3           # 搜索页数
  python -m cli.run --offers-only       # 仅采集产品目录（不重新搜索）
  python -m cli.run --alerts-only       # 仅运行预警
  python -m cli.run --filter-only       # 仅运行商品过滤
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.search import search_factories
from collector.offers import collect_offers
from engine.alerter import run_alerts
from engine.filter import run_filter
from core.db import MonitorDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = "data/monitor.db"


def main():
    parser = argparse.ArgumentParser(description="1688 工厂监控 — 一键运行")
    parser.add_argument("--keyword", default="小夜灯")
    parser.add_argument("--pages", type=int, default=5)
    parser.add_argument("--offers-only", action="store_true")
    parser.add_argument("--alerts-only", action="store_true")
    parser.add_argument("--filter-only", action="store_true")
    args = parser.parse_args()

    db = MonitorDB(DB_PATH)
    db.ensure_schema()

    if args.alerts_only:
        logger.info("仅运行预警引擎")
        n = run_alerts(db)
        print(f"  🔔 新增预警: {n}")
        db.close()
        return

    if args.filter_only:
        logger.info("仅运行商品过滤")
        result = run_filter(db)
        print(f"  ✅ {result['active']} 家 active, {result['paused']} 家 paused")
        db.close()
        return

    if not args.offers_only:
        logger.info("阶段一: 搜索工厂（关键词=%s, %d 页）", args.keyword, args.pages)
        n = search_factories(args.keyword, args.pages)
        print(f"  ✅ 搜索完成，{n} 家工厂\n")

    logger.info("阶段二: 产品目录采集")
    n = collect_offers()
    print(f"  ✅ 采集完成，{n} 家入库\n")

    logger.info("阶段三: 商品过滤")
    result = run_filter(db)
    print(f"  ✅ {result['active']} 家 active, {result['paused']} 家 paused\n")

    logger.info("阶段四: 预警检测")
    n = run_alerts(db)
    print(f"  🔔 新增预警: {n}")

    db.close()
    print("\n✅ 全部完成")


if __name__ == "__main__":
    main()

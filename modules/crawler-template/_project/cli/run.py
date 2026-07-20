"""
【模板】一键编排入口

功能：
  - 阶段一：列表页采集（list_page）
  - 阶段二：详情采集（detail_page）
  - 阶段三：数据过滤（filter）
  - 阶段四：预警检测（alerter）

用法：
    python -m cli.run                    # 全流程
    python -m cli.run --keyword 灯具     # 指定关键词
    python -m cli.run --pages 3          # 指定页数
    python -m cli.run --list-only        # 仅阶段一
    python -m cli.run --detail-only      # 仅阶段二
    python -m cli.run --filter-only      # 仅阶段三
    python -m cli.run --alert-only       # 仅阶段四
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.list_page import collect_list_page
from collector.detail_page import collect_details
from engine.alerter import run_alerts as run_alert_engine
from engine.filter import run_filter as run_filter_engine
from core.db import ProjectDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = "data/monitor.db"


def main():
    parser = argparse.ArgumentParser(description="爬虫 — 一键运行")
    parser.add_argument("--keyword", default="关键词")
    parser.add_argument("--pages", type=int, default=5)
    parser.add_argument("--list-only", action="store_true",
                        help="仅列表页采集")
    parser.add_argument("--detail-only", action="store_true",
                        help="仅详情采集")
    parser.add_argument("--filter-only", action="store_true",
                        help="仅数据过滤")
    parser.add_argument("--alert-only", action="store_true",
                        help="仅预警检测")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="无头模式")
    args = parser.parse_args()

    db = ProjectDB(DB_PATH)
    db.ensure_schema()

    if args.alert_only:
        logger.info("阶段四: 预警检测")
        n = run_alert_engine(db)
        print(f"  🔔 新增预警: {n}")
        db.close()
        return

    if args.filter_only:
        logger.info("阶段三: 数据过滤")
        result = run_filter_engine(db)
        print(f"  ✅ {result['active']} active, {result['paused']} paused")
        db.close()
        return

    if not args.detail_only:
        logger.info("阶段一: 列表页采集（关键词=%s, %d 页）",
                     args.keyword, args.pages)
        n = collect_list_page(args.keyword, args.pages)
        print(f"  ✅ {n} 条\n")

    if not args.list_only:
        logger.info("阶段二: 详情采集")
        n = collect_details()
        print(f"  ✅ {n} 条\n")

    logger.info("阶段三: 数据过滤")
    result = run_filter_engine(db)
    print(f"  ✅ {result['active']} active, {result['paused']} paused\n")

    logger.info("阶段四: 预警检测")
    n = run_alert_engine(db)
    print(f"  🔔 新增预警: {n}")

    db.close()
    print("\n✅ 全部完成")


if __name__ == "__main__":
    main()

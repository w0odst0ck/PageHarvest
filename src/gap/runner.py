#!/usr/bin/env python3
"""
gap/runner.py — 商品缺口分析 CLI 入口

从 PageHarvest 数据目录中读取选品清单，与外部平台在售商品库比对，
找出缺失商品，导出结构化 Excel 报告。

用法：
    python -m gap.runner                                         # 自动发现路径
    python -m gap.runner --listing /path/to/选品清单              # 指定选品目录
    python -m gap.runner --inventory /path/to/在售商品.xlsx       # 指定在售库
    python -m gap.runner --fuzzy --fuzzy-threshold 55             # 启用模糊匹配
    python -m gap.runner --output /path/to/output                 # 指定输出目录
"""

import argparse
import logging
import sys
import os

# 确保能导入 gap 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gap.config import GapConfig
from gap.analyzer import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="商品缺口分析 — 找出选品清单中有、在售清单中没有的商品",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m gap.runner                                         自动发现路径
  python -m gap.runner --inventory 河姆渡-all-20260704.xlsx     指定在售商品
  python -m gap.runner --fuzzy --fuzzy-threshold 55             启用模糊匹配
  python -m gap.runner --listing data/ZKH/震坤行/上架清单       指定选品目录
        """,
    )
    parser.add_argument(
        "--listing", "-l",
        default=None,
        help="选品清单根目录（默认: 自动在 data/ 下查找）",
    )
    parser.add_argument(
        "--inventory", "-i",
        default=None,
        help="在售商品文件路径（默认: 自动发现河姆渡-all-*.xlsx）",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="输出目录（默认: 与选品清单同目录）",
    )
    parser.add_argument(
        "--listing-pattern",
        default="00-选品推荐合集.csv",
        help="选品清单文件名模式（默认: 00-选品推荐合集.csv）",
    )
    parser.add_argument(
        "--key-hint",
        default=None,
        help="手动指定匹配键列名（如 SKU编号、标题、商品名称）",
    )
    parser.add_argument(
        "--fuzzy", "-f",
        action="store_true",
        help="启用模糊匹配（需 pip install rapidfuzz）",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=int,
        default=55,
        help="模糊匹配阈值 (0-100，跨平台推荐 50-60，默认 55)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="详细日志",
    )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # 日志设置
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # 确定 PageHarvest 数据目录
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(script_dir, "data")
    if not os.path.isdir(data_dir):
        data_dir = ""

    cfg = GapConfig.from_env(data_dir=data_dir)

    # 命令行覆盖
    if args.listing:
        cfg.listing_folder = args.listing
    if args.inventory:
        cfg.inventory_file = args.inventory
    if args.output:
        cfg.output_folder = args.output
    if args.key_hint:
        cfg.key_hint = args.key_hint

    # 解析最终路径
    listing_dir = cfg.resolve_listing_folder()
    inventory_path = cfg.resolve_inventory_file()
    output_dir = cfg.output_folder or listing_dir

    # 打印配置概览
    print("=" * 60)
    print("  商品缺口分析 — Product Gap Analyzer")
    print("=" * 60)
    print(f"  选品清单: {listing_dir or '(未指定)'}")
    print(f"  在售商品: {inventory_path or '(未指定)'}")
    print(f"  输出目录: {output_dir}")
    print(f"  模糊匹配: {'启用' if args.fuzzy else '跳过'} (阈值: {args.fuzzy_threshold})")
    print()

    if not listing_dir:
        print("❌ 未找到选品清单目录。请指定:\n")
        print("   python -m gap.runner --listing /path/to/选品清单\n")
        print("  或确保 data/ZKH/震坤行/上架清单/ 存在且有选品数据。")
        sys.exit(1)

    if not inventory_path or not os.path.exists(inventory_path):
        print(f"❌ 未找到在售商品文件。请指定:\n")
        print("   python -m gap.runner --inventory /path/to/在售商品.xlsx\n")
        sys.exit(1)

    # 执行全流程
    result = run_pipeline(
        listing_folder=listing_dir,
        inventory_file=inventory_path,
        output_folder=output_dir,
        listing_pattern=args.listing_pattern,
        key_hint=args.key_hint,
        fuzzy=args.fuzzy,
        fuzzy_threshold=args.fuzzy_threshold,
        verbose=args.verbose,
    )

    print()
    print(result["summary"])
    print()
    print("=" * 60)
    print(f"  状态: {'✓ 完成' if result['status'] == 'ok' else '❌ 异常'}")
    print("=" * 60)


if __name__ == "__main__":
    main()

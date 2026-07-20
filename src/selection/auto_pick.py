"""
selection/auto_pick.py — 选品分析 Phase 2 增强模块

在现有 zkh-picker.py 每品类分析完成后，自动追加汇总统计和
给缺口分析（gap/）的"接力信号"。

这不是独立脚本，而是 zkh-picker.py 可选的 post-process 插件。
"""

import os
import csv
import logging
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)


def summarize_selection(output_dir: str) -> dict:
    """扫描选品输出目录，统计各品类/策略的上架推荐情况。

    返回汇总信息，供后续 gap 分析使用。

    Args:
        output_dir: 上架清单根目录（含各品类子文件夹）

    Returns:
        { categories: [str], total_recommended: int,
          by_category: { name: { strategy: count } },
          listing_dir: str }
    """
    if not os.path.isdir(output_dir):
        raise FileNotFoundError(f"选品输出目录不存在: {output_dir}")

    subdirs = sorted([
        d for d in os.listdir(output_dir)
        if os.path.isdir(os.path.join(output_dir, d))
        and not d.startswith("_")
    ])

    if not subdirs:
        # 可能是扁平输出无子夹，直接扫描
        collection_files = [
            f for f in os.listdir(output_dir)
            if f == "00-选品推荐合集.csv"
        ]
        if collection_files:
            # 单品类模式
            categories_info = _scan_single(output_dir)
            return {
                "categories": [categories_info["name"]],
                "total_recommended": categories_info["total"],
                "by_category": {categories_info["name"]: categories_info["strategies"]},
                "listing_dir": output_dir,
            }
        return {
            "categories": [],
            "total_recommended": 0,
            "by_category": {},
            "listing_dir": output_dir,
        }

    by_category = {}
    total = 0
    for sub in subdirs:
        cat_dir = os.path.join(output_dir, sub)
        collection_file = os.path.join(cat_dir, "00-选品推荐合集.csv")
        if not os.path.exists(collection_file):
            continue
        strategies = _count_strategies(collection_file)
        cat_total = sum(strategies.values())
        by_category[sub] = strategies
        total += cat_total
        logger.debug("  %s: %d 条推荐 (%s)", sub, cat_total, strategies)

    return {
        "categories": list(by_category.keys()),
        "total_recommended": total,
        "by_category": by_category,
        "listing_dir": output_dir,
    }


def _scan_single(output_dir: str) -> dict:
    """扫描扁平输出（无子文件夹模式）"""
    collection_file = os.path.join(output_dir, "00-选品推荐合集.csv")
    strategies = _count_strategies(collection_file) if os.path.exists(collection_file) else {}
    return {
        "name": os.path.basename(output_dir.rstrip("/")),
        "total": sum(strategies.values()),
        "strategies": strategies,
    }


def _count_strategies(csv_path: str) -> dict:
    """统计 CSV 中各策略的条目数"""
    strategies = Counter()
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s = row.get("策略", "").strip()
                if s:
                    strategies[s] += 1
    except Exception as e:
        logger.warning("  无法读取 %s: %s", csv_path, e)
    return dict(strategies)


def print_summary(summary: dict):
    """终端打印汇总信息"""
    categories = summary["categories"]
    if not categories:
        print("  ⚠ 未找到选品清单")
        return
    print(f"  📋 汇总: {len(categories)} 品类, {summary['total_recommended']} 个推荐商品")
    for cat in categories:
        strategies = summary["by_category"].get(cat, {})
        items = ", ".join(f"{s}: {c}" for s, c in strategies.items())
        print(f"     {cat:<8} → {items}")

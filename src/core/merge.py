"""
跨平台数据合并与对比工具
"""

import csv, os
from typing import Optional
from core.schema import UnifiedProduct, AnalysisReport


def merge_csv_by_keyword(data_dir: str, keyword: str, platforms: list[str],
                         output: Optional[str] = None) -> str:
    """
    将多个平台的搜索页 CSV 合并为一个跨平台对比 CSV。

    Args:
        data_dir: 数据根目录
        keyword: 品类关键词
        platforms: 平台列表，如 ["1688", "京东"]
        output: 输出文件名，默认 cross_platform_comparison.csv

    Returns:
        输出文件路径
    """
    if output is None:
        output = os.path.join(data_dir, keyword, "cross_platform_comparison.csv")

    all_rows = []
    for platform in platforms:
        csv_file = os.path.join(data_dir, keyword, f"all_{platform}.csv")
        if not os.path.exists(csv_file):
            continue
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                row['platform'] = platform
                all_rows.append(row)

    if not all_rows:
        print(f"警告: 未找到任何平台的数据 ({', '.join(platforms)})")
        return ""

    # 统一输出字段
    fieldnames = [
        'platform', 'product_id', 'title', 'price_min', 'price_max',
        'shop_name', 'shop_type', 'brand', 'sales_text',
        'review_count', 'rating', 'is_self_operated', 'product_url'
    ]

    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"跨平台对比表已保存: {output}")
    return output

"""
数据存储抽象层
支持按平台+品类存储 CSV 和报告。
"""

import os, csv, json
from datetime import datetime
from pathlib import Path
from typing import Optional
from core.schema import UnifiedProduct, UnifiedDetail, AnalysisReport


def product_csv_path(data_dir: str, platform: str, keyword: str) -> str:
    """返回搜索页 CSV 路径（按平台目录）"""
    platform_dir = os.path.join(data_dir, platform)
    Path(platform_dir).mkdir(parents=True, exist_ok=True)
    return os.path.join(platform_dir, f"all_{keyword}.csv")


def detail_csv_path(data_dir: str, platform: str, keyword: str) -> str:
    """返回详情页 CSV 路径（按平台目录）"""
    platform_dir = os.path.join(data_dir, platform)
    Path(platform_dir).mkdir(parents=True, exist_ok=True)
    return os.path.join(platform_dir, f"top_{keyword}_details.csv")


def report_path(data_dir: str, platform: str, keyword: str) -> str:
    """返回分析报告路径（按平台目录）"""
    platform_dir = os.path.join(data_dir, platform)
    Path(platform_dir).mkdir(parents=True, exist_ok=True)
    return os.path.join(platform_dir, f"analysis_{keyword}.txt")


def save_products_csv(products: list[UnifiedProduct],
                      filepath: str,
                      append: bool = False):
    """将 UnifiedProduct 列表保存为 CSV"""
    fieldnames = [
        'platform', 'product_id', 'title', 'price_min', 'price_max',
        'currency', 'shop_name', 'shop_type', 'brand',
        'sales_text', 'review_count', 'rating',
        'is_ad', 'is_self_operated',
        'tags', 'image_url', 'product_url',
    ]

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    mode = 'a' if append else 'w'
    with open(filepath, mode, newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        if not append or os.path.getsize(filepath) == 0:
            writer.writeheader()
        for p in products:
            row = {k: getattr(p, k, '') for k in fieldnames}
            if isinstance(row['tags'], list):
                row['tags'] = '|'.join(row['tags'])
            writer.writerow(row)

    print(f"  已保存: {filepath}  ({len(products)} 条)")


def save_detail_csv(details: list[UnifiedDetail],
                    filepath: str):
    """将 UnifiedDetail 列表保存为 CSV"""
    fieldnames = [
        'platform', 'product_id', 'title', 'brand', 'spec',
        'product_code', 'price_min', 'price_max', 'min_order',
        'ship_from', 'sales_count', 'yearly_sales',
        'repurchase_rate', 'listing_date',
        'main_images', 'detail_images', 'videos',
        'sku_count', 'attributes', 'sku_matrix',
    ]

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for d in details:
            row = {k: getattr(d, k, '') for k in fieldnames}
            for lst_field in ['main_images', 'detail_images', 'videos']:
                if isinstance(row.get(lst_field), list):
                    row[lst_field] = '|'.join(row[lst_field])
            if isinstance(row.get('attributes'), dict):
                row['attributes'] = json.dumps(row['attributes'], ensure_ascii=False)
            if isinstance(row.get('sku_matrix'), list):
                row['sku_matrix'] = json.dumps(row['sku_matrix'], ensure_ascii=False)
            writer.writerow(row)

    print(f"  已保存: {filepath}  ({len(details)} 条)")


def save_report(report: AnalysisReport, filepath: str):
    """保存分析报告"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(report.report_text)
    print(f"  报告已保存: {filepath}")

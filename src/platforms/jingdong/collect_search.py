"""
京东搜索页批量解析工具
======================

批量解析浏览器渲染后的京东搜索页 HTML（如 search.jd.com/Search 保存的页面），
输出结构化 CSV。

用法:
    # 批量解析目录下所有 HTML
    python -m platforms.jingdong.collect_search data/JD/搜索页/ --batch

    # 单文件解析
    python -m platforms.jingdong.collect_search 灯具-京东-1.html

    # 指定关键词
    python -m platforms.jingdong.collect_search 灯具-京东-1.html --keyword 灯具
"""

import os
import re
import sys
import csv
import json
import logging
from typing import Optional

from .search_parser import parse_search_html, raw_to_unified

logger = logging.getLogger(__name__)


def parse_search_file(filepath: str, keyword: str = "") -> list[dict]:
    """解析单个京东搜索页 HTML 文件，返回结构化列表。

    Returns:
        list[dict] — 每项包含搜索页各字段
    """
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    # 自动从文件名推断关键词
    if not keyword:
        base = os.path.basename(filepath)
        # 文件名格式："灯具 - 商品搜索 - 京东-1.html"
        m = re.match(r'^(.+?)\s*[-–—]\s*商品搜索', base)
        if m:
            keyword = m.group(1).strip()
        else:
            # 从 saved from URL 推断
            m = re.search(r'keyword=([^&]+)', html[:500] if len(html) > 500 else html)
            if m:
                from urllib.parse import unquote
                keyword = unquote(m.group(1))

    raw = parse_search_html(html, keyword)
    products = raw_to_unified(raw, platform="京东", keyword=keyword)

    results = []
    for p in products:
        results.append({
            "platform": p.platform,
            "product_id": p.product_id,
            "product_url": p.product_url,
            "title": p.title,
            "price_min": p.price_min,
            "price_max": p.price_max,
            "brand": p.brand,
            "shop_name": p.shop_name,
            "shop_type": p.shop_type,
            "sales_text": p.sales_text,
            "review_count": p.review_count,
            "rating": p.rating,
            "is_self_operated": p.is_self_operated,
            "is_ad": p.is_ad,
            "tags": ", ".join(p.tags) if p.tags else "",
            "image_url": p.image_url,
        })

    return results


def _batch_process(dir_path: str, keyword: str = "", output: str = "") -> int:
    """批量处理目录下所有 .html 文件"""
    html_files = sorted([
        os.path.join(dir_path, f)
        for f in os.listdir(dir_path)
        if f.endswith(".html") and not f.endswith("-files")
    ])

    if not html_files:
        print(f"⚠  目录下无 .html 文件: {dir_path}")
        return 0

    print(f"📂 找到 {len(html_files)} 个 HTML 文件")

    all_results = []
    for fpath in html_files:
        fname = os.path.basename(fpath)
        try:
            products = parse_search_file(fpath, keyword=keyword)
            for p in products:
                p["source_file"] = fname
            all_results.extend(products)
            print(f"  ✅ {fname[:50]:50} {len(products)} 个商品")
        except Exception as e:
            print(f"  ❌ {fname[:50]:50} 解析失败: {e}")

    if not all_results:
        print("⚠  未解析到任何商品")
        return 0

    print(f"\n📊 共 {len(all_results)} 条商品数据")

    # 去重（按 product_id）
    seen = set()
    unique = []
    for p in all_results:
        pid = p["product_id"]
        if pid not in seen:
            seen.add(pid)
            unique.append(p)
    duplicates = len(all_results) - len(unique)
    if duplicates:
        print(f"⚠  去重: 移除 {duplicates} 条重复（不同页面中的相同商品）")
        all_results = unique

    # 输出
    output_path = output or os.path.join(dir_path, "jd_search_results.csv")
    fieldnames = [
        "platform", "product_id", "product_url", "title",
        "price_min", "price_max", "brand", "shop_name", "shop_type",
        "sales_text", "review_count", "rating",
        "is_self_operated", "is_ad", "tags", "image_url", "source_file",
    ]
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_results)

    print(f"📁 已保存: {output_path}")

    # 摘要
    self_op = sum(1 for p in all_results if p["is_self_operated"])
    shops = set(p["shop_name"] for p in all_results if p["shop_name"])
    print(f"\n📊 摘要:")
    print(f"  商品数:      {len(all_results)}")
    print(f"  自营:        {self_op}/{len(all_results)}")
    print(f"  店铺数:      {len(shops)}")
    if all_results:
        prices = [p["price_min"] for p in all_results if p["price_min"] > 0]
        if prices:
            print(f"  价格区间:    ¥{min(prices):.2f} ~ ¥{max(prices):.2f}")
            print(f"  均价:        ¥{sum(prices)/len(prices):.2f}")

    return len(all_results)


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="京东搜索页批量解析工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单文件
  python -m platforms.jingdong.collect_search 灯具-京东-1.html

  # 批量解析目录
  python -m platforms.jingdong.collect_search data/JD/ --batch

  # 指定关键词（自动推断失败时）
  python -m platforms.jingdong.collect_search data/JD/ --batch --keyword 灯具

  # 输出到指定路径
  python -m platforms.jingdong.collect_search data/JD/ --batch -o result.csv

  # 输出 JSON
  python -m platforms.jingdong.collect_search 灯具-京东-1.html --json
        """,
    )
    parser.add_argument("target", help="HTML 文件路径 或 目录（配合 --batch）")
    parser.add_argument("--keyword", "-k", default="", help="搜索关键词（自动推断失败时指定）")
    parser.add_argument("--batch", "-b", action="store_true", help="批量解析目录下所有 .html 文件")
    parser.add_argument("--output", "-o", default="", help="输出 CSV 路径")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    if not os.path.exists(args.target):
        print(f"❌ 路径不存在: {args.target}")
        sys.exit(1)

    if args.batch and os.path.isdir(args.target):
        total = _batch_process(args.target, keyword=args.keyword, output=args.output)
        sys.exit(0 if total > 0 else 1)

    # 单文件模式
    if not os.path.isfile(args.target):
        print(f"❌ 不是文件: {args.target}（需要 --batch 批量解析目录）")
        sys.exit(1)

    products = parse_search_file(args.target, keyword=args.keyword)
    if not products:
        print("❌ 未解析到商品")
        sys.exit(1)

    if args.json:
        print(json.dumps(products, ensure_ascii=False, indent=2))
    else:
        print(f"📊 共 {len(products)} 个商品:\n")
        for i, p in enumerate(products[:20]):
            tag_str = " [自营]" if p["is_self_operated"] else ""
            print(f"  {i+1:2d}. {p['title'][:50]}")
            print(f"      ¥{p['price_min']:.2f}  |  {p['shop_name']}{tag_str}")
            print(f"      {p['sales_text'] or '-'}  |  SKU: {p['product_id']}")
            print()
        if len(products) > 20:
            print(f"  ... 还有 {len(products) - 20} 个商品（共 {len(products)} 个）")

    # 单文件也支持输出
    if args.output:
        fieldnames = [
            "platform", "product_id", "product_url", "title",
            "price_min", "price_max", "brand", "shop_name", "shop_type",
            "sales_text", "review_count", "rating",
            "is_self_operated", "is_ad", "tags", "image_url",
        ]
        with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(products)
        print(f"📁 已保存: {args.output}")


if __name__ == "__main__":
    main()

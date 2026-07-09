#!/usr/bin/env python3
"""
京东选品分析器 (JD Product Picker)
===================================
从 collect_search 输出的 CSV 中分析商品格局，输出统一格式的选品清单。

结果模板（所有平台统一）：

  合集: 策略,排名,品牌,标题,价格,销量,好评率,自营,链接
  策略: 排名,品牌,标题,价格,销量,好评率,自营,链接

用法:
    python -m selection.jd-picker data/JD/京东-灯具-搜索结果.csv --name 灯具
    python -m selection.jd-picker data/JD/京东-灯具-搜索结果.csv --name 灯具 -o output/JD/
"""

import os
import re
import sys
import csv
import json
from collections import Counter, defaultdict

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from selection.selection_schema import STRATEGY_LIMITS, STRATEGY_ORDER, get_collection_fields, get_strategy_fields

# JD 扩展列
PLATFORM = "jd"
COLLECTION_FIELDS = get_collection_fields(PLATFORM)
STRATEGY_FIELDS   = get_strategy_fields(PLATFORM)


# ═══════════════════════════════════════════════════════════════
#  1. 数据载入
# ═══════════════════════════════════════════════════════════════

def load_csv(filepath: str) -> list[dict]:
    with open(filepath, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


# ═══════════════════════════════════════════════════════════════
#  2. 策略分类
# ═══════════════════════════════════════════════════════════════
#
#  维度：销量 + 好评率 + 自营
#  策略：必上/推荐/暗马/关注
# ═══════════════════════════════════════════════════════════════

def parse_sales(sales_text: str) -> int:
    if not sales_text:
        return 0
    m = re.search(r'([\d.]+)\s*万?', sales_text)
    if not m:
        return 0
    val = float(m.group(1))
    return int(val * 10000) if '万' in sales_text else int(val)


def parse_rating(sales_text: str) -> float:
    if not sales_text:
        return 0.0
    m = re.search(r'(\d+)%\s*好评', sales_text)
    return float(m.group(1)) if m else 0.0


def classify_product(row: dict, rank: int) -> tuple:
    """(priority, label) — 优先级越低越优先"""
    sales_count = parse_sales(row.get("sales_text", ""))
    rating = parse_rating(row.get("sales_text", ""))
    is_self = row.get("is_self_operated", "False") == "True"
    tags = row.get("tags", "")

    # 销量等级
    if sales_count >= 500000:
        sales_level = "超高"
    elif sales_count >= 100000:
        sales_level = "高"
    elif sales_count >= 10000:
        sales_level = "中"
    else:
        sales_level = "低"

    # 策略判定
    if sales_level == "超高" and is_self and rating >= 98:
        return (1, "🔥 必上")
    if sales_level == "高" and is_self and rating >= 99:
        return (1, "🔥 必上")
    if sales_level == "高" and is_self:
        return (2, "👍 推荐")
    if sales_level == "超高" and rating >= 97:
        return (2, "👍 推荐")
    if sales_level == "中" and rating >= 99 and is_self:
        return (3, "💡 暗马")
    if rank <= 60 and rating >= 99 and is_self:
        return (3, "💡 暗马")
    if rating >= 98 and is_self:
        return (5, "📌 关注")
    if "百亿补贴" in tags or "政府补贴" in tags:
        return (5, "📌 关注")
    return (99, "—")


# ═══════════════════════════════════════════════════════════════
#  3. 分析 & 输出
# ═══════════════════════════════════════════════════════════════

def analyze(name: str, csv_path: str, output_dir: str):
    rows = load_csv(csv_path)
    if not rows:
        print(f"  ⚠ {name}: CSV 无数据")
        return

    total = len(rows)
    self_op = sum(1 for r in rows if r.get("is_self_operated") == "True")
    print(f"\n  📁 {name}")
    print(f"     共 {total} 个商品, 自营 {self_op}/{total}")

    # ── 策略分类 ──
    classified = []
    for i, row in enumerate(rows):
        rank = i + 1
        priority, label = classify_product(row, rank)
        rating = parse_rating(row.get("sales_text", ""))
        row_cache = {
            "排名": rank,
            "_priority": priority,
            "_strategy": label,
            "_sales_count": parse_sales(row.get("sales_text", "")),
            # 模板公共字段
            "品牌": row.get("brand", ""),
            "标题": row.get("title", ""),
            "价格": float(row.get("price_min", 0)),
            "链接": row.get("product_url", ""),
            # JD 扩展字段
            "销量": row.get("sales_text", ""),
            "好评率": f'{rating:.0f}%' if rating else "",
            "自营": "是" if row.get("is_self_operated") == "True" else "",
        }
        classified.append(row_cache)

    # ── 输出策略文件 ──
    cat_dir = os.path.join(output_dir, name)
    os.makedirs(cat_dir, exist_ok=True)

    for tag in STRATEGY_ORDER:
        limit = STRATEGY_LIMITS[tag]
        items = [p for p in classified if p["_strategy"] == tag]
        items.sort(key=lambda p: p["_priority"])
        shown = items[:limit] if limit < 999 else items
        if not shown:
            continue

        fpath = os.path.join(cat_dir, f"{tag}.csv")
        with open(fpath, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=STRATEGY_FIELDS)
            w.writeheader()
            for p in shown:
                w.writerow({k: p[k] for k in STRATEGY_FIELDS})
        print(f"  ✅ {tag}: {len(shown)} 条")

    # ── 输出合集 ──
    merge = []
    for tag in STRATEGY_ORDER:
        limit = STRATEGY_LIMITS[tag]
        items = [p for p in classified if p["_strategy"] == tag]
        items.sort(key=lambda p: p["_priority"])
        shown = items[:limit] if limit < 999 else items
        for p in shown:
            row = {"策略": tag}
            row.update({k: p[k] for k in STRATEGY_FIELDS})
            merge.append(row)

    merge_path = os.path.join(cat_dir, "00-选品推荐合集.csv")
    with open(merge_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLLECTION_FIELDS)
        w.writeheader()
        w.writerows(merge)
    print(f"  ✅ 00-选品推荐合集.csv: {len(merge)} 条")

    # ── 报告 ──
    _write_report(name, rows, merge, output_dir)


def _write_report(name, rows, limited_items, output_dir):
    """生成可读分析报告，数据均基于实际输出的 limited_items"""
    total = len(rows)
    shops = Counter(p.get("shop_name", "未知") for p in rows)
    prices = [float(r.get("price_min", 0)) for r in rows if float(r.get("price_min", 0)) > 0]

    # 各策略实际输出数量
    strat_shown = Counter(p["策略"] for p in limited_items)

    sales_levels = Counter()
    for r in rows:
        sc = parse_sales(r.get("sales_text", ""))
        if sc >= 500000:
            sales_levels["超高(50万+)"] += 1
        elif sc >= 100000:
            sales_levels["高(10万+)"] += 1
        elif sc >= 10000:
            sales_levels["中(1万+)"] += 1
        else:
            sales_levels["低(<1万)"] += 1

    # 按策略分组（实际输出排序）
    by_strat = {tag: [] for tag in STRATEGY_ORDER}
    for p in limited_items:
        by_strat[p["策略"]].append(p)

    report_path = os.path.join(output_dir, f"选品分析_{name}.txt")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(f"京东选品分析报告 — {name}\n")
        f.write("=" * 50 + "\n\n")
        f.write("【概览】\n")
        f.write(f"  商品总数:   {total}\n")
        f.write(f"  推荐上架:   {len(limited_items)} 个\n")
        f.write(f"  自营比例:   {sum(1 for r in rows if r.get('is_self_operated') == 'True')}/{total}\n")
        f.write(f"  价格区间:   ¥{min(prices):.2f} ~ ¥{max(prices):.2f}\n" if prices else "")
        f.write(f"  均价:       ¥{sum(prices)/len(prices):.2f}\n" if prices else "")
        f.write(f"  店铺数:     {len(shops)}\n\n")

        f.write("【推荐上架分布】\n")
        for tag in STRATEGY_ORDER:
            f.write(f"  {tag}: {strat_shown.get(tag, 0)} 个\n")
        f.write("\n")

        f.write("【店铺格局】\n")
        for shop, count in shops.most_common(10):
            f.write(f"  {shop[:24]:24} {count:3} 个\n")
        f.write("\n")

        for tag in ["🔥 必上", "💡 暗马"]:
            items = by_strat.get(tag, [])
            if items:
                label = "🔥 必上清单" if tag == "🔥 必上" else "💡 暗马精选"
                f.write(f"【{label}】\n")
                for p in items:
                    f.write(f"  ¥{p['价格']:>7.2f}  {(p.get('品牌','') or '-'):12}  {p['标题'][:40]}\n")
                f.write("\n")

        f.write("=" * 50 + "\n")
        f.write(f"输出目录: {output_dir}/{name}/\n")


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="京东选品分析器 — 输出统一格式选品清单",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m selection.jd-picker data/JD/京东-灯具-搜索结果.csv --name 灯具
  python -m selection.jd-picker data/JD/京东-灯具-搜索结果.csv --name 灯具 -o output/JD/
        """,
    )
    parser.add_argument("csv_file", help="京东搜索结果 CSV")
    parser.add_argument("--name", "-n", required=True, help="品类名称")
    parser.add_argument("--output", "-o", default="output/JD", help="输出目录")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.csv_file):
        print(f"❌ 文件不存在: {args.csv_file}")
        sys.exit(1)

    analyze(args.name, args.csv_file, args.output)
    print(f"\n  推荐上架: {os.path.join(args.output, args.name)}/")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
1688 选品分析器 (1688 Product Picker)
======================================

1688 有两条数据获取路径：

  Path A [主力]: 1688采购助手插件 → XLSX 导出
      浏览器安装 1688采购助手 → 打开搜索页 → 插件自动提取商品数据 → 导出 XLSX
      数据字段：标题,商品ID,价格,年销售件数,复购率,店铺,综合服务等

  Path B [备用]: 搜索页 HTML → 解析

输出格式（统一模板，对应 selection_schema）：
  合集: 策略,排名,品牌,标题,价格,年销,复购率,店铺,链接
  策略: 排名,品牌,标题,价格,年销,复购率,店铺,链接

用法:
    # Path A: 插件 XLSX
    python -m selection.1688-picker data/1688/插件导出/ --name 灯具

    # Path B: HTML
    python -m selection.1688-picker data/1688/搜索页/ --from-html --name 灯具
"""

import os, re, sys, csv, glob
from collections import Counter

# 确保项目根在 sys.path 中（subprocess 调用时保证）
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from selection.selection_schema import STRATEGY_LIMITS, STRATEGY_ORDER

PLATFORM = "1688"
COLLECTION_FIELDS = ["策略", "排名", "品牌", "标题", "价格", "年销", "复购率", "店铺", "链接"]
STRATEGY_FIELDS   = ["排名", "品牌", "标题", "价格", "年销", "复购率", "店铺", "链接"]


# ══════════════════════════════════════
#  Path A: 采购助手 XLSX
# ══════════════════════════════════════

def parse_xlsx(filepath: str) -> list[dict]:
    """解析 1688采购助手 XLSX"""
    import openpyxl
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    header = [str(h or "").strip() for h in rows[0]]
    col_map = {name: idx for idx, name in enumerate(header)}
    required = {"标题", "商品ID", "价格", "年销售件数", "店铺名称", "商品链接"}
    missing = required - set(col_map.keys())
    if missing:
        raise ValueError(f"XLSX 缺字段: {missing}")
    products = []
    for row in rows[1:]:
        if not row or not row[col_map["商品ID"]]:
            continue
        pid = row[col_map["商品ID"]]
        products.append({
            "title": str(row[col_map["标题"]] or ""),
            "product_id": str(int(pid)) if isinstance(pid, float) else str(pid),
            "price": float(row[col_map["价格"]]) if row[col_map["价格"]] else 0.0,
            "yearly_sales": int(row[col_map["年销售件数"]]) if row[col_map["年销售件数"]] else 0,
            "shop_name": str(row[col_map["店铺名称"]] or ""),
            "product_url": str(row[col_map["商品链接"]] or ""),
            "repurchase_rate": str(row[col_map["复购率"]] or "") if "复购率" in col_map else "",
            "brand": _guess_brand(str(row[col_map["标题"]] or "")),
        })
    return products


def _guess_brand(title: str) -> str:
    for b in ["飞利浦","Philips","欧普","OPPLE","雷士","NVC","佛山照明","FSL",
              "松下","Panasonic","公牛","小米","米家","美的","正泰","德力西",
              "三雄极光","TCL","阳光","尚为","华荣"]:
        if b in title:
            return b
    return ""


# ══════════════════════════════════════
#  Path B: HTML 搜索页
# ══════════════════════════════════════

def parse_html_dir(html_dir: str) -> list[dict]:
    from platforms.alibaba.search_parser import parse_html
    files = sorted(glob.glob(os.path.join(html_dir, "*.html")))
    products = []
    for fpath in files:
        try:
            for p in parse_html(fpath):
                products.append({
                    "title": p.get("title", ""),
                    "product_id": "",
                    "price": float(p.get("price", 0) or 0),
                    "yearly_sales": 0,
                    "shop_name": p.get("shop_name", ""),
                    "product_url": p.get("shop_url", ""),
                    "repurchase_rate": "",
                    "brand": _guess_brand(p.get("title", "")),
                })
        except Exception as e:
            print(f"  ⚠ {os.path.basename(fpath)}: {e}")
    return products


# ══════════════════════════════════════
#  策略分类
# ══════════════════════════════════════

def classify(p: dict, rank: int) -> tuple:
    sales = p.get("yearly_sales", 0)
    rp = p.get("repurchase_rate", "")
    rp_val = float(re.search(r'([\d.]+)', rp).group(1)) if rp and re.search(r'([\d.]+)', rp) else 0
    if sales >= 50000 and rp_val >= 30:
        return (1, "🔥 必上")
    if sales >= 10000 and rp_val >= 20:
        return (1, "🔥 必上")
    if sales >= 50000:
        return (2, "👍 推荐")
    if sales >= 10000 and rp_val >= 10:
        return (2, "👍 推荐")
    if sales >= 3000 and rp_val >= 20:
        return (3, "💡 暗马")
    if rp_val >= 30:
        return (3, "💡 暗马")
    if sales >= 1000:
        return (5, "📌 关注")
    return (99, "—")


# ══════════════════════════════════════
#  分析 & 输出
# ══════════════════════════════════════

def analyze(name: str, products: list[dict], output_dir: str):
    total = len(products)
    print(f"\n  📁 {name}")
    print(f"     共 {total} 个商品")

    classified = []
    for i, p in enumerate(products):
        rank = i + 1
        priority, label = classify(p, rank)
        classified.append({
            "排名": rank, "_priority": priority, "_strategy": label,
            "品牌": p.get("brand", ""),
            "标题": p.get("title", ""),
            "价格": p.get("price", 0),
            "年销": str(p.get("yearly_sales", 0)),
            "复购率": p.get("repurchase_rate", ""),
            "店铺": p.get("shop_name", ""),
            "链接": p.get("product_url", ""),
            "_sales": p.get("yearly_sales", 0),
        })

    os.makedirs(os.path.join(output_dir, name), exist_ok=True)

    for tag in STRATEGY_ORDER:
        limit = STRATEGY_LIMITS[tag]
        items = sorted([p for p in classified if p["_strategy"] == tag],
                       key=lambda p: (-p["_sales"], p["_priority"]))[:limit]
        if not items:
            continue
        fpath = os.path.join(output_dir, name, f"{tag}.csv")
        with open(fpath, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=STRATEGY_FIELDS)
            w.writeheader()
            w.writerows({k: p[k] for k in STRATEGY_FIELDS} for p in items)
        print(f"  ✅ {tag}: {len(items)} 条")

    merge = []
    for tag in STRATEGY_ORDER:
        limit = STRATEGY_LIMITS[tag]
        items = sorted([p for p in classified if p["_strategy"] == tag],
                       key=lambda p: (-p["_sales"], p["_priority"]))[:limit]
        for p in items:
            row = {"策略": tag}
            row.update({k: p[k] for k in STRATEGY_FIELDS})
            merge.append(row)

    fpath = os.path.join(output_dir, name, "00-选品推荐合集.csv")
    with open(fpath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLLECTION_FIELDS)
        w.writeheader()
        w.writerows(merge)
    print(f"  ✅ 00-选品推荐合集.csv: {len(merge)} 条")

    _write_report(name, products, merge, output_dir)


def _write_report(name, rows, limited_items, output_dir):
    total = len(rows)
    strat_shown = Counter(p["策略"] for p in limited_items)
    shops = Counter(p.get("店铺", "未知") for p in limited_items)
    prices = [p.get("price", 0) for p in rows if p.get("price", 0) > 0]
    all_shops = Counter(p.get("shop_name", "未知") for p in rows if p.get("shop_name"))

    fp = os.path.join(output_dir, f"选品分析_{name}.txt")
    with open(fp, "w", encoding="utf-8") as f:
        f.write(f"1688选品分析报告 — {name}\n" + "=" * 50 + "\n\n")
        f.write(f"【概览】\n")
        f.write(f"  商品总数:   {total}\n")
        f.write(f"  推荐上架:   {len(limited_items)} 个\n")
        if prices:
            f.write(f"  价格区间:   ¥{min(prices):.2f} ~ ¥{max(prices):.2f}\n")
            f.write(f"  均价:       ¥{sum(prices)/len(prices):.2f}\n")
        f.write(f"  店铺数:     {len(all_shops)}\n\n")
        f.write("【推荐上架分布】\n")
        for tag in STRATEGY_ORDER:
            c = strat_shown.get(tag, 0)
            if c: f.write(f"  {tag}: {c} 个\n")
        f.write("\n")
        f.write("【店铺格局】\n")
        for shop, count in all_shops.most_common(10):
            f.write(f"  {shop[:24]:24} {count:3} 个\n")
        f.write("\n")
        by_strat = {t: [p for p in limited_items if p["策略"] == t] for t in STRATEGY_ORDER}
        for tag in ["🔥 必上", "💡 暗马"]:
            items = by_strat.get(tag, [])
            if items:
                f.write(f"【{'🔥 必上' if tag=='🔥 必上' else '💡 暗马'}清单】\n")
                for p in items:
                    f.write(f"  ¥{p['价格']:>7.2f}  {p['店铺']:24}  {p['标题'][:40]}\n")
                f.write("\n")
        f.write("=" * 50 + "\n")
        f.write(f"输出目录: {output_dir}/{name}/\n")


# ══════════════════════════════════════
#  CLI
# ══════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="1688 选品分析器（XLSX + HTML 备用）",
        epilog="""
数据来源:
  Path A [推荐]: 1688采购助手插件 → 搜索页 → 导出 XLSX
  Path B [备用]: 浏览器保存搜索页 HTML

示例:
  python -m selection.1688-picker data/1688/插件导出/ --name 灯具
  python -m selection.1688-picker data/1688/搜索页/ --from-html --name 灯具
        """,
    )
    parser.add_argument("data_dir")
    parser.add_argument("--name", "-n", required=True)
    parser.add_argument("--from-html", action="store_true", help="从 HTML 解析（备用）")
    parser.add_argument("--output", "-o", default="output/1688")
    args = parser.parse_args()

    if not os.path.isdir(args.data_dir):
        print(f"❌ 目录不存在: {args.data_dir}"); sys.exit(1)

    if args.from_html:
        print("  📡 Path B: HTML 解析")
        products = parse_html_dir(args.data_dir)
    else:
        xlsx_files = sorted(glob.glob(os.path.join(args.data_dir, "*.xlsx")))
        if not xlsx_files:
            print("⚠  无 XLSX, 走 HTML 备用")
            products = parse_html_dir(args.data_dir)
        else:
            products = []
            for f in xlsx_files:
                p = parse_xlsx(f)
                print(f"    {os.path.basename(f)}: {len(p)} 条")
                products.extend(p)

    if not products:
        print("❌ 无数据"); sys.exit(1)
    seen = set()
    unique = []
    for p in products:
        pid = p.get("product_id") or p.get("title", "")
        if pid not in seen:
            seen.add(pid)
            unique.append(p)
    dup = len(products) - len(unique)
    if dup:
        print(f"  ⚠ 去重 {dup} 条")
    analyze(args.name, unique, args.output)


if __name__ == "__main__":
    main()

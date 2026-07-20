#!/usr/bin/env python3
"""
震坤行选品分析器 (ZKH Product Picker)
======================================
从销量降序的 HTML 数据中提取商品信息，识别"行家精选"标签，
分析品牌格局，输出分级上架推荐清单。

用法:
    python3 picker.py data/ZKH/分析-专用灯具  --name 专用灯具
    python3 picker.py data/ZKH/分析-室内灯具  --name 室内灯具
    python3 picker.py data/ZKH/分析-户外灯具  --name 户外灯具
    python3 picker.py data/ZKH/分析-照明配套产品 --name 配套

批量:
    python3 picker.py --all

输出:
    output/上架清单_品类名.csv
    output/选品分析报告_品类名.txt
"""

import os, sys, re, json, csv
from collections import Counter, defaultdict

from selection.selection_schema import STRATEGY_LIMITS, STRATEGY_ORDER


# ═══════════════════════════════════════════════════════════════
#  1. HTML 解析
# ═══════════════════════════════════════════════════════════════

def parse_zkh_html(html: str) -> list[dict]:
    """
    解析震坤行搜索页 HTML，返回商品列表。
    注意：proGroupNo 按卡片出现顺序排列，用位置索引匹配。
    """
    # ── Step 1: 提取 JSON 中 proGroupNo → tags 映射 ──
    pro_nos_order = []
    pro_tags = {}
    for m in re.finditer(r'"proGroupNo"\s*:\s*"(\d+)"', html):
        pn = m.group(1)
        if not pro_nos_order or pn != pro_nos_order[-1]:
            pro_nos_order.append(pn)
            after = html[m.start():m.start() + 2000]
            tag_m = re.search(r'"productTags"\s*:\s*(\[[^\]]+\])', after)
            if tag_m:
                try:
                    tags = json.loads(tag_m.group(1))
                    pro_tags[pn] = [t['tagText'] for t in tags if t.get('tagText')]
                except Exception:
                    pro_tags[pn] = []
            else:
                pro_tags[pn] = []

    # ── Step 2: 按卡片分割 ──
    splitter = r'<div class="goods-item-wrap-new clearfix common-item-wrap">'
    parts = re.split(splitter, html)[1:]

    products = []
    card_idx = 0

    for part in parts:
        # 有效商品必须有标题
        name_m = re.search(r'goods-name[^>]*title="([^"]*)"', part)
        if not name_m:
            continue

        title = name_m.group(1).strip()

        # URL / 商品ID
        link_m = re.search(r'href="(https?://[^"]*)"', part)
        if not link_m:
            link_m = re.search(r'href="(/[^"]*)"', part)
        url = link_m.group(1) if link_m else ''
        if url and not url.startswith('http'):
            url = 'https://www.zkh.com' + url

        sku_m = re.search(r'/item/([^./?]+)', url)

        # 价格
        int_m = re.search(r'integer[^>]*>(\d+)<', part)
        dec_m = re.search(r'decimal[^>]*>([.\d]+)<', part)
        price_str = ''
        if int_m:
            price_str = int_m.group(1)
            if dec_m:
                price_str += dec_m.group(1)
        try:
            price_value = float(price_str)
        except (ValueError, TypeError):
            price_value = 0.0

        # 图片
        img_m = re.search(r'<img[^>]*src="([^"]*)"', part)
        img_count = len(re.findall(r'<li class="gls-item"', part))

        # 品牌（/ 后第一个词）
        brand = title.split('/', 1)[1].strip().split(' ')[0].strip() if '/' in title else ''

        # 型号
        model_m = re.search(r'制造商型号[^>]*>([^<]+)', part)
        model = model_m.group(1).strip() if model_m else ''

        # 单位
        unit_m = re.search(r'unit[^>]*>([^<]+)<', part)
        unit = unit_m.group(1) if unit_m else ''

        # 发货天数
        delivery_m = re.search(r'deliver[^>]*>([^<]+)', part)
        delivery = delivery_m.group(1).strip() if delivery_m else ''

        # 标签（按位置匹配 proGroupNo）
        tags = []
        if card_idx < len(pro_nos_order):
            tags = pro_tags.get(pro_nos_order[card_idx], [])

        products.append({
            'product_id': sku_m.group(1) if sku_m else '',
            'product_url': url,
            'title': title,
            'price': price_value,
            'brand': brand,
            'model': model,
            'unit': unit,
            'image_url': img_m.group(1) if img_m else '',
            'image_count': img_count,
            'delivery': delivery,
            'tags': tags,
        })
        card_idx += 1

    return products


# ═══════════════════════════════════════════════════════════════
#  2. 策略分类
# ═══════════════════════════════════════════════════════════════

def classify_product(rank: int, is_expert: bool) -> tuple:
    """
    根据排名和行家精选标记分类。
    排名 = 在销量降序排列中的绝对位置（1-based）。
    每页约60个商品。
    """
    page = (rank - 1) // 60 + 1
    if is_expert and page <= 3:
        return (1, '🔥 必上')
    if is_expert and page <= 8:
        return (2, '👍 推荐')
    if not is_expert and page <= 3:
        return (3, '💡 暗马')
    if is_expert:
        return (4, '🔹 补充')
    if page <= 5:
        return (5, '📌 关注')
    return (99, '—')


# ═══════════════════════════════════════════════════════════════
#  3. 分析 & 输出
# ═══════════════════════════════════════════════════════════════

def analyze_category(name: str, html_dir: str, output_dir: str):
    """分析一个品类，生成清单和报告"""
    html_files = sorted([
        f for f in os.listdir(html_dir)
        if f.endswith('.html') and not f.endswith('_files.html')
    ])

    if not html_files:
        print(f"  ⚠ {name}: 目录下无 HTML 文件", file=sys.stderr)
        return

    # ── 解析所有页面 ──
    all_products = []
    for fname in html_files:
        fpath = os.path.join(html_dir, fname)
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
        products = parse_zkh_html(html)
        all_products.extend(products)

    total = len(all_products)
    experts = [p for p in all_products if '行家精选' in p['tags']]

    print(f"\n  📁 {name}")
    print(f"     解析 {len(html_files)} 页, 共 {total} 个商品, 行家精选 {len(experts)} 个")

    # ── 策略分类 ──
    classified = []
    for i, p in enumerate(all_products):
        rank = i + 1
        is_expert = '行家精选' in p['tags']
        priority, label = classify_product(rank, is_expert)
        p['_rank'] = rank
        p['_page'] = (rank - 1) // 60 + 1
        p['_priority'] = priority
        p['_strategy'] = label
        classified.append(p)

    # ── 按策略分文件输出（每个品类一个子目录） ──
    strategy_limits = STRATEGY_LIMITS.copy()
    strategy_limits['🔹 补充'] = 0

    cat_dir = os.path.join(output_dir, name)
    os.makedirs(cat_dir, exist_ok=True)

    list_fields = ['排名', '品牌', '标题', '价格', '型号', '行家精选', '页码', '图片数', '链接']
    total_shown = 0

    for strategy_tag in STRATEGY_ORDER:
        limit = strategy_limits[strategy_tag]
        if limit == 0:
            continue

        items = [p for p in classified if p['_strategy'] == strategy_tag][:limit]
        if not items:
            continue

        fname = f'{strategy_tag}.csv'
        fpath = os.path.join(cat_dir, fname)

        with open(fpath, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=list_fields)
            w.writeheader()
            for p in items:
                w.writerow({
                    '排名': p['_rank'],
                    '品牌': p['brand'],
                    '标题': p['title'],
                    '价格': p['price'],
                    '型号': p['model'],
                    '行家精选': '是' if '行家精选' in p['tags'] else '',
                    '页码': p['_page'],
                    '图片数': p['image_count'],
                    '链接': p['product_url'],
                })
        total_shown += len(items)
        print(f"      {fname}: {len(items)} 条")

    # ── 汇总合并（选品推荐合集，控制在40-50条） ──
    merge = []
    for strategy_tag in STRATEGY_ORDER:
        limit = STRATEGY_LIMITS[strategy_tag]
        if limit == 0: continue
        for p in classified:
            if p['_strategy'] == strategy_tag:
                merge.append(p)
                if len([x for x in merge if x['_strategy'] == strategy_tag]) >= limit:
                    break

    merge_fields = ['策略', '排名', '品牌', '标题', '价格', '型号', '行家精选', '链接']
    merge_path = os.path.join(cat_dir, '00-选品推荐合集.csv')
    with open(merge_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=merge_fields)
        w.writeheader()
        for p in merge:
            w.writerow({
                '策略': p['_strategy'],
                '排名': p['_rank'],
                '品牌': p['brand'],
                '标题': p['title'],
                '价格': p['price'],
                '型号': p['model'],
                '行家精选': '是' if '行家精选' in p['tags'] else '',
                '链接': p['product_url'],
            })
    print(f"      00-选品推荐合集.csv: {len(merge)} 条")
    print(f"      → 共 {total_shown} 个值得上架的商品")

    # ── 输出分析报告（同步 selection_schema 模板格式） ──
    report_path = os.path.join(output_dir, f'选品分析_{name}.txt')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"震坤行选品分析报告 — {name}\n")
        f.write("=" * 50 + "\n\n")
        f.write("【概览】\n")
        f.write(f"  商品总数:   {total}\n")
        f.write(f"  推荐上架:   {total_shown} 个\n")
        f.write(f"  行家精选:   {len(experts)} 个\n")
        prices = [p['price'] for p in all_products if p['price'] > 0]
        if prices:
            f.write(f"  价格区间:   ¥{min(prices):.2f} ~ ¥{max(prices):.2f}\n")
            f.write(f"  均价:       ¥{sum(prices)/len(prices):.2f}\n")
        f.write(f"  品牌数:     {len(Counter(p['brand'] for p in all_products if p['brand']))}\n\n")

        # 推荐上架分布（实际输出数量）
        strat_shown = Counter(p['_strategy'] for p in merge)
        f.write("【推荐上架分布】\n")
        for tag in STRATEGY_ORDER:
            c = strat_shown.get(tag, 0)
            if c:
                f.write(f"  {tag}: {c} 个\n")
        f.write("\n")

        # 品牌TOP
        brand_counts = Counter(p['brand'] for p in all_products if p['brand'])
        f.write("【品牌TOP10】\n")
        for b, n in brand_counts.most_common(10):
            e = sum(1 for p in all_products if p['brand'] == b and '行家精选' in p['tags'])
            star = f' ⭐{e}' if e else ''
            f.write(f"  {b:<16} {n:3} 个{star}\n")
        f.write("\n")

        # 按策略分组
        by_strat = {t: [p for p in merge if p['_strategy'] == t] for t in STRATEGY_ORDER}
        for tag in ["🔥 必上", "💡 暗马"]:
            items = by_strat.get(tag, [])
            if items:
                label = "🔥 必上清单" if tag == "🔥 必上" else "💡 暗马精选"
                f.write(f"【{label}】\n")
                for p in items:
                    expert = '⭐' if '行家精选' in p['tags'] else ''
                    f.write(f"  ¥{p['price']:>7.2f}  {p['brand']:12}  {p['title'][:40]}\n")
                f.write("\n")

        f.write("=" * 50 + "\n")
        f.write(f"输出目录: {output_dir}/{name}/\n")
    print(f"     报告: {report_path}")

    return classified


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='震坤行选品分析器 - 解析销量降序HTML，输出上架推荐清单',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('html_dir', nargs='?', help='HTML 文件目录')
    parser.add_argument('--name', '-n', help='品类名称')
    parser.add_argument('--all', '-a', action='store_true', help='批量分析 data/ZKH/分析-* 所有品类')
    parser.add_argument('--output', '-o', default='data/ZKH/震坤行/上架清单', help='输出目录')

    args = parser.parse_args()

    # 确定要分析的品类
    categories = []

    if args.all:
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'ZKH')
            # __file__ = selection/zkh-picker.py, os.path.dirname × 2 = project root
        if not os.path.isdir(base):
            base = 'data/ZKH'
        for d in sorted(os.listdir(base)):
            if d.startswith('分析-'):
                cat_name = d.replace('分析-', '').replace('照明配套产品', '配套')
                categories.append((cat_name, os.path.join(base, d)))
    elif args.html_dir and args.name:
        categories.append((args.name, args.html_dir))
    else:
        parser.print_help()
        print("\n示例:")
        print("  python3 picker.py data/ZKH/分析-室内灯具 --name 室内灯具")
        print("  python3 picker.py --all")
        sys.exit(1)

    # 输出目录
    output_dir = os.path.abspath(args.output)
    os.makedirs(output_dir, exist_ok=True)

    print("═" * 55)
    print("  震坤行选品分析器 v1")
    print("═" * 55)

    all_results = []
    for name, hdir in categories:
        result = analyze_category(name, hdir, output_dir)
        if result:
            all_results.extend(result)

    # 汇总
    if len(categories) > 1 and all_results:
        total = len(all_results)
        experts = sum(1 for p in all_results if '行家精选' in p['tags'])
        strat = Counter(p['_strategy'] for p in all_results if p['_priority'] <= 5)
        print(f"\n{'='*55}")
        print(f"  汇总: {len(categories)} 品类, {total} 商品, 行家精选 {experts}")
        print(f"  推荐上架: {sum(n for s, n in strat.most_common())} 个")
        print(f"  输出目录: {output_dir}/")
        print(f"{'='*55}")

    # ── 赛后总结（复用 auto_pick 的分析能力）──
    if len(categories) > 0:
        try:
            from selection.auto_pick import summarize_selection, print_summary
            summary = summarize_selection(output_dir)
            print()
            print_summary(summary)
        except Exception:
            pass  # 不影响主流程

    print("\n✅ 分析完成")


if __name__ == '__main__':
    main()

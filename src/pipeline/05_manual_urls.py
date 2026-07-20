"""
手动录入商品详情页URL
打开 1688.com，搜索商品，把详情页URL贴进来
"""
import csv
import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_targets(category, top_n=10):
    from collections import Counter
    csv_path = os.path.join(PROJECT_DIR, "data", category, "cleaned_products.csv")
    if not os.path.exists(csv_path):
        print(f"错误: 未找到 {csv_path}")
        return []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    shop_counter = Counter(r['shop_name'] for r in rows if r['shop_name'])
    top_shops = [s for s, _ in shop_counter.most_common(top_n)]
    targets = []
    for shop in top_shops:
        shop_products = [r for r in rows if r['shop_name'] == shop]
        if not shop_products:
            continue
        priced = []
        for r in shop_products:
            try:
                priced.append((float(r['price']), r))
            except:
                pass
        if not priced:
            priced = [(0, shop_products[0])]
        priced.sort(key=lambda x: x[0])
        target = priced[len(priced) // 2][1]
        targets.append({
            'shop_name': shop,
            'title': target['title'],
            'price': target['price'],
            'product_count': shop_counter[shop],
        })
    return targets


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--cat', default='投光灯')
    parser.add_argument('--top', type=int, default=10)
    args = parser.parse_args()

    targets = get_targets(args.cat, args.top)
    if not targets:
        return

    print(f"\n{'='*60}")
    print(f"手动录入: {args.cat} Top {args.top}")
    print(f"请打开 1688.com，搜索商品，复制详情页URL粘贴过来")
    print(f"{'='*60}")

    results = []
    for i, t in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {t['shop_name']}  ({t['product_count']}个商品)")
        print(f"  关键词: {t['shop_name']} {t['title'][:20]}")
        url = input(f"  详情页URL: ").strip()
        results.append({
            'shop_name': t['shop_name'],
            'title': t['title'],
            'detail_url': url,
        })

    out_path = os.path.join(PROJECT_DIR, "data", args.cat, "top_products_urls.csv")
    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['shop_name', 'title', 'detail_url'])
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ 已保存: {out_path}")


if __name__ == '__main__':
    main()

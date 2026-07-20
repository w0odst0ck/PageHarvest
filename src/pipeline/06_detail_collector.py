"""直接用1688库的AlibabaParser解析详情页HTML"""
import csv, os, sys, json

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 把1688库加入路径
LIB_PATH = os.path.join(PROJECT_DIR, '1688', '1688')
sys.path.insert(0, LIB_PATH)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--cat', default='投光灯')
    args = parser.parse_args()

    # 读详情页URL
    url_csv = os.path.join(PROJECT_DIR, "data", args.cat, "top_products_urls.csv")
    with open(url_csv, 'r', encoding='utf-8-sig') as f:
        products = list(csv.DictReader(f))
    products = [p for p in products if p.get('detail_url')]

    # 找到已保存的HTML
    base_dir = os.path.join(PROJECT_DIR, "data", args.cat, "products_detail")

    # 导入1688库解析器
    from utils.parsers.alibaba_parser import AlibabaParser

    results = []
    print(f"\n共 {len(products)} 个商品")

    for i, p in enumerate(products, 1):
        oid_match = __import__('re').search(r'/offer/(\d+)', p['detail_url'])
        oid = oid_match.group(1) if oid_match else 'unknown'
        html_path = os.path.join(base_dir, oid, f"{oid}.html")

        print(f"\n[{i}/{len(products)}] {p['shop_name']} ({oid})")

        if not os.path.exists(html_path):
            print(f"  跳过: HTML不存在 {html_path}")
            continue

        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()

        print(f"  HTML: {len(html)//1024}KB")

        # 用1688库解析器
        parser = AlibabaParser(html)

        title = parser.get_title()
        shop_info = parser.get_shop_info()
        ship_from = parser.get_ship_from()
        sales = parser.get_sales_count()
        min_order = parser.get_min_order()
        attrs = parser.get_attributes()
        main_imgs = parser.get_main_images()
        detail_imgs = parser.get_detail_images()
        vids = parser.get_videos()
        skus = parser.get_sku_matrix()
        plugin = parser.get_plugin_data()
        trend = parser.get_trend_data()

        brand = ''
        spec = ''
        for k, v in attrs:
            if '品牌' in k:
                brand = v
            if '型号' in k or '货号' in k:
                spec = v

        ship = ship_from or plugin.get('category', '')
        yearly = trend.get('yearly_sales', plugin.get('yearly_sales_pieces', ''))
        listing = plugin.get('listing_date', '')

        print(f"  标题: {(title or '')[ :35]}")
        print(f"  店铺: {shop_info.get('shop_name','') if shop_info else ''}")
        print(f"  品牌: {brand or '-'}  型号: {spec or '-'}")
        print(f"  发货地: {ship or '-'}")
        print(f"  主图: {len(main_imgs)}  详情图: {len(detail_imgs)}  视频: {len(vids)}")
        print(f"  SKU: {len(skus)}  属性: {len(attrs)}")
        print(f"  年销量: {yearly}  上架: {listing}")

        # 保存解析结果
        prod_dir = os.path.join(base_dir, oid)
        os.makedirs(prod_dir, exist_ok=True)
        res_path = os.path.join(prod_dir, '_1688_parsed.txt')
        with open(res_path, 'w', encoding='utf-8') as f:
            f.write(f"标题: {title}\n")
            f.write(f"店铺: {shop_info.get('shop_name','') if shop_info else ''}\n")
            f.write(f"品牌: {brand}  型号: {spec}\n")
            f.write(f"发货地: {ship}\n")
            f.write(f"销量: {sales}  起批量: {min_order}\n")
            f.write(f"年销量: {yearly}  上架: {listing}\n\n")
            f.write(f"主图 ({len(main_imgs)}张):\n")
            for u in main_imgs:
                f.write(f"  {u}\n")
            f.write(f"\n详情图 ({len(detail_imgs)}张):\n")
            for u in detail_imgs:
                f.write(f"  {u}\n")
            f.write(f"\n视频 ({len(vids)}个):\n")
            for u in vids:
                f.write(f"  {u}\n")
            f.write(f"\n属性 ({len(attrs)}条):\n")
            for k, v in attrs:
                f.write(f"  {k}: {v}\n")
            f.write(f"\nSKU ({len(skus)}条):\n")
            for s in skus:
                f.write(f"  {s.get('sku_name','')}  ¥{s.get('price',0)}  库存{s.get('stock',0)}\n")

        print(f"  已保存: {res_path}")

        results.append({
            'offer_id': oid,
            'shop_name': p['shop_name'],
            'title': title or '',
            'brand': brand,
            'spec': spec,
            'ship_from': ship,
            'main_images': len(main_imgs),
            'detail_images': len(detail_imgs),
            'videos': len(vids),
            'sku_count': len(skus),
            'attribute_count': len(attrs),
            'yearly_sales': yearly,
            'listing_date': listing,
            'status': 'OK',
        })

    # 保存汇总
    out_path = os.path.join(PROJECT_DIR, "data", args.cat, "top_products_details.csv")
    fnames = ['offer_id', 'shop_name', 'title', 'brand', 'spec',
              'ship_from', 'main_images', 'detail_images', 'videos',
              'sku_count', 'attribute_count', 'yearly_sales', 'listing_date', 'status']
    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fnames)
        w.writeheader()
        w.writerows(results)
    print(f"\n✅ 汇总: {out_path}")


if __name__ == '__main__':
    main()

"""
1688 搜索结果HTML解析器 v2
从油猴下载的HTML中提取商品数据 → CSV

用法:
    python parser.py           # 解析 data/ 下所有HTML → CSV
    python parser.py --stats   # 统计已有CSV

提取字段:
  keyword, title, price, sales, desc, tags,
  shop_name, shop_url, image_url,
  category, yearly_sales, monthly_dist, fulfillment_rate,
  listing_date, review_count, shop_age, return_rate
"""

import os, glob, csv, re, sys
from bs4 import BeautifulSoup
from collections import Counter

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")

# 支持 --cat 参数指定品类
CATEGORY = None
for i, a in enumerate(sys.argv[1:], 1):
    if a == '--cat' and i < len(sys.argv):
        CATEGORY = sys.argv[i + 1]
        break

FIELDS = [
    'keyword', 'title', 'price', 'sales', 'desc', 'tags',
    'shop_name', 'shop_url', 'image_url',
    'category', 'yearly_sales', 'monthly_dist',
    'fulfillment_rate', 'listing_date',
    'review_count', 'shop_age', 'return_rate'
]


def parse_html(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    keyword = os.path.basename(filepath).replace('.html', '')
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.find_all(class_=re.compile(r'search-offer-item'))

    products = []
    for item in items:
        try:
            p = {'keyword': keyword}

            # 标题
            el = item.find(class_='offer-title-row')
            p['title'] = el.get_text(strip=True) if el else ''

            # 价格
            el = item.find(class_='offer-price-row')
            price_text = el.get_text(strip=True) if el else ''
            m = re.search(r'[\d]+(?:\.\d+)?', price_text.replace(',', ''))
            p['price'] = m.group() if m else ''

            # 销量（从desc-text中提取）
            p['sales'] = ''
            for d in item.find_all(class_='desc-text'):
                t = d.get_text(strip=True)
                if '成交' in t or '销量' in t:
                    p['sales'] = t
                    break

            # 描述
            el = item.find(class_='offer-desc-row')
            p['desc'] = el.get_text(strip=True) if el else ''

            # 标签
            tags = []
            el = item.find(class_='offer-tag-row')
            if el:
                for dt in el.find_all(class_='desc-text'):
                    tags.append(dt.get_text(strip=True))
            p['tags'] = '|'.join(tags)

            # 店铺
            p['shop_name'] = ''
            p['shop_url'] = ''
            el = item.find(class_='offer-shop-row')
            if el:
                link = el.find('a')
                if link:
                    p['shop_name'] = link.get_text(strip=True)
                    p['shop_url'] = link.get('href', '')

            # 图片
            img = item.find('img', class_='main-img')
            p['image_url'] = img.get('src', '') if img else ''

            # ========== 插件扩展数据 (plugin-offer-search-card) ==========
            p['category'] = ''
            p['yearly_sales'] = ''
            p['monthly_dist'] = ''
            p['fulfillment_rate'] = ''
            p['listing_date'] = ''
            p['review_count'] = ''
            p['shop_age'] = ''
            p['return_rate'] = ''

            extra = item.find(class_='plugin-offer-search-card')
            if extra:
                text = extra.get_text(strip=True)
                # 解析键值对: 年销量:XXX 月代销:XXX 等
                for key, field in [
                    ('类目:', 'category'),
                    ('年销量:', 'yearly_sales'),
                    ('月代销:', 'monthly_dist'),
                    ('48h揽收:', 'fulfillment_rate'),
                    ('上架日期:', 'listing_date'),
                    ('评论数:', 'review_count'),
                    ('开店:', 'shop_age'),
                    ('回头率:', 'return_rate'),
                ]:
                    idx = text.find(key)
                    if idx >= 0:
                        end = len(text)
                        # 找下一个冒号或结尾
                        for next_key in ['类目:', '年销量:', '月代销:', '48h揽收:',
                                         '支持面单:', '上架日期:', '评论数:', '开店:', '回头率:']:
                            nidx = text.find(next_key, idx + len(key))
                            if nidx > idx:
                                end = min(end, nidx)
                        p[field] = text[idx + len(key):end].strip().rstrip(',')

            products.append(p)
        except Exception as e:
            continue

    return products


def parse_all():
    html_files = []
    search_root = os.path.join(DATA_DIR, CATEGORY) if CATEGORY else DATA_DIR
    if not os.path.exists(search_root):
        print("错误: 目录不存在", search_root)
        return []
    for root, dirs, files in os.walk(search_root):
        for f in files:
            if f.endswith('.html') and not f.endswith('_files.html'):
                html_files.append(os.path.join(root, f))

    if not html_files:
        print("错误: data/ 目录下没有HTML文件")
        return []

    all_products = []
    for f in sorted(html_files):
        products = parse_html(f)
        all_products.extend(products)
        print("  {}: {} 个".format(os.path.basename(f)[:25], len(products)))

    return all_products


def save_csv(products, filepath):
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(products)
    print("\n已保存: " + filepath)


def print_stats(products):
    print("\n========== 统计 ==========")
    print("总商品数:", len(products))
    print("去重标题:", len(set(p['title'] for p in products)))

    kw_count = Counter(p['keyword'] for p in products)
    print("\n各关键词:")
    for kw, n in kw_count.most_common():
        print("  {}: {} 个".format(kw, n))

    prices = []
    for p in products:
        try:
            prices.append(float(p['price']))
        except:
            pass
    if prices:
        prices.sort()
        print("\n价格分布:")
        print("  最低:   ¥{:.2f}".format(prices[0]))
        print("  最高:   ¥{:.2f}".format(prices[-1]))
        print("  中位数:  ¥{:.2f}".format(prices[len(prices)//2]))
        print("  平均:   ¥{:.2f}".format(sum(prices)/len(prices)))

    # 统计有插件数据的商品数
    with_data = sum(1 for p in products if p.get('category'))
    print("\n插件数据覆盖率: {}/{} ({:.0f}%)".format(
        with_data, len(products), with_data/len(products)*100))


if __name__ == "__main__":
    import sys

    if '--stats' in sys.argv:
        csv_file = os.path.join(DATA_DIR, "all_products.csv")
        if os.path.exists(csv_file):
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                products = list(reader)
            print_stats(products)
        else:
            print("未找到 all_products.csv")
        sys.exit(0)

    products = parse_all()
    if not products:
        sys.exit(1)

    out_dir = os.path.join(DATA_DIR, CATEGORY) if CATEGORY else DATA_DIR
    csv_path = os.path.join(out_dir, "all_products.csv")
    save_csv(products, csv_path)
    print_stats(products)

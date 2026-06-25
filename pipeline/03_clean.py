"""
03_clean.py — 数据清洗
输入: data/all_products.csv (17字段原始数据)
输出: data/cleaned_products.csv

清洗内容:
  1. 价格修正: 去除异常值, 标准化格式
  2. 标题清洗: 去除冗余后缀("标题链接标+链")
  3. 标签结构化: 提取回头率, 服务标签
  4. 供应商名称去前后空格
  5. 类目路径拆分
  6. 去重 (同标题+同供应商视为重复)
  7. 品牌识别 (从标题中匹配已知品牌)
"""

import os, csv, re, sys
from collections import Counter

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(PROJECT_DIR, "data", "all_products.csv")
OUTPUT = os.path.join(PROJECT_DIR, "data", "cleaned_products.csv")

# 已知照明品牌词库 (可扩展)
BRAND_KEYWORDS = [
    '欧普', '雷士', '飞利浦', 'Philips', '松下', 'Panasonic',
    '佛山照明', 'FSL', '三雄极光', '公牛', 'BULL',
    '小米', '华为', 'Yeelight', '美的', 'Midea', 'TCL',
    '西门子', 'Siemens', 'ABB', '施耐德', 'Schneider',
    '德力西', '正泰', 'CHNT', '阳光照明', 'Yankon',
    '木林森', 'MLS', '欧司朗', 'Osram', 'GE',
    '西顿', 'CDN', '三思', '华艺', '琪朗',
    '涂鸦', 'Tuya', '天猫精灵', '小爱同学',
    'opple', 'nvc', 'viborg', 'DALI', 'KNX',
]


def clean_price(price_str):
    """价格标准化"""
    if not price_str:
        return ''
    price_str = price_str.strip()
    # 去除多余小数点 (如 "6.82.2")
    parts = price_str.split('.')
    if len(parts) > 2:
        price_str = parts[0] + '.' + parts[1]
    try:
        val = float(price_str)
        if val <= 0 or val > 9999999:
            return ''
        return price_str
    except:
        return ''


def clean_title(title):
    """标题清洗"""
    # 去除采购助手追加的后缀 "标题链接标+链"
    for suffix in ['标题链接标+链', '标题', '链接', '标+链']:
        idx = title.rfind(suffix)
        if idx > 0:
            title = title[:idx]
    return title.strip()


def extract_brand(title):
    """从标题中提取品牌"""
    for brand in BRAND_KEYWORDS:
        if brand in title:
            return brand
    return ''


def extract_return_rate(tags):
    """从标签中提取回头率"""
    if '回头率' in tags:
        m = re.search(r'回头率(\d+)%', tags)
        if m:
            return m.group(1) + '%'
    return ''


def main():
    if not os.path.exists(INPUT):
        print("错误: 未找到 {}".format(INPUT))
        print("请先运行 02_parse.py")
        sys.exit(1)

    with open(INPUT, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print("原始数据: {} 条".format(len(rows)))

    cleaned = []
    dup_key = set()
    dup_count = 0
    removed_count = 0

    for r in rows:
        # 价格清洗
        r['price'] = clean_price(r['price'])
        if not r['price']:
            removed_count += 1
            continue

        # 标题清洗
        r['title'] = clean_title(r['title'])
        if len(r['title']) < 5:
            removed_count += 1
            continue

        # 品牌识别
        r['brand'] = extract_brand(r['title'])

        # 回头率
        tag_text = r.get('tags', '')
        if not r.get('return_rate'):
            r['return_rate'] = extract_return_rate(tag_text)

        # 供应商清洗
        r['shop_name'] = r['shop_name'].strip()

        # 去重 (标题前20字 + 供应商)
        dedup_key = (r['title'][:20], r['shop_name'])
        if dedup_key in dup_key:
            dup_count += 1
            continue
        dup_key.add(dedup_key)

        cleaned.append(r)

    # 写CSV
    fieldnames = [
        'keyword', 'title', 'price', 'sales', 'desc', 'tags',
        'shop_name', 'shop_url', 'image_url',
        'category', 'yearly_sales', 'monthly_dist',
        'fulfillment_rate', 'listing_date',
        'review_count', 'shop_age', 'return_rate',
        'brand'
    ]

    with open(OUTPUT, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned)

    print("\n清洗结果:")
    print("  无效价格/标题移除:  {} 条".format(removed_count))
    print("  重复商品去重:       {} 条".format(dup_count))
    print("  有效数据:           {} 条".format(len(cleaned)))
    print("  识别到品牌:         {} 条".format(sum(1 for c in cleaned if c['brand'])))
    print("  输出文件:           {}".format(OUTPUT))

    # 品牌统计
    brand_stats = Counter(c['brand'] for c in cleaned if c['brand'])
    if brand_stats:
        print("\n品牌分布:")
        for brand, n in brand_stats.most_common(10):
            print("  {}: {} 个".format(brand, n))


if __name__ == "__main__":
    main()

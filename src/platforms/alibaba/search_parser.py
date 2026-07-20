"""
1688 搜索页解析器
继承自原有 02_parse.py 的核心逻辑，封装为平台解析器。
"""

import os, csv, re, sys
from bs4 import BeautifulSoup
from collections import Counter

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIELDS = [
    'keyword', 'title', 'price', 'sales', 'desc', 'tags',
    'shop_name', 'shop_url', 'image_url',
    'category', 'yearly_sales', 'monthly_dist',
    'fulfillment_rate', 'listing_date',
    'review_count', 'shop_age', 'return_rate'
]


def parse_html(filepath):
    """
    ★ 核心逻辑：继承原有的 parse_html，不做任何变动。
    从单个1688搜索页HTML提取商品数据，返回 dict 列表。
    """
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


def parse_html_to_raw(html: str, keyword: str) -> list[dict]:
    """
    直接解析 HTML 字符串（用于适配器调用）。
    与原 parse_html 等价，但接受字符串而非文件路径。
    """
    soup = BeautifulSoup(html, 'html.parser')
    items = soup.find_all(class_=re.compile(r'search-offer-item'))

    products = []
    for item in items:
        try:
            p = {'keyword': keyword}

            el = item.find(class_='offer-title-row')
            p['title'] = el.get_text(strip=True) if el else ''

            el = item.find(class_='offer-price-row')
            price_text = el.get_text(strip=True) if el else ''
            m = re.search(r'[\d]+(?:\.\d+)?', price_text.replace(',', ''))
            p['price'] = m.group() if m else ''

            p['sales'] = ''
            for d in item.find_all(class_='desc-text'):
                t = d.get_text(strip=True)
                if '成交' in t or '销量' in t:
                    p['sales'] = t
                    break

            el = item.find(class_='offer-desc-row')
            p['desc'] = el.get_text(strip=True) if el else ''

            tags = []
            el = item.find(class_='offer-tag-row')
            if el:
                for dt in el.find_all(class_='desc-text'):
                    tags.append(dt.get_text(strip=True))
            p['tags'] = '|'.join(tags)

            p['shop_name'] = ''
            p['shop_url'] = ''
            el = item.find(class_='offer-shop-row')
            if el:
                link = el.find('a')
                if link:
                    p['shop_name'] = link.get_text(strip=True)
                    p['shop_url'] = link.get('href', '')

            img = item.find('img', class_='main-img')
            p['image_url'] = img.get('src', '') if img else ''

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
                        for next_key in ['类目:', '年销量:', '月代销:', '48h揽收:',
                                         '支持面单:', '上架日期:', '评论数:', '开店:', '回头率:']:
                            nidx = text.find(next_key, idx + len(key))
                            if nidx > idx:
                                end = min(end, nidx)
                        p[field] = text[idx + len(key):end].strip().rstrip(',')

            products.append(p)
        except Exception:
            continue

    return products


def raw_to_unified(raw: list[dict], platform: str = "1688",
                   keyword: str = "") -> list:
    """
    将原始 dict 转为 UnifiedProduct。
    """
    from core.schema import UnifiedProduct
    import re as _re

    results = []
    for item in raw:
        # 提取 product_id 从 shop_url 或详情链接
        pid = ""
        url = item.get('shop_url', '')
        m = _re.search(r'offerId=(\d+)', url)
        if m:
            pid = m.group(1)
        if not pid and item.get('shop_url'):
            m = _re.search(r'/offer/(\d+)', item.get('shop_url', ''))
            if m:
                pid = m.group(1)

        try:
            price = float(item.get('price', 0)) if item.get('price') else 0.0
        except:
            price = 0.0

        # 解析年销量
        yearly = item.get('yearly_sales', '')
        sales_text = yearly if yearly else item.get('sales', '')

        # 解析评论数
        review_count = 0
        rc = item.get('review_count', '')
        if rc:
            m = _re.search(r'\d+', rc)
            if m:
                review_count = int(m.group())

        # 回头率→评分
        rating = 0.0
        rr = item.get('return_rate', '')
        if rr:
            m = _re.search(r'[\d.]+', rr)
            if m:
                rating = float(m.group())

        up = UnifiedProduct(
            platform=platform,
            product_id=pid,
            product_url=f"https://detail.1688.com/offer/{pid}.html" if pid else '',
            title=item.get('title', ''),
            price_min=price,
            price_max=price,
            shop_name=item.get('shop_name', ''),
            sales_text=sales_text,
            review_count=review_count,
            rating=rating,
            image_url=item.get('image_url', ''),
            tags=item.get('tags', '').split('|') if item.get('tags') else [],
            raw_data=item,
        )
        results.append(up)

    return results

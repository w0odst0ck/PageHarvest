"""
震坤行 (zkh.com) 搜索页解析器
"""
import re, json
from typing import Optional
from core.schema import UnifiedProduct


def parse_search_html(html: str, keyword: str) -> list[dict]:
    """
    解析震坤行搜索页 HTML → 原始字典列表。
    """
    products = []

    # 按商品卡片分割
    splitter = r'<div class="goods-item-wrap-new clearfix common-item-wrap">'
    parts = re.split(splitter, html)
    cards_html = []

    for i, part in enumerate(parts[1:], 1):
        next_split = re.search(splitter, part)
        cards_html.append(part[:next_split.start()] if next_split else part)

    for card in cards_html:
        name_m = re.search(r'goods-name[^>]*title="([^"]*)"', card)
        title = name_m.group(1).strip() if name_m else ''
        if not title:
            continue

        # 优先取绝对链接，其次相对链接
        link_m = re.search(r'href="(https?://[^"]*)"', card)
        if not link_m:
            link_m = re.search(r'href="(/[^"]*)"', card)
        url = link_m.group(1) if link_m else ''
        # 相对链接补全
        if url and not url.startswith('http'):
            url = 'https://www.zkh.com' + url

        sku_m = re.search(r'/item/([^./?]+)', url)
        product_id = sku_m.group(1) if sku_m else ''

        int_m = re.search(r'integer[^>]*>(\d+)<', card)
        dec_m = re.search(r'decimal[^>]*>([.\d]+)<', card)
        price_str = ''
        if int_m:
            price_str = int_m.group(1)
            if dec_m:
                price_str += dec_m.group(1)

        price_value = 0.0
        try:
            price_value = float(price_str)
        except (ValueError, TypeError):
            pass

        img_m = re.search(r'<img[^>]*src="([^"]*)"', card)
        image = img_m.group(1) if img_m else ''

        # 中文品牌名（/ 后第一个词，可读性更高）
        if '/' in title:
            after_slash = title.split('/', 1)[1].strip()
            brand = after_slash.split(' ')[0].strip() if ' ' in after_slash else after_slash
        else:
            brand = ''

        model_m = re.search(r'制造商型号[^>]*>([^<]+)', card)
        model = model_m.group(1).strip() if model_m else ''

        unit_m = re.search(r'unit[^>]*>([^<]+)<', card)
        unit = unit_m.group(1) if unit_m else ''

        products.append({
            'product_id': product_id,
            'product_url': url,
            'title': title,
            'price': price_value,
            'currency': 'CNY',
            'brand': brand,
            'image_url': image,
            'model': model,
            'unit': unit,
        })

    # 第二步：从页面 JSON 中提取 productTags，按 product_id 匹配
    # productTags 在商品 JSON 数据中，通过 sku/产品ID 关联
    tag_map = {}  # sku -> [tag_text, ...]
    for m in re.finditer(r'"(sku|productId|id)":\s*"([A-Z0-9]+)"[^}]*?"productTags":\s*(\[[^\]]+\])', html):
        try:
            sku = m.group(2)
            tags_json = json.loads(m.group(3))
            tags = [t.get('tagText', '') for t in tags_json if t.get('tagText')]
            if tags:
                tag_map[sku] = tags
        except:
            pass

    for p in products:
        sku = p['product_id']
        if sku in tag_map:
            p['tags'] = tag_map[sku]
        else:
            p['tags'] = []

    return products


def raw_to_unified(raw_list: list[dict]) -> list[UnifiedProduct]:
    """原始字典 → UnifiedProduct"""
    return [
        UnifiedProduct(
            platform='震坤行',
            product_id=p['product_id'],
            product_url=p['product_url'],
            title=p['title'],
            price_min=p['price'],
            price_max=p['price'],
            currency=p['currency'],
            brand=p['brand'],
            image_url=p['image_url'],
            tags=p.get('tags', []),
            raw_data={'model': p['model'], 'unit': p['unit']},
        )
        for p in raw_list
    ]

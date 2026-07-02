"""
京东搜索页解析器
京东搜索页是 React SPA，CSS 类名为 webpack hash。
解析策略：不用类名精确匹配，而是通过 data-* 属性和结构特征定位。
"""

import re
from bs4 import BeautifulSoup
from typing import Optional


def _int_from_text(text: str) -> int:
    """从"已售5万+"、"8000+"等文本中提取数值"""
    if not text:
        return 0
    m = re.search(r'([\d.]+)(万)?', text)
    if not m:
        return 0
    val = float(m.group(1))
    if m.group(2):  # 万单位
        val *= 10000
    return int(val)


def _float_from_text(text: str) -> float:
    """从"¥152.8"或"152.8"中提取数值"""
    if not text:
        return 0.0
    m = re.search(r'([\d.]+)', text)
    return float(m.group(1)) if m else 0.0


def parse_search_html(html: str, keyword: str) -> list[dict]:
    """
    解析京东搜索页 HTML，返回原始 dict 列表。
    不依赖 CSS 类名精确匹配，通过 data-sku 属性定位商品卡片。
    """
    soup = BeautifulSoup(html, 'html.parser')
    products = []

    # 定位商品卡片：所有带 data-sku 属性的 div
    card_wrappers = soup.find_all('div', attrs={'data-sku': True})

    for card in card_wrappers:
        try:
            sku = card.get('data-sku', '')
            if not sku or sku == 'true':  # 过滤非商品元素
                continue

            # ── 标题：span[title] 优先，title 属性包含完整标题 ──
            title_el = card.find('span', title=True)
            title = title_el.get('title', '') if title_el else ''
            if not title:
                # fallback: 找 class 含有 title 的 span
                for span in card.find_all('span'):
                    if span.get('title'):
                        title = span['title']
                        break

            # ── 价格 ──
            price_min = 0.0
            price_max = 0.0

            # 策略: 找所有含 ¥ 的文本，取最小的为主价，其他为划线价
            all_prices = []
            for tag in card.find_all(['span', 'i', 'div']):
                text = tag.get_text(strip=True)
                m = re.search(r'¥([\d.]+)', text)
                if m:
                    val = float(m.group(1))
                    if val not in all_prices:
                        all_prices.append(val)

            # 找 class 含 gray 的灰色价格（划线价）
            gray_prices = []
            for tag in card.find_all(class_=lambda c: c and 'gray' in c.lower() if c else False):
                text = tag.get_text(strip=True)
                m = re.search(r'([\d.]+)', text)
                if m:
                    gray_prices.append(float(m.group(1)))

            if all_prices:
                all_prices.sort()
                price_min = all_prices[0]
                if gray_prices:
                    price_max = max(gray_prices)
                elif len(all_prices) > 1:
                    price_max = max(all_prices)

            if price_min == 0.0:
                # fallback: 全局搜索
                all_text = card.get_text()
                m = re.search(r'¥(\d+\.?\d*)', all_text)
                if m:
                    price_min = float(m.group(1))

            # ── 店铺名 ──
            shop_name = ''
            shop_els = card.find_all('span', class_=lambda c: c and 'name' in c.lower() if c else False)
            for el in shop_els:
                text = el.get_text(strip=True)
                if text and len(text) > 1 and ('店' in text or '专区' in text or '旗舰' in text):
                    shop_name = text
                    break
            if not shop_name:
                # fallback: 找用户可见的最长连续文本
                for span in card.find_all('span'):
                    text = span.get_text(strip=True)
                    if text and ('旗舰店' in text or '自营' in text or '专卖店' in text or '专营店' in text):
                        shop_name = text
                        break

            # ── 是否为自营 ──
            is_self_operated = bool(card.find('img', alt='自营'))

            # ── 销量 ──
            sales_text = ''
            volume_els = card.find_all('span', class_=lambda c: c and 'volume' in c.lower() if c else False)
            for el in volume_els:
                text = el.get_text(strip=True)
                if '已售' in text or '万+' in text:
                    sales_text = text
                    break
            if not sales_text:
                # fallback: 文本包含 "已售" 的任意元素
                for el in card.find_all(['span', 'div']):
                    text = el.get_text(strip=True)
                    if '已售' in text:
                        sales_text = text
                        break

            review_count = _int_from_text(sales_text)

            # ── 评分/好评率 ──
            rating = 0.0
            # 先找 title 属性中的好评率（更可靠）
            for el in card.find_all(['span', 'div'], title=True):
                title_text = el.get('title', '')
                m = re.search(r'(\d+)%好评', title_text)
                if m:
                    rating = float(m.group(1))
                    break
            if rating == 0.0:
                # fallback: 找正文中的
                for el in card.find_all(['span', 'div']):
                    text = el.get_text(strip=True)
                    m = re.search(r'(\d+)%好评', text)
                    if m:
                        rating = float(m.group(1))
                        break

            # ── 是否为广告 ──
            is_ad = bool(card.find('div', class_=lambda c: c and 'ad' in c.lower() if c else False))
            if not is_ad:
                is_ad = bool(card.find(text='广告'))

            # ── 图片 URL ──
            image_url = ''
            img = card.find('img', class_=lambda c: c and 'img_' in c if c else False)
            if img:
                image_url = img.get('data-src') or img.get('src') or ''
            if not image_url:
                img = card.find('img')
                if img:
                    image_url = img.get('data-src') or img.get('src') or ''

            # ── 标签 ──
            tags = []
            for img_tag in card.find_all('img', alt=True):
                alt = img_tag['alt']
                if alt not in ('', '广告', 'JUMIA') and len(alt) < 20:
                    tags.append(alt)

            product = {
                'sku': sku,
                'title': title,
                'price_min': price_min,
                'price_max': price_max if price_max > price_min else 0.0,
                'shop_name': shop_name,
                'sales_text': sales_text,
                'review_count': review_count,
                'rating': rating,
                'is_ad': is_ad,
                'is_self_operated': is_self_operated,
                'tags': list(set(tags)),
                'image_url': image_url,
                'keyword': keyword,
            }
            products.append(product)

        except Exception as e:
            continue

    return products


def raw_to_unified(raw: list[dict], platform: str = "京东",
                   keyword: str = "") -> list:
    """将原始 dict 转为 UnifiedProduct"""
    from core.schema import UnifiedProduct

    results = []
    for item in raw:
        sku = item.get('sku', '')
        up = UnifiedProduct(
            platform=platform,
            product_id=sku,
            product_url=f"https://item.jd.com/{sku}.html" if sku else '',
            title=item.get('title', ''),
            price_min=item.get('price_min', 0.0),
            price_max=item.get('price_max', 0.0),
            shop_name=item.get('shop_name', ''),
            shop_type='自营' if item.get('is_self_operated') else '',
            sales_text=item.get('sales_text', ''),
            review_count=item.get('review_count', 0),
            rating=item.get('rating', 0.0),
            is_ad=item.get('is_ad', False),
            is_self_operated=item.get('is_self_operated', False),
            tags=item.get('tags', []),
            image_url=item.get('image_url', ''),
            raw_data=item,
        )
        results.append(up)

    return results

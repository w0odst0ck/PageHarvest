"""
京东搜索页解析器

支持两种页面格式：
1. re.jd.com/search (React SPA): 商品卡片为 <div data-sku="...">
2. list.jd.com/list.html (传统 SSR): 商品卡片为 <li class="gl-item" data-sku="...">

统一输出 UnifiedProduct 兼容的 dict。
"""

import re
from bs4 import BeautifulSoup, Tag
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


# ════════════════════════════════════════════════════════════════════════
#  主入口：自动检测页面类型并分派
# ════════════════════════════════════════════════════════════════════════

def parse_search_html(html: str, keyword: str) -> list[dict]:
    """
    解析京东搜索页 HTML，自动检测页面类型。

    支持：
      - re.jd.com/search SPA 页面（data-sku 在 div 上）
      - list.jd.com/list.html 传统页面（data-sku 在 li.gl-item 上）
      - search.jd.com/Search SPA 页面
    """
    soup = BeautifulSoup(html, 'html.parser')

    # 策略 1：找 div[data-sku] — SPA 模式 (re.jd.com / search.jd.com)
    products = _parse_spa_format(soup)
    if products:
        print(f"  [解析器] 检测到 SPA 格式: {len(products)} 个商品")
        return products

    # 策略 2：找 li.gl-item[data-sku] — 传统列表页 (list.jd.com)
    products = _parse_traditional_format(soup)
    if products:
        print(f"  [解析器] 检测到传统列表页: {len(products)} 个商品")
        return products

    # 策略 3：通用后备 — 任何带 data-sku 的元素
    products = _parse_generic_data_sku(soup)
    if products:
        print(f"  [解析器] 通用 data-sku 匹配: {len(products)} 个商品")
        return products

    print("  [解析器] 未找到商品，返回空列表")
    return []


# ════════════════════════════════════════════════════════════════════════
#  格式解析器
# ════════════════════════════════════════════════════════════════════════

def _parse_spa_format(soup: BeautifulSoup) -> list[dict]:
    """
    解析 React SPA 格式 (re.jd.com/search)

    特征：<div data-sku="12345"> ... </div>
    CSS 类名为 webpack hash，通过 data-sku 定位 + 结构特征启发式提取。
    """
    products = []
    card_wrappers = soup.find_all('div', attrs={'data-sku': True})

    if not card_wrappers:
        return []

    for card in card_wrappers:
        try:
            sku = card.get('data-sku', '')
            if not sku or sku == 'true':
                continue

            product = _extract_spa_card(card)
            if product:
                product['sku'] = sku
                product['keyword'] = ''
                products.append(product)
        except Exception:
            continue

    return products


def _parse_traditional_format(soup: BeautifulSoup) -> list[dict]:
    """
    解析传统列表页格式 (list.jd.com/list.html)

    特征：<li class="gl-item" data-sku="12345">
          内层结构：.p-img / .p-name / .p-price / .p-commit / .p-shop / .p-icons
    """
    products = []
    cards = soup.find_all('li', class_='gl-item', attrs={'data-sku': True})

    if not cards:
        return []

    for card in cards:
        try:
            sku = card.get('data-sku', '')
            if not sku or sku == 'true':
                continue

            product = _extract_traditional_card(card, soup)
            if product:
                product['sku'] = sku
                product['keyword'] = ''
                products.append(product)
        except Exception:
            continue

    return products


def _parse_generic_data_sku(soup: BeautifulSoup) -> list[dict]:
    """
    通用后备：查找任何带 data-sku 的元素。

    可能命中 search.jd.com 新版或其它 JD 子域名变体。
    """
    products = []
    cards = soup.find_all(attrs={'data-sku': True})

    if not cards:
        return []

    for card in cards:
        try:
            sku = card.get('data-sku', '')
            if not sku or sku == 'true':
                continue
            # 尝试 SPA 提取
            product = _extract_spa_card(card)
            if not product:
                product = _extract_traditional_card(Tag, soup) if False else {}
            if product:
                product['sku'] = sku
                product['keyword'] = ''
                products.append(product)
        except Exception:
            continue

    return products


# ════════════════════════════════════════════════════════════════════════
#  卡片字段提取
# ════════════════════════════════════════════════════════════════════════

def _extract_spa_card(card: Tag) -> Optional[dict]:
    """
    从 SPA 格式的卡片 div 中提取字段。

    re.jd.com/search 使用 webpack hash 类名，通过属性 + 文本启发式定位。
    """
    result = {}

    # ── 标题 ──
    result['title'] = _spa_extract_title(card)

    # ── 价格 ──
    price_min, price_max = _spa_extract_prices(card)
    result['price_min'] = price_min
    result['price_max'] = price_max

    # ── 店铺名 ──
    result['shop_name'] = _spa_extract_shop(card)

    # ── 自营 ──
    result['is_self_operated'] = bool(card.find('img', alt='自营'))

    # ── 销量/评价 ──
    sales_text, review_count = _spa_extract_sales(card)
    result['sales_text'] = sales_text
    result['review_count'] = review_count

    # ── 好评率 ──
    result['rating'] = _spa_extract_rating(card)

    # ── 广告 ──
    result['is_ad'] = _spa_check_ad(card)

    # ── 图片 ──
    result['image_url'] = _spa_extract_image(card)

    # ── 标签 ──
    result['tags'] = _spa_extract_tags(card)

    return result


def _extract_traditional_card(card: Tag, soup: BeautifulSoup) -> Optional[dict]:
    """
    从传统列表页的 li.gl-item 中提取字段。

    list.jd.com 使用语义化类名：.p-name, .p-price, .p-commit, .p-shop, .p-icons
    """
    result = {}

    # ── 标题 ──
    result['title'] = _trad_extract_title(card)

    # ── 价格 ──
    price_min, price_max = _trad_extract_prices(card)
    result['price_min'] = price_min
    result['price_max'] = price_max

    # ── 店铺名 ──
    result['shop_name'] = _trad_extract_shop(card)

    # ── 自营 ──
    result['is_self_operated'] = _trad_check_self_operated(card)

    # ── 销量/评价 ──
    sales_text, review_count = _trad_extract_sales(card)
    result['sales_text'] = sales_text
    result['review_count'] = review_count

    # ── 好评率 ──
    result['rating'] = _trad_extract_rating(card)

    # ── 广告 ──
    result['is_ad'] = _trad_check_ad(card)

    # ── 图片 ──
    result['image_url'] = _trad_extract_image(card)

    # ── 标签 ──
    result['tags'] = _trad_extract_tags(card)

    return result


# ════════════════════════════════════════════════════════════════════════
#  SPA 格式字段提取（启发式）
# ════════════════════════════════════════════════════════════════════════

def _spa_extract_title(card: Tag) -> str:
    """SPA 页面标题提取：优先 span[title]"""
    title_el = card.find('span', title=True)
    if title_el:
        return title_el.get('title', '')
    for span in card.find_all('span'):
        if span.get('title'):
            return span['title']
    return ''


def _spa_extract_prices(card: Tag) -> tuple:
    """SPA 页面价格提取"""
    all_prices = []
    for tag in card.find_all(['span', 'i', 'div']):
        text = tag.get_text(strip=True)
        m = re.search(r'¥([\d.]+)', text)
        if m:
            val = float(m.group(1))
            if val not in all_prices:
                all_prices.append(val)

    gray_prices = []
    for tag in card.find_all(
        class_=lambda c: c and 'gray' in c.lower() if c else False
    ):
        text = tag.get_text(strip=True)
        m = re.search(r'([\d.]+)', text)
        if m:
            gray_prices.append(float(m.group(1)))

    price_min = 0.0
    price_max = 0.0

    if all_prices:
        all_prices.sort()
        price_min = all_prices[0]
        if gray_prices:
            price_max = max(gray_prices)
        elif len(all_prices) > 1:
            price_max = max(all_prices)

    if price_min == 0.0:
        all_text = card.get_text()
        m = re.search(r'¥(\d+\.?\d*)', all_text)
        if m:
            price_min = float(m.group(1))

    return price_min, price_max


def _spa_extract_shop(card: Tag) -> str:
    """SPA 页面店铺名提取"""
    shop_els = card.find_all(
        'span', class_=lambda c: c and 'name' in c.lower() if c else False
    )
    for el in shop_els:
        text = el.get_text(strip=True)
        if text and len(text) > 1 and ('店' in text or '专区' in text or '旗舰' in text):
            return text
    for span in card.find_all('span'):
        text = span.get_text(strip=True)
        if text and ('旗舰店' in text or '自营' in text or '专卖店' in text or '专营店' in text):
            return text
    return ''


def _spa_extract_sales(card: Tag) -> tuple:
    """SPA 页面销量提取"""
    sales_text = ''
    volume_els = card.find_all(
        'span', class_=lambda c: c and 'volume' in c.lower() if c else False
    )
    for el in volume_els:
        text = el.get_text(strip=True)
        if '已售' in text or '万+' in text:
            sales_text = text
            break
    if not sales_text:
        for el in card.find_all(['span', 'div']):
            text = el.get_text(strip=True)
            if '已售' in text:
                sales_text = text
                break
    review_count = _int_from_text(sales_text)
    return sales_text, review_count


def _spa_extract_rating(card: Tag) -> float:
    """SPA 页面好评率提取"""
    for el in card.find_all(['span', 'div'], title=True):
        title_text = el.get('title', '')
        m = re.search(r'(\d+)%好评', title_text)
        if m:
            return float(m.group(1))
    for el in card.find_all(['span', 'div']):
        text = el.get_text(strip=True)
        m = re.search(r'(\d+)%好评', text)
        if m:
            return float(m.group(1))
    return 0.0


def _spa_check_ad(card: Tag) -> bool:
    """SPA 页面广告标记"""
    if card.find('div', class_=lambda c: c and 'ad' in c.lower() if c else False):
        return True
    if card.find(text='广告'):
        return True
    return False


def _spa_extract_image(card: Tag) -> str:
    """SPA 页面图片 URL"""
    img = card.find(
        'img', class_=lambda c: c and 'img_' in c if c else False
    )
    if img:
        return img.get('data-src') or img.get('src') or ''
    img = card.find('img')
    if img:
        return img.get('data-src') or img.get('src') or ''
    return ''


def _spa_extract_tags(card: Tag) -> list:
    """SPA 页面标签"""
    tags = []
    for img_tag in card.find_all('img', alt=True):
        alt = img_tag['alt']
        if alt and alt not in ('', '广告', 'JUMIA') and len(alt) < 20:
            tags.append(alt)
    return list(set(tags))


# ════════════════════════════════════════════════════════════════════════
#  传统列表页字段提取（语义化类名）
# ════════════════════════════════════════════════════════════════════════

def _trad_extract_title(card: Tag) -> str:
    """传统页标题提取：.p-name a[title]"""
    p_name = card.find('div', class_='p-name')
    if p_name:
        a = p_name.find('a', title=True)
        if a:
            return a.get('title', '')
        # fallback: 所有 a 标签的 title
        for a in p_name.find_all('a'):
            if a.get('title'):
                return a['title']
        # fallback: em 标签
        em = p_name.find('em')
        if em:
            return em.get_text(strip=True)
    # 全局搜索 card 中的 a[title]
    for a in card.find_all('a', title=True):
        t = a['title']
        if t and len(t) > 5:
            return t
    return ''


def _trad_extract_prices(card: Tag) -> tuple:
    """传统页价格提取：.p-price"""
    p_price = card.find('div', class_='p-price')
    if not p_price:
        return 0.0, 0.0

    prices = []
    for tag in p_price.find_all(['strong', 'i', 'span', 'em']):
        text = tag.get_text(strip=True)
        m = re.search(r'¥?([\d.]+)', text)
        if m:
            val = float(m.group(1))
            if val not in prices:
                prices.append(val)

    # 去掉划线价的元素（带 del / strike 的父级）
    del_prices = []
    for tag in p_price.find_all(['del', 's', 'strike']):
        text = tag.get_text(strip=True)
        m = re.search(r'([\d.]+)', text)
        if m:
            del_prices.append(float(m.group(1)))

    # 找 <i> 标签，通常是划线价
    i_prices = []
    for i_tag in p_price.find_all('i'):
        text = i_tag.get_text(strip=True)
        m = re.search(r'([\d.]+)', text)
        if m:
            i_prices.append(float(m.group(1)))

    if prices:
        prices.sort()
        price_min = prices[0]
        # 划线价：<i> 或 <del> 中的价格
        all_strikethrough = list(set(del_prices + i_prices))
        if all_strikethrough:
            price_max = max(all_strikethrough)
        elif len(prices) > 1:
            price_max = max(prices)
        else:
            price_max = 0.0
        return price_min, price_max

    return 0.0, 0.0


def _trad_extract_shop(card: Tag) -> str:
    """传统页店铺名提取：.p-shop"""
    p_shop = card.find('div', class_='p-shop')
    if p_shop:
        a = p_shop.find('a')
        if a:
            text = a.get_text(strip=True)
            if text:
                return text
        # fallback span
        for span in p_shop.find_all('span'):
            text = span.get_text(strip=True)
            if text and len(text) > 1:
                return text
    return ''


def _trad_check_self_operated(card: Tag) -> bool:
    """传统页自营检测：.p-icons 包含'自营'"""
    p_icons = card.find('div', class_='p-icons')
    if p_icons:
        for span in p_icons.find_all('span'):
            if span.get_text(strip=True) == '自营':
                return True
        for img in p_icons.find_all('img'):
            alt = img.get('alt', '')
            if '自营' in alt:
                return True
    return False


def _trad_extract_sales(card: Tag) -> tuple:
    """传统页销量提取：.p-commit"""
    sales_text = ''
    p_commit = card.find('div', class_='p-commit')
    if p_commit:
        # 评价数在 <a> 中
        a = p_commit.find('a')
        if a:
            text = a.get_text(strip=True)
            # 可能是 "1234条评价" 或纯数字
            if text:
                # 去掉"条评价"后缀
                text = re.sub(r'条评价.*', '', text)
                sales_text = text
    review_count = _int_from_text(sales_text)
    # 如果没提取到销量，看整个 card 中有没有"已售"
    if not sales_text:
        for el in card.find_all(['span', 'div']):
            text = el.get_text(strip=True)
            if '已售' in text:
                sales_text = text
                review_count = _int_from_text(sales_text)
                break
    return sales_text, review_count


def _trad_extract_rating(card: Tag) -> float:
    """传统页好评率提取"""
    for el in card.find_all(['span', 'div'], title=True):
        m = re.search(r'(\d+)%', el.get('title', ''))
        if m:
            return float(m.group(1))
    for el in card.find_all(['span', 'div']):
        m = re.search(r'(\d+)%好评', el.get_text(strip=True))
        if m:
            return float(m.group(1))
    return 0.0


def _trad_check_ad(card: Tag) -> bool:
    """传统页广告检测"""
    if card.find('div', class_='p-ad'):
        return True
    if card.find(text='广告'):
        return True
    return False


def _trad_extract_image(card: Tag) -> str:
    """传统页图片提取：.p-img"""
    p_img = card.find('div', class_='p-img')
    if p_img:
        img = p_img.find('img')
        if img:
            return img.get('data-src') or img.get('src') or ''
    return ''


def _trad_extract_tags(card: Tag) -> list:
    """传统页标签：.p-icons 中的 span 文字"""
    tags = []
    p_icons = card.find('div', class_='p-icons')
    if p_icons:
        for span in p_icons.find_all('span'):
            text = span.get_text(strip=True)
            if text and text not in ('自营',):
                tags.append(text)
        for img in p_icons.find_all('img', alt=True):
            alt = img['alt']
            if alt and alt not in ('自营',) and len(alt) < 20:
                tags.append(alt)
    return list(set(tags))


# ════════════════════════════════════════════════════════════════════════
#  统一输出
# ════════════════════════════════════════════════════════════════════════

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

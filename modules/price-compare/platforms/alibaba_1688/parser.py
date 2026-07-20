"""
1688 HTML 解析模块

从 Playwright 获取的 SSR HTML 中提取结构化商品数据。
选择器兼容 1688 搜索页当前版本。
"""

import re
import logging
from typing import Optional

from . import config
from core.logger import get_logger

log = get_logger()

# ── 商品卡片选择器（按优先级） ──
CARD_SELECTORS = [
    'div.offer-list-item-wrap',           # PC 新版
    'div[class*="offer-list-item"]',       # PC 兼容
    'div[class*="list-item"]',            # 通用
    'div[data-traceid]',                  # data 属性定位
]

# ── 字段提取器（每个字段多个选择器降级） ──
FIELD_SELECTORS = {
    "title": [
        ('.title a', 'text'),
        ('h4 a', 'text'),
        ('a[class*="title"]', 'text'),
        ('div[class*="title"] a', 'text'),
    ],
    "price": [
        ('.price', 'text'),
        ('span[class*="price"]', 'text'),
        ('div[class*="price"]', 'text'),
        ('strong[class*="price"]', 'text'),
    ],
    "sales": [
        ('.sale', 'text'),
        ('span[class*="sale"]', 'text'),
        ('div[class*="sale"]', 'text'),
        ('span[class*="deal"]', 'text'),
    ],
    "link": [
        ('a[href*="offer"]', 'href'),
        ('a[href*="detail"]', 'href'),
        ('.title a', 'href'),
    ],
    "image": [
        ('img[data-sf-original-src]', 'data-sf-original-src'),
        ('img[src]', 'src'),
        ('img[data-lazyload]', 'data-lazyload'),
    ],
    "shop": [
        ('.shop-name a', 'text'),
        ('a[class*="shop"]', 'text'),
        ('span[class*="shop"]', 'text'),
    ],
}


def parse_search(html: str) -> list[dict]:
    """
    从搜索页 HTML 提取商品列表。

    Args:
        html: 搜索页 HTML

    Returns:
        [{title, price_min, price_max, unit, sales, link, image, shop}, ...]
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, 'html.parser')
    products = []

    # 定位商品卡片
    cards = None
    for selector in CARD_SELECTORS:
        cards = soup.select(selector)
        if cards:
            break

    if not cards:
        log.warning(config.PLATFORM_NAME, "未找到商品卡片")
        return []

    for card in cards:
        try:
            product = _extract_search_item(card)
            if product["title"]:
                products.append(product)
        except Exception:
            continue

    return products


def _extract_search_item(card) -> dict:
    """从单张商品卡片提取信息"""
    result = {
        "title": "",
        "price_min": 0.0,
        "price_max": 0.0,
        "unit": "",
        "sales": "",
        "link": "",
        "image": "",
        "shop": "",
    }

    # 标题
    for selector, attr in FIELD_SELECTORS["title"]:
        el = card.select_one(selector)
        if el:
            text = el.get_text(strip=True)
            if text:
                result["title"] = text
                break

    # 价格
    for selector, attr in FIELD_SELECTORS["price"]:
        el = card.select_one(selector)
        if el:
            text = el.get_text(strip=True)
            text = re.sub(r'[¥￥,\s]', '', text)
            prices = re.findall(r'[\d.]+', text)
            if prices:
                values = [float(p) for p in prices]
                result["price_min"] = min(values)
                result["price_max"] = max(values)
            break

    # 销量
    for selector, attr in FIELD_SELECTORS["sales"]:
        el = card.select_one(selector)
        if el:
            text = el.get_text(strip=True)
            if text:
                result["sales"] = text
                break

    # 链接
    for selector, attr in FIELD_SELECTORS["link"]:
        el = card.select_one(selector)
        if el:
            href = el.get("href", "")
            if href:
                if href.startswith("//"):
                    href = "https:" + href
                result["link"] = href
                break

    # 图片
    for selector, attr in FIELD_SELECTORS["image"]:
        el = card.select_one(selector)
        if el:
            src = el.get(attr, "")
            if src:
                if src.startswith("//"):
                    src = "https:" + src
                result["image"] = src
                break

    # 店铺名
    for selector, attr in FIELD_SELECTORS["shop"]:
        el = card.select_one(selector)
        if el:
            text = el.get_text(strip=True)
            if text:
                result["shop"] = text
                break

    return result


def extract_key_info(product: dict) -> dict:
    """提取比价关键信息

    Args:
        product: parse_search() 返回的单条数据

    Returns:
        {"title": str, "price": float, "shop": str, "link": str}
    """
    price = product.get("price_min", 0) or product.get("price_max", 0)
    return {
        "title": product.get("title", ""),
        "price": price,
        "shop": product.get("shop", ""),
        "link": product.get("link", ""),
    }

"""
震坤行 — 搜索页解析器

解析 SSR 渲染后的搜索页 HTML，提取商品列表。
数据来源：
  1. window.__INITIAL_DATA__ 中的结构化 JSON
  2. DOM 中的价格元素（JSON 中 sellingPrice 为空时）
"""

import re
import json
import logging
from typing import Optional
from bs4 import BeautifulSoup

from . import config
from core.logger import get_logger

log = get_logger()

# ═══════════════════════════════════════════════════════════════
#  解析入口
# ═══════════════════════════════════════════════════════════════

def parse(html: str) -> list[dict]:
    """
    解析 ZKH 搜索页 HTML，返回候选商品列表。

    策略：
      1. 从 window.__INITIAL_DATA__ JSON 中提取结构化数据
      2. 如 JSON 中无价格，从 DOM 中提取
      3. 返回统一格式的候选列表

    Returns:
        [
            {
                "title": "敏华 应急灯 ...",
                "price": 46.9,
                "url": "https://www.zkh.com/product/xxx.html",
                "shop": "",             # ZKH 自营，无店铺概念
                "sku": "AA5186623",
                "brand": "MANVA/敏华电工",
                "model": "M-ZFZD-E5W3004",
                "confidence_hint": "",
            }
        ]
    """
    candidates = []

    # 1. 从 JSON 提取
    json_items = _parse_initial_data(html)

    if json_items:
        log.debug(config.PLATFORM_NAME, f"从 SSR JSON 提取到 {len(json_items)} 条")
        # 同时从 DOM 提取价格映射
        price_map = _parse_dom_prices(html)

        for item in json_items:
            candidate = _normalize_item(item, price_map)
            if candidate:
                candidates.append(candidate)
    else:
        # 2. JSON 提取失败，纯 DOM 解析
        log.debug(config.PLATFORM_NAME, "JSON 提取失败，尝试 DOM 解析")
        candidates = _parse_dom_only(html)

    log.debug(config.PLATFORM_NAME, f"解析到 {len(candidates)} 个候选商品")
    return candidates


# ═══════════════════════════════════════════════════════════════
#  SSR JSON 解析
# ═══════════════════════════════════════════════════════════════

def _parse_initial_data(html: str) -> list[dict]:
    """从 window.__INITIAL_DATA__ 提取商品列表"""
    # 尝试多种可能的数据路径
    patterns = [
        # 标准 SSR 格式
        r'window\.__INITIAL_DATA__\s*=\s*(\{.*?\});',
        # 可能带有 JSON.parse
        r'window\.__INITIAL_DATA__\s*=\s*JSON\.parse\(\s*[\'"](.+?)[\'"]\s*\)',
        # 直接赋值
        r'__INITIAL_DATA__\s*=\s*(\{.*?\});',
        # Nuxt 格式
        r'window\.__NUXT__\s*=\s*(\{.*?\});',
    ]

    for pattern in patterns:
        m = re.search(pattern, html, re.DOTALL)
        if m:
            try:
                raw = m.group(1)
                data = json.loads(raw)
                items = _find_product_list(data)
                if items:
                    return items
            except (json.JSONDecodeError, Exception):
                continue

    # 最后尝试：找任何包含 productList 的 JSON 块
    for m in re.finditer(r'\{[^{}]*"productList"[^{}]*\}', html):
        try:
            data = json.loads(m.group())
            items = _find_product_list(data)
            if items:
                return items
        except Exception:
            continue

    return []


def _find_product_list(data) -> list[dict]:
    """递归查找商品列表"""
    if isinstance(data, dict):
        for key in ["productList", "list", "products", "items", "result"]:
            val = data.get(key)
            if isinstance(val, list) and len(val) > 0:
                # 检查这确实是一个商品列表（有标题/价格字段）
                if val[0].get("proSkuProductName") or val[0].get("title") or val[0].get("name"):
                    return val
            if isinstance(val, dict):
                result = _find_product_list(val)
                if result:
                    return result
    return []


# ═══════════════════════════════════════════════════════════════
#  DOM 价格提取
# ═══════════════════════════════════════════════════════════════

def _parse_dom_prices(html: str) -> dict:
    """
    从 DOM 中提取价格，按商品索引映射。

    ZKH 的 SSR JSON 中 sellingPrice 可能为空，
    但渲染后的 DOM 里有具体价格。
    """
    soup = BeautifulSoup(html, "html.parser")
    price_map = {}

    price_elements = soup.select(".sku-price-wrap-new")
    for idx, el in enumerate(price_elements):
        integer = el.select_one(".integer")
        decimal = el.select_one(".decimal")
        if integer and decimal:
            try:
                price = float(f"{integer.get_text(strip=True)}.{decimal.get_text(strip=True)}")
                price_map[idx] = price
            except ValueError:
                continue

    return price_map


# ═══════════════════════════════════════════════════════════════
#  标准化
# ═══════════════════════════════════════════════════════════════

def _normalize_item(item: dict, price_map: dict = None, idx: int = 0) -> Optional[dict]:
    """将 ZKH 商品数据标准化为统一格式"""
    title = (item.get("proSkuProductName") or
             item.get("title") or
             item.get("name") or "").strip()
    if not title:
        return None

    # 链接
    sku_no = item.get("proSkuNo") or item.get("skuNo") or item.get("id") or ""
    if sku_no:
        url = f"https://www.zkh.com/product/{sku_no}.html"
    else:
        url = ""

    # 价格
    price = _extract_price(item, price_map, idx)

    # 品牌
    brand = (item.get("proBrandName") or
             item.get("brand") or
             item.get("brandName") or "").strip()

    # 型号
    model = (item.get("proMaterialNo") or
             item.get("model") or
             item.get("materialNo") or "").strip()

    return {
        "title": title,
        "price": price,
        "url": url,
        "shop": "震坤行自营",
        "sku": sku_no,
        "brand": brand,
        "model": model,
        "confidence_hint": f"{brand} {model}" if brand and model else title[:40],
    }


def _extract_price(item: dict, price_map: dict = None, idx: int = 0) -> Optional[float]:
    """多策略提取价格"""
    # 1. 从 JSON 的 sellingPrice
    sp = item.get("sellingPrice") or item.get("price") or item.get("salePrice") or item.get("showPrice")
    if sp is not None:
        try:
            return float(sp)
        except (ValueError, TypeError):
            pass

    # 2. 从 JSON 的 priceInfo
    pi = item.get("priceInfo") or {}
    if isinstance(pi, dict):
        for k in ["price", "sellingPrice", "showPrice", "salePrice"]:
            v = pi.get(k)
            if v:
                try:
                    return float(v)
                except (ValueError, TypeError):
                    pass

    # 3. 从 DOM 价格映射
    if price_map and idx in price_map:
        return price_map[idx]

    # 4. 从 JSON 的 priceRange
    pr = item.get("priceRange") or {}
    if isinstance(pr, dict):
        for k in ["minPrice", "maxPrice", "price"]:
            v = pr.get(k)
            if v:
                try:
                    return float(v)
                except (ValueError, TypeError):
                    pass

    return None


# ═══════════════════════════════════════════════════════════════
#  DOM 兜底解析（JSON 提取失败时用）
# ═══════════════════════════════════════════════════════════════

def _parse_dom_only(html: str) -> list[dict]:
    """纯 DOM 解析（备选方案）"""
    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    # 尝试多种商品容器
    for container_sel in [".product-item", "[class*='product-item']",
                          ".search-result-item", "[class*='search-item']",
                          ".sku-item", "[class*='sku-item']",
                          ".goods-item", ".item"]:
        containers = soup.select(container_sel)
        if len(containers) >= 2:
            break
    else:
        containers = []

    for container in containers:
        title_el = container.select_one("a[title], [class*='title'] a, [class*='name'] a, a")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        if href and not href.startswith("http"):
            href = f"https://www.zkh.com{href}"

        price = None
        price_el = container.select_one(".sku-price-wrap-new .integer, [class*='price'], [class*='money']")
        if price_el:
            integer = price_el.select_one(".integer")
            decimal = price_el.select_one(".decimal")
            if integer and decimal:
                try:
                    price = float(f"{integer.get_text(strip=True)}.{decimal.get_text(strip=True)}")
                except ValueError:
                    pass
            else:
                try:
                    price = float(re.search(r'[\d.]+', price_el.get_text(strip=True)).group())
                except Exception:
                    pass

        candidates.append({
            "title": title,
            "price": price,
            "url": href,
            "shop": "震坤行自营",
            "sku": "",
            "brand": "",
            "model": "",
            "confidence_hint": title[:40],
        })

    return candidates

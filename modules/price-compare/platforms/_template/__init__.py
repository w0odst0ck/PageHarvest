"""新平台模板 —— 拷贝此目录创建新平台"""

from . import crawler, parser, matcher
from .config import PLATFORM_NAME


def run(products: list[dict]) -> dict:
    """
    平台入口函数。所有平台必须实现此接口。

    Args:
        products: loader 输出的标准商品列表

    Returns:
        {
            "platform": PLATFORM_NAME,
            "results": [
                {
                    "sku": "...",
                    "price": 0.0,
                    "title": "...",
                    "url": "...",
                    "shop": "...",
                    "confidence": "高/中/低",
                    "matched": True,
                }
            ],
            "unmatched": [
                {"sku": "...", "name": "...", "brand": "...", "model": "...", "reason": "..."}
            ],
            "errors": [...]
        }
    """
    results = []
    unmatched = []
    errors = []

    for prod in products:
        keyword = _build_keyword(prod)
        if not keyword:
            unmatched.append({**prod, 'reason': '无法生成搜索词'})
            continue

        # 1. 搜索
        html = crawler.search(keyword)
        if html is None:
            errors.append({'sku': prod.get('sku'), 'reason': '搜索失败'})
            continue

        # 2. 解析
        candidates = parser.parse(html)

        # 3. 匹配
        match_result = matcher.match(prod, candidates)

        if match_result and match_result.get('matched'):
            results.append(match_result)
        else:
            unmatched.append({
                'sku': prod.get('sku', ''),
                'name': prod.get('name', ''),
                'brand': prod.get('brand', ''),
                'model': prod.get('model', ''),
                'reason': match_result.get('reason', '未匹配') if match_result else '未匹配',
            })

    return {
        'platform': PLATFORM_NAME,
        'results': results,
        'unmatched': unmatched,
        'errors': errors,
    }


def _build_keyword(prod: dict) -> str:
    """根据商品信息生成搜索关键词"""
    brand = (prod.get('brand') or '').strip()
    model = (prod.get('model') or '').strip()
    if brand and model:
        return f"{brand} {model}"
    if brand:
        return brand
    return ''

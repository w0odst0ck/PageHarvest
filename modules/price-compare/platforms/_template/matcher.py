"""商品匹配模块 —— 搜索结果与询价商品的匹配逻辑"""

from core.logger import get_logger

log = get_logger()


def match(target: dict, candidates: list[dict]) -> dict | None:
    """
    从搜索结果中匹配目标商品

    Args:
        target: {"sku": "...", "brand": "敏华", "model": "M-ZFZD-E5W3004", "name": "..."}
        candidates: parser 解析出的候选商品列表

    Returns:
        匹配成功: {"sku": "...", "price": 30.5, "title": "...", "url": "...",
                    "shop": "...", "confidence": "高/中/低", "matched": True}
        匹配失败: {"sku": "...", "matched": False, "reason": "..."}
        无可匹配: None
    """
    brand = (target.get('brand') or '').strip().lower()
    model = (target.get('model') or '').strip().lower()

    if not brand:
        return None

    best = None
    best_score = 0

    for c in candidates:
        title = (c.get('title') or '').strip().lower()

        score = 0
        if brand and brand in title:
            score += 50
        if model and model in title:
            score += 50
        elif model and any(part in title for part in model.split() if len(part) > 2):
            score += 30

        if score > best_score:
            best_score = score
            best = c

    if best and best_score >= 80:
        return {
            'sku': target.get('sku', ''),
            'price': best.get('price', 0),
            'title': best.get('title', ''),
            'url': best.get('url', ''),
            'shop': best.get('shop', ''),
            'confidence': '高',
            'matched': True,
        }
    elif best and best_score >= 50:
        return {
            'sku': target.get('sku', ''),
            'price': best.get('price', 0),
            'title': best.get('title', ''),
            'url': best.get('url', ''),
            'shop': best.get('shop', ''),
            'confidence': '中',
            'matched': True,
        }
    elif best:
        return {
            'sku': target.get('sku', ''),
            'price': best.get('price', 0),
            'title': best.get('title', ''),
            'url': best.get('url', ''),
            'shop': best.get('shop', ''),
            'confidence': '低',
            'matched': True,
        }

    return {'sku': target.get('sku', ''), 'matched': False, 'reason': '搜索无结果'}

"""震坤行平台模块"""

from . import crawler, parser, matcher
from .config import PLATFORM_NAME
from core.logger import get_logger

log = get_logger()


def run(products: list[dict]) -> dict:
    """
    在震坤行上搜索并匹配所有商品。

    使用 Playwright 直接导航到搜索页（不经过主页交互），
    从 SSR JSON 中提取结构化数据。
    """
    results = []
    unmatched = []
    errors = []

    for prod in products:
        keyword = _build_keyword(prod)
        if not keyword:
            unmatched.append({
                'sku': prod.get('sku', ''),
                'name': prod.get('name', ''),
                'brand': prod.get('brand', ''),
                'model': prod.get('model', ''),
                'reason': '无法生成搜索词',
            })
            continue

        # 1. 搜索
        log.info(PLATFORM_NAME, f"搜索: {keyword}")
        html = crawler.search(keyword)
        if html is None:
            errors.append({'sku': prod.get('sku'), 'reason': '搜索失败'})
            continue

        # 2. 解析
        candidates = parser.parse(html)
        if not candidates:
            unmatched.append({
                'sku': prod.get('sku', ''),
                'name': prod.get('name', ''),
                'brand': prod.get('brand', ''),
                'model': prod.get('model', ''),
                'reason': '搜索无结果',
            })
            continue

        # 3. 匹配
        match_result = matcher.match(prod, candidates)

        if match_result and match_result.get('matched'):
            results.append(match_result)
            log.info(PLATFORM_NAME,
                     f"匹配: {prod.get('sku')} → {match_result.get('confidence')}")
        else:
            reason = match_result.get('reason', '未匹配') if match_result else '未匹配'
            unmatched.append({
                'sku': prod.get('sku', ''),
                'name': prod.get('name', ''),
                'brand': prod.get('brand', ''),
                'model': prod.get('model', ''),
                'reason': reason,
            })
            log.info(PLATFORM_NAME,
                     f"未匹配: {prod.get('sku')} → {reason}")

    log.info(PLATFORM_NAME,
             f"完成: 匹配 {len(results)}, 未匹配 {len(unmatched)}, 错误 {len(errors)}")
    return {
        'platform': PLATFORM_NAME,
        'results': results,
        'unmatched': unmatched,
        'errors': errors,
    }


def _build_keyword(prod: dict) -> str:
    """生成搜索关键词"""
    brand = (prod.get('brand') or '').strip()
    model = (prod.get('model') or '').strip()
    name = (prod.get('name') or '').strip()

    if brand and model:
        return f"{brand} {model}"
    if brand:
        return brand
    if model:
        return model
    if name:
        return name[:30]
    return ''

"""请求模块 —— 负责搜索请求和反爬策略"""

import requests
from core.utils import (
    random_ua, random_referrer, adaptive_delay, check_blocked,
    exponential_retry, load_cookie, shuffle_products
)
from core.logger import get_logger
from . import config

log = get_logger()


def search(keyword: str, tracker=None) -> str | None:
    """
    搜索关键词，返回 HTML

    Args:
        keyword: 搜索关键词，如 "敏华 M-ZFZD-E5W3004"
        tracker: RequestTracker 实例（用于自适应延时）

    Returns:
        成功: 搜索结果页 HTML 字符串
        被拦截: 抛出异常
        失败: None
    """
    log.debug(config.PLATFORM_NAME, f"搜索: {keyword}")

    # 1. 构建请求
    url = config.SEARCH_URL.format(keyword=keyword)
    ua = random_ua()
    referer = random_referrer(config.PLATFORM_NAME)
    headers = {
        **config.HEADERS,
        'User-Agent': ua,
        'Referer': referer,
    }
    cookies = load_cookie(config.COOKIE_FILE)

    # 2. 自适应延时
    adaptive_delay()

    # 3. 发送请求（带重试）
    def _do_request():
        resp = requests.get(
            url,
            headers=headers,
            cookies=cookies if cookies else None,
            timeout=config.TIMEOUT,
        )
        resp.raise_for_status()
        html = resp.text

        # 4. 检测是否被风控拦截
        blocked = check_blocked(html, config.BLOCK_KEYWORDS)
        if blocked:
            log.warning(config.PLATFORM_NAME,
                        f"被风控拦截: {keyword} → 触发关键词: {blocked}")
            raise RuntimeError(f"blocked: {blocked}")

        return html

    success, result, error = exponential_retry(
        _do_request,
        retry_delays=[3, 8, 20],
    )

    if not success:
        log.error(config.PLATFORM_NAME, f"搜索失败: {keyword} → {error}")
        return None

    return result

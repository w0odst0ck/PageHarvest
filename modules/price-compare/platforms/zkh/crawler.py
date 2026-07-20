"""
震坤行 — 爬虫模块

直接 Playwright 导航到搜索页，获取 SSR HTML。
不经过主页交互，避免 WAF。
"""

from core.browser import BrowserManager
from . import config
from core.logger import get_logger

log = get_logger()


def search(keyword: str) -> str | None:
    """
    搜索关键词，返回 SSR 渲染后的 HTML。

    使用 Playwright 直接导航到搜索页 URL，不需要任何交互。
    """
    url = config.SEARCH_URL.format(keyword=keyword)
    log.debug(config.PLATFORM_NAME, f"搜索: {keyword}")

    with BrowserManager(headless=True) as browser:
        # 加载搜索页（直接导航，不经过主页）
        result = browser.search_render(
            url=url,
            platform="zkh",
            wait_timeout=20,
            stealth=True,
        )

        if result.get("blocked"):
            log.warning(config.PLATFORM_NAME,
                        f"搜索被拦: {result['blocked']}")
            return None

        if result["success"]:
            log.info(config.PLATFORM_NAME, f"搜索成功: {len(result['html'])} 字节")
            return result["html"]

        log.error(config.PLATFORM_NAME,
                  f"搜索失败: {result.get('error', '未知')}")
        return None

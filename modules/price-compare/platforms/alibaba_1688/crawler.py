"""
1688 — 爬虫模块

使用 Playwright 搜索 1688，返回 SSR HTML。
不走 requests，避免被 x5sec 风控拦截。

策略：
  1. 直接导航到搜索 URL（不经过主页交互）
  2. 用 STEALTH_JS 抹掉 Playwright 特征
  3. Cookie 持久化：首次 headed 登录 → 后续 headless
  4. 翻页通过循环构造 URL page 参数

用法：
    from platforms.alibaba_1688.crawler import search

    html = search("敏华 M-ZFZD-E5W3004")
    if html:
        # 传给 parser 解析
        ...
"""

import time
import logging
from pathlib import Path

from core.browser import BrowserManager
from lib.stealth import STEALTH_JS
from . import config
from core.logger import get_logger

log = get_logger()

# 搜索 URL 模板
SEARCH_URL_TEMPLATE = (
    "https://s.1688.com/selloffer/offer_search.htm"
    "?keywords={keyword}&page={page}"
)

# 登录页 URL（用于 Cookie 持久化）
LOGIN_URL = "https://login.1688.com/"
CHECK_URL = "https://s.1688.com/"

# 翻页空页判断（1688 每页最多 50 条）
MAX_PER_PAGE = 50


def search(keyword: str, pages: int = 3) -> list[dict] | None:
    """
    搜索关键词，返回多页采集结果。

    Args:
        keyword: 搜索关键词
        pages: 搜索页数

    Returns:
        成功: [{"html": str, "page": 1}, ...]
        失败: None
    """
    log.debug(config.PLATFORM_NAME, f"搜索: {keyword}")

    results = []

    with BrowserManager(headless=True, login_url=LOGIN_URL) as bm:
        # ── Cookie 检查 ──
        if not bm.cookie_path.exists():
            log.warning(config.PLATFORM_NAME,
                        "Cookie 不存在，请在浏览器手动登录 1688")
            bm.restart(headless=False)
            bm.wait_for_login()
            bm.restart(headless=True)

        # ── Cookie 有效性检查 ──
        if bm.cookie_path.exists() and not bm.check_login(check_url=CHECK_URL):
            log.warning(config.PLATFORM_NAME, "Cookie 已过期，重新登录")
            bm.delete_cookies()
            bm.restart(headless=False)
            bm.wait_for_login(timeout_s=300)

        # ── 搜多页 ──
        for page_num in range(1, pages + 1):
            url = SEARCH_URL_TEMPLATE.format(
                keyword=keyword,
                page=page_num
            )

            try:
                # 使用 "domcontentloaded" + sleep 代替 "networkidle"
                # 1688 页面有长连接，"networkidle" 会超时
                page = bm.new_page(url, wait_until="domcontentloaded")
                time.sleep(3)  # 等 JS 渲染商品卡片

                # 检查是否被风控拦截
                html = page.content()
                blocked = _check_blocked(html)
                if blocked:
                    log.warning(config.PLATFORM_NAME,
                                f"第 {page_num} 页被拦截: {blocked}")
                    page.close()
                    # 如果第一页就被拦，整体失败
                    if page_num == 1:
                        return None
                    break

                # 检查是否有商品
                card_count = _count_cards(html)
                if card_count == 0:
                    log.info(config.PLATFORM_NAME,
                             f"第 {page_num} 页无商品，翻页结束")
                    page.close()
                    break

                log.info(config.PLATFORM_NAME,
                         f"第 {page_num} 页: {card_count} 个商品")
                results.append({"html": html, "page": page_num})
                page.close()

            except Exception as e:
                log.warning(config.PLATFORM_NAME,
                            f"第 {page_num} 页采集失败: {e}")
                # 单页失败不影响其他页
                continue

    if not results:
        return None

    return results


def search_single(keyword: str) -> str | None:
    """
    搜索关键词，返回第一页 HTML（兼容旧 API）。

    用法同 zkh/crawler.py 的 search():
        html = search("关键词")
        if html: parse(html)
    """
    results = search(keyword, pages=1)
    if not results:
        return None
    return results[0]["html"]


def _check_blocked(html: str) -> str | None:
    """检测是否被风控拦截"""
    if not html or len(html) < 500:
        return "空页面/页面太短"

    text = html.lower()
    keywords = [
        "验证码", "滑块", "人机验证", "captcha", "verify",
        "访问受限", "请求太频繁", "身份验证",
        "很抱歉", "访问出错", "系统检测到",
        "请滑动", "拖动滑块", "安全验证",
        "x5sec",
    ]
    for kw in keywords:
        if kw.lower() in text:
            return kw
    return None


def _count_cards(html: str) -> int:
    """估算搜索页商品数量"""
    # 1688 搜索页商品容器特征
    import re
    patterns = [
        r'class="[^"]*offer-list-item[^"]*"',
        r'data-traceid',
        r'class="[^"]*title[^"]*"[^>]*>',
    ]
    for p in patterns:
        count = len(re.findall(p, html))
        if count > 0:
            return count
    return 0

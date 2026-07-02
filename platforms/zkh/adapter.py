"""
震坤行 (zkh.com) 平台适配器
"""
import re
import urllib.request
from typing import Optional
from urllib.parse import quote

from core.schema import UnifiedProduct, UnifiedDetail
from core.registry import register
from platforms.base import PlatformAdapter
from .search_parser import parse_search_html, raw_to_unified


@register("震坤行")
class ZhenKunHangAdapter(PlatformAdapter):
    """震坤行平台适配器"""

    @property
    def platform_name(self) -> str:
        return "震坤行"

    # ── URL 模板 ──

    def search_url(self, keyword: str, page: int = 1) -> str:
        params = quote(keyword, safe='')
        return f"https://www.zkh.com/search.html?keywords={params}&page={page}"

    def product_url(self, product_id: str) -> str:
        return f"https://www.zkh.com/item/{product_id}.html"

    # ── 采集 ──

    def collect_search(self, keyword: str, page: int = 1) -> str:
        url = self.search_url(keyword, page)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode('utf-8', errors='replace')

    def collect_detail(self, product_id: str) -> str:
        url = self.product_url(product_id)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
            }
        )
        with urllib.request.urlopen(req) as resp:
            return resp.read().decode('utf-8', errors='replace')

    # ── 解析 ──

    def parse_search(self, html: str, keyword: str) -> list[UnifiedProduct]:
        # 检测 WAF 拦截
        if 'aliyun_waf' in html or len(html) < 20000:
            # WAF 页面或内容过短，无法解析
            return []
        return raw_to_unified(parse_search_html(html, keyword))

    def parse_detail(self, html: str) -> Optional[UnifiedDetail]:
        return None

"""
京东适配器（搜索页 + 详情页）
"""

import os, requests, time, logging
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

from core.schema import UnifiedProduct, UnifiedDetail
from platforms.base import PlatformAdapter
from core.registry import register
from .search_parser import parse_search_html, raw_to_unified
from .detail_parser import parse_detail as parse_jd_detail, to_unified_detail


@register("京东")
class JDAdapter(PlatformAdapter):
    """京东平台适配器"""

    @property
    def platform_name(self) -> str:
        return "京东"

    # ── URL 模板 ──
    # ⚠ 2026年更新: search.jd.com 已废弃
    # 新搜索地址: re.jd.com/search?keyword=XXX&page=N
    # （页面含 JSON 商品数据，结构与旧版不同）

    def search_url(self, keyword: str, page: int = 1) -> str:
        return (
            f"https://re.jd.com/search"
            f"?keyword={quote(keyword)}"
            f"&page={page}"
        )

    def product_url(self, product_id: str) -> str:
        return f"https://item.jd.com/{product_id}.html"

    # ── 采集 ──

    def collect_search(self, keyword: str, page: int = 1) -> str:
        """
        采集京东搜索页 HTML。

        ⚠ 在线采集不适用：京东搜索页是 React SPA，requests 只能拿到 SPA 壳，
           不含渲染后的商品数据。

        正确方式：浏览器打开 search.jd.com/Search?keyword=xxx →
                  滚动到商品显示完毕 → 右键另存为 HTML（渲染后完整的）
        """
        headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        resp = requests.get(self.search_url(keyword, page), headers=headers, timeout=30)
        resp.encoding = 'utf-8'
        return resp.text  # 注意：这是 SPA 壳 HTML，不含商品数据

    def collect_detail(self, product_id: str) -> str:
        """
        采集京东详情页 HTML。

        ⚠ 在线采集不适用：京东详情页信息分布在多个异步接口中，
           requests 拿到的 HTML 不含渲染后的完整数据。

        正确方式：浏览器打开 item.jd.com/{product_id}.html →
                  等待页面完全加载 → 右键另存为 HTML
        """
        headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36'),
        }
        resp = requests.get(self.product_url(product_id), headers=headers, timeout=30)
        resp.encoding = 'utf-8'
        return resp.text  # 注意：是未渲染的原始 HTML

    # ── 解析 ──

    def parse_search(self, html: str, keyword: str) -> list[UnifiedProduct]:
        """
        解析京东搜索页 HTML。
        接收浏览器保存的渲染后 HTML（含 data-sku 的商品卡片）。
        """
        raw = parse_search_html(html, keyword)
        return raw_to_unified(raw, platform="京东", keyword=keyword)

    def parse_detail(self, html: str) -> Optional[UnifiedDetail]:
        """
        京东详情页解析，使用 detail_parser 模块。
        """
        try:
            jd = parse_jd_detail(html)
            unified_dict = to_unified_detail(jd)
            # 填充 product_url
            if jd.product_id:
                unified_dict['product_url'] = self.product_url(jd.product_id)
            return UnifiedDetail(**unified_dict)
        except Exception as e:
            logger.error(f"京东详情解析异常: {e}")
            return None

    # ── 能力声明 ──

    @property
    def capabilities(self) -> set[str]:
        """京东搜索页采集依赖浏览器渲染，详情解析支持离线 HTML"""
        return {"search", "detail"}

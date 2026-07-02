"""
京东适配器（搜索页 + 详情页）
"""

import os, requests, time
from typing import Optional
from urllib.parse import quote

from core.schema import UnifiedProduct, UnifiedDetail
from platforms.base import PlatformAdapter
from core.registry import register
from .search_parser import parse_search_html, raw_to_unified


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
        京东是 React SPA，直接 requests 拿到的 HTML 不含渲染后的商品数据。
        实际使用推荐：
          1. 油猴脚本翻页保存渲染后 HTML（与1688方案一致）
          2. 或用 Selenium 渲染后保存
          3. 或解析 JS 加载的 JSON 接口
        """
        headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        resp = requests.get(self.search_url(keyword, page), headers=headers, timeout=30)
        resp.encoding = 'utf-8'
        time.sleep(0.5)
        return resp.text

    def collect_detail(self, product_id: str) -> str:
        """采集京东详情页 HTML"""
        headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36'),
        }
        resp = requests.get(self.product_url(product_id), headers=headers, timeout=30)
        resp.encoding = 'utf-8'
        time.sleep(0.5)
        return resp.text

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
        京东详情页解析（基础版）。
        京东详情页信息分布在多个异步接口中，完整解析需要：
          1. 页面 HTML 中的 window.pageConfig
          2. p.3.cn 价格接口
          3. 商品描述接口
        此为初步实现，后续可按需增强。
        """
        from bs4 import BeautifulSoup
        import json, re as _re

        soup = BeautifulSoup(html, 'html.parser')

        # 尝试从 pageConfig 提取 sku
        sku = ''
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'pageConfig' in script.string:
                m = _re.search(r'"sku"\s*:\s*"(\d+)"', script.string)
                if m:
                    sku = m.group(1)
                    break

        # 标题
        title_el = soup.find('title')
        title = title_el.get_text(strip=True) if title_el else ''
        # 去除 "- 京东" 后缀
        title = _re.sub(r'\s*[-–—]\s*京东$', '', title)

        # 价格（简单提取）
        price = 0.0
        price_el = soup.find('span', class_='price')
        if price_el:
            m = _re.search(r'[\d.]+', price_el.get_text())
            if m:
                price = float(m.group())

        detail = UnifiedDetail(
            platform="京东",
            product_id=sku,
            product_url=self.product_url(sku) if sku else '',
            title=title,
            price_min=price,
            price_max=price,
            raw_data={'html_saved': True},
        )
        return detail

    # ── 能力声明 ──

    @property
    def capabilities(self) -> set[str]:
        """京东搜索页采集依赖浏览器渲染，详情解析为初步"""
        return {"search"}

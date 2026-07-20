"""
1688 采集器（搜索页 + 详情页）
封装原有的采集逻辑，提供统一的 PlatformAdapter 接口。
"""

import os, requests, time, csv
from typing import Optional
from urllib.parse import quote

from core.schema import UnifiedProduct, UnifiedDetail
from platforms.base import PlatformAdapter
from core.registry import register
from .search_parser import parse_html_to_raw, raw_to_unified


@register("1688")
class AlibabaAdapter(PlatformAdapter):
    """1688 平台适配器"""

    @property
    def platform_name(self) -> str:
        return "1688"

    # ── URL 模板 ──

    def search_url(self, keyword: str, page: int = 1) -> str:
        return (
            f"https://s.1688.com/selloffer/offer_search.htm"
            f"?keywords={quote(keyword)}"
            f"&n=y&spm=a26352.13672862.category.3"
            f"&beginPage={page}"
        )

    def product_url(self, product_id: str) -> str:
        return f"https://detail.1688.com/offer/{product_id}.html"

    # ── 采集 ──

    def collect_search(self, keyword: str, page: int = 1) -> str:
        """
        采集1688搜索页HTML。
        实际项目中由油猴脚本完成，这里提供 requests 后备方案。
        """
        url = self.search_url(keyword, page)
        headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cookie': '',  # 需要登录态时填写
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.encoding = 'gbk'
        time.sleep(1)  # 合理延迟
        return resp.text

    def collect_detail(self, product_id: str) -> str:
        """采集1688详情页HTML"""
        url = self.product_url(product_id)
        headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                           'AppleWebKit/537.36 (KHTML, like Gecko) '
                           'Chrome/120.0.0.0 Safari/537.36'),
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.encoding = 'gbk'
        time.sleep(1)
        return resp.text

    # ── 解析 ──

    def parse_search(self, html: str, keyword: str) -> list[UnifiedProduct]:
        """
        使用原有核心解析逻辑（parse_html_to_raw → raw_to_unified）
        ★ 核心逻辑完全不变 ★
        """
        raw = parse_html_to_raw(html, keyword)
        return raw_to_unified(raw, platform="1688", keyword=keyword)

    def parse_detail(self, html: str) -> Optional[UnifiedDetail]:
        """
        详情页解析：使用 1688 开源库的 AlibabaParser。
        如果第三方库不可用，fallback 到基础解析。
        """
        try:
            import sys
            project_dir = os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))
            lib_path = os.path.join(project_dir, '1688', '1688')
            sys.path.insert(0, lib_path)

            from utils.parsers.alibaba_parser import AlibabaParser
            parser = AlibabaParser(html)
            result = parser.parse()

            if not result:
                return None

            detail = UnifiedDetail(
                platform="1688",
                product_id=result.get('product_code', ''),
                product_url='',
                title=result.get('title', ''),
                brand=result.get('brand', ''),
                spec=result.get('spec', ''),
                price_min=result.get('price_min', 0),
                price_max=result.get('price_max', 0),
                ship_from=result.get('ship_from', ''),
                sales_count=result.get('sales_count', 0),
                min_order=result.get('min_order', 1),
                main_images=result.get('main_images', []),
                detail_images=result.get('detail_images', []),
                videos=result.get('videos', []),
                attributes=result.get('attributes', {}),
                sku_matrix=result.get('sku_matrix', []),
                raw_data=result,
            )
            return detail

        except ImportError:
            print("  警告: 1688 开源库不可用，跳过详情解析")
            return None
        except Exception as e:
            print(f"  详情解析失败: {e}")
            return None

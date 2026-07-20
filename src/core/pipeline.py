"""
管道编排器
将采集 → 解析 → 存储编排为完整管线，支持单平台和多平台。
"""

import os, time, csv
from typing import Optional
from collections import Counter

from core.registry import get_platform, list_platforms
from core.schema import UnifiedProduct, AnalysisReport
from core.storage import product_csv_path, save_products_csv, save_report


class SearchPipeline:
    """搜索页管线：采集 → 解析 → 清洗 → 分析"""

    def __init__(self, platform: str, data_dir: str):
        self.adapter = get_platform(platform)
        self.platform = platform
        self.data_dir = data_dir

    def run(self, keyword: str, pages: int = 1,
            html_dir: Optional[str] = None) -> list[UnifiedProduct]:
        """
        执行搜索页管线。

        Args:
            keyword: 搜索关键词/品类名
            pages: 采集页数（仅在线模式）
            html_dir: 本地 HTML 目录（如有预存文件则读取本地，否则在线采集）

        Returns:
            解析后的 UnifiedProduct 列表
        """
        print(f"\n{'='*55}")
        print(f"  [{self.platform}] 搜索页管线 — {keyword}")
        print(f"{'='*55}")

        all_products = []

        if html_dir and os.path.isdir(html_dir):
            # 模式 A：读取本地 HTML 文件
            html_files = sorted([
                os.path.join(html_dir, f)
                for f in os.listdir(html_dir)
                if f.endswith('.html') and not f.endswith('_files.html')
            ])
            print(f"  读取本地 HTML: {len(html_files)} 个文件")

            for fp in html_files:
                with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                    html = f.read()
                products = self.adapter.parse_search(html, keyword)
                all_products.extend(products)
                print(f"    {os.path.basename(fp)[:25]}: {len(products)} 个商品")

        else:
            # 模式 B：在线采集
            print(f"  在线采集: {pages} 页")
            for page in range(1, pages + 1):
                print(f"    第 {page} 页...", end=' ')
                html = self.adapter.collect_search(keyword, page)
                products = self.adapter.parse_search(html, keyword)
                all_products.extend(products)
                print(f"{len(products)} 个商品")

        # 保存 CSV
        csv_path = product_csv_path(self.data_dir, self.platform, keyword)
        save_products_csv(all_products, csv_path)

        print(f"\n  ✓ 完成: 共 {len(all_products)} 个商品")
        return all_products


class DetailPipeline:
    """详情页管线：URL → 采集 → 解析 → 存储"""

    def __init__(self, platform: str, data_dir: str):
        self.adapter = get_platform(platform)
        self.platform = platform
        self.data_dir = data_dir

    def run(self, keyword: str,
            urls: Optional[list[str]] = None,
            product_ids: Optional[list[str]] = None) -> list:
        """
        执行详情页管线。

        Args:
            keyword: 品类名
            urls: 详情页 URL 列表
            product_ids: 商品 ID 列表
        """
        from core.storage import detail_csv_path

        ids = product_ids or []
        if urls:
            import re
            for url in urls:
                m = re.search(r'offer/(\d+)', url)
                if m:
                    ids.append(m.group(1))
                else:
                    m = re.search(r'/(\d+)\.html', url)
                    if m:
                        ids.append(m.group(1))

        if not ids:
            print("  错误: 未提供任何商品 ID 或 URL")
            return []

        # 去重
        ids = list(set(ids))
        print(f"\n{'='*55}")
        print(f"  [{self.platform}] 详情页管线 — {keyword} ({len(ids)} 个)")
        print(f"{'='*55}")

        results = []
        for pid in ids:
            print(f"    采集: {pid} ...", end=' ')
            try:
                html = self.adapter.collect_detail(pid)
                detail = self.adapter.parse_detail(html)
                if detail:
                    detail.product_id = pid
                    detail.product_url = self.adapter.product_url(pid)
                    results.append(detail)
                    print("✓")
                else:
                    print("解析失败")
            except Exception as e:
                print(f"✗ {e}")
            time.sleep(1)

        if results:
            csv_path = detail_csv_path(self.data_dir, self.platform, keyword)
            from core.storage import save_detail_csv
            save_detail_csv(results, csv_path)

        print(f"\n  ✓ 完成: {len(results)}/{len(ids)} 个成功")
        return results


class CrossPlatformPipeline:
    """跨平台对比管线"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def run(self, keyword: str, platforms: list[str],
            pages: int = 1) -> None:
        """
        对指定关键词执行多平台搜索页采集+对比。

        Args:
            keyword: 品类名
            platforms: 平台列表，如 ["1688", "京东"]
            pages: 每个平台采集页数
        """
        print(f"\n{'='*55}")
        print(f"  跨平台对比 — {keyword}")
        print(f"  平台: {', '.join(platforms)}")
        print(f"{'='*55}")

        for platform in platforms:
            pipeline = SearchPipeline(platform, self.data_dir)
            pipeline.run(keyword, pages=pages)

        # 合并对比
        from core.merge import merge_csv_by_keyword
        merge_csv_by_keyword(self.data_dir, keyword, platforms)

        print(f"\n  ✓ 跨平台对比完成")

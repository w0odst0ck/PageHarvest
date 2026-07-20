"""
1688 工厂搜索 → factories 表

从搜索页提取工厂卡片 → 打开名片页 → 获取产品目录 URL → 写入 factories 表。

用法：
  python -m collector.search --keyword 小夜灯 --pages 5
"""

import argparse
import logging
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser import BrowserManager
from core.db import MonitorDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_ENCODING = "gbk"
DB_PATH = "data/monitor.db"


def extract_card_url(card) -> str:
    """从工厂卡片 data-aplus-report 提取 memberId 拼名片页 URL"""
    report = card.get_attribute("data-aplus-report") or ""
    m = re.search(r"item_id@([^\^]+)", report)
    if m:
        return f"https://sale.1688.com/factory/card.html?memberId={m.group(1)}"
    return ""


def search_factories(keyword: str, pages: int = 5) -> int:
    """采集搜索页并写入 factories 表，返回入库数"""
    db = MonitorDB(DB_PATH)
    db.ensure_schema()

    with BrowserManager(headless=True) as bm:
        total_written = 0

        for page_num in range(1, pages + 1):
            url = (
                f"https://s.1688.com/company/pc/factory_search.htm"
                f"?keywords={quote(keyword, encoding=_ENCODING)}"
                f"&spm=a260k.22462580.searchbox.0&beginPage={page_num}"
            )
            page = bm.new_page(url, wait_until="domcontentloaded")
            time.sleep(3)

            cards = page.query_selector_all(".space-factory-card")
            n = len(cards)
            logger.info("第 %d 页: %d 家工厂", page_num, n)

            for card in cards:
                title_el = card.query_selector(".title")
                city_el = card.query_selector(".city")
                cert_el = card.query_selector(".super-text")
                year_el = card.query_selector(".year-text")
                rates = card.query_selector_all(".rate")

                name = title_el.inner_text().strip() if title_el else ""
                city = city_el.inner_text().strip() if city_el else ""
                cert = cert_el.inner_text().strip() if cert_el else ""
                year_str = year_el.inner_text().strip() if year_el else "0"
                years = int(re.search(r"\d+", year_str).group()) if re.search(r"\d+", year_str) else 0
                response = rates[0].inner_text().strip() if len(rates) >= 1 else ""
                fulfillment = rates[1].inner_text().strip() if len(rates) >= 2 else ""
                repurchase = rates[2].inner_text().strip() if len(rates) >= 3 else ""
                card_url = extract_card_url(card)

                fid = db.upsert_factory(
                    shop_name=name, shop_url=card_url,
                    card_url=card_url, catalog_url="",
                    cert_level=cert, location=city, years_on_1688=years,
                )
                total_written += 1

            page.close()

        # ── 补全产品目录 URL（打开名片页）──
        logger.info("开始补全产品目录 URL...")
        factories = db.get_factories_without_catalog_url()
        # 复用 get_factories_without_shop_url 的查询语义：card_url 有值但尚无 catalog
        page = None
        for f in factories:
            card_url = f["card_url"]
            if "b2b-" not in card_url:
                logger.info("  跳过 alias ID: %s", f["shop_name"])
                continue
            try:
                if page is None:
                    page = bm.new_page(card_url, wait_until="domcontentloaded")
                else:
                    page.goto(card_url, wait_until="domcontentloaded")
                time.sleep(2)

                cat_link = page.query_selector('a[data-btrack*="pc-card-shop-gallery-btn"]')
                if not cat_link:
                    logger.warning("  未找到产品目录链接: %s", f["shop_name"])
                    continue

                catalog_url = cat_link.get_attribute("href") or ""
                # 提取商品总数
                total_text = cat_link.inner_text().strip()
                m = re.search(r"(\d+)", total_text)
                total_products = int(m.group(1)) if m else 0

                # 回填 catalog_url 到 shop_url 字段
                db.upsert_factory(
                    shop_name=f["shop_name"], shop_url=f["shop_url"],
                    card_url=f["card_url"], catalog_url=catalog_url,
                    cert_level=f["cert_level"], location=f["location"],
                    years_on_1688=f["years_on_1688"],
                )
                logger.info("  ✅ %s → %d 商品", f["shop_name"], total_products)
            except Exception as e:
                logger.warning("  ⚠️  失败 %s: %s", f["shop_name"], type(e).__name__)

        if page:
            page.close()

    db.close()
    return total_written


def main():
    parser = argparse.ArgumentParser(description="1688 工厂搜索采集")
    parser.add_argument("--keyword", default="小夜灯", help="搜索关键词")
    parser.add_argument("--pages", type=int, default=5, help="搜索页数")
    args = parser.parse_args()

    n = search_factories(args.keyword, args.pages)
    print(f"\n✅ 采集完成，共 {n} 家工厂")


if __name__ == "__main__":
    main()

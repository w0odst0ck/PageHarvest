"""
产品目录页采集 → factory_snapshots + product_snapshots

读取 factories 表中有 catalog_url 的工厂 → 打开产品目录页 → 爬取商品 → 排序取 Top10 → 入库。

用法：
  python -m collector.offers
"""

import json
import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser import BrowserManager
from core.db import MonitorDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = "data/monitor.db"


def collect_offers() -> int:
    """采集所有活跃工厂的产品目录，返回成功入库的工厂数"""
    db = MonitorDB(DB_PATH)
    db.ensure_schema()

    factories = db.get_factories_with_catalog_url()

    if not factories:
        logger.warning("无待采集工厂（请先运行 collector.search）")
        db.close()
        return 0

    logger.info("待采集: %d 家工厂", len(factories))
    success = 0

    with BrowserManager(headless=True) as bm:
        page = None

        for f in factories:
            catalog_url = f["catalog_url"]
            factory_id = f["id"]
            shop_name = f["shop_name"]

            try:
                if page is None:
                    page = bm.new_page(catalog_url, wait_until="domcontentloaded")
                else:
                    page.goto(catalog_url, wait_until="domcontentloaded")
                time.sleep(3)

                # 提取商品卡片
                product_cards = page.query_selector_all(".galleyItemLink")
                logger.info("  %s: %d 个商品", shop_name, len(product_cards))

                if not product_cards:
                    logger.warning("  无商品卡片，跳过")
                    continue

                # 滚动到底部加载更多商品（懒加载页面）
                prev_count = 0
                for _ in range(5):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    time.sleep(1.5)
                    product_cards = page.query_selector_all(".galleyItemLink")
                    if len(product_cards) == prev_count:
                        break
                    prev_count = len(product_cards)

                logger.info("  加载完成: %d 个商品", len(product_cards))

                products = []
                for card in product_cards:
                    href = card.get_attribute("href") or ""
                    product_id = ""
                    m = re.search(r"/offer/(\d+)", href)
                    if m:
                        product_id = m.group(1)

                    title_el = card.query_selector(".galleyName")
                    title = title_el.inner_text().strip() if title_el else ""

                    price_el = card.query_selector(".price")
                    price_str = price_el.inner_text().strip() if price_el else "0"
                    try:
                        price = float(price_str)
                    except ValueError:
                        price = 0.0

                    price_right = card.query_selector(".priceRight")
                    right_text = price_right.inner_text().strip() if price_right else ""
                    sales = 0
                    m2 = re.search(r"销(\d+)", right_text)
                    if m2:
                        sales = int(m2.group(1))

                    market_tag_el = card.query_selector(".marketTag")
                    sales_tag = market_tag_el.inner_text().strip() if market_tag_el else ""

                    sample_tags = card.query_selector_all(".sampleTag")
                    category_tags = [t.inner_text().strip() for t in sample_tags]

                    products.append({
                        "product_id": product_id,
                        "title": title,
                        "price": price,
                        "sales_30d": sales,
                        "sales_tag": sales_tag,
                        "category_tags": json.dumps(category_tags, ensure_ascii=False),
                    })

                # 排序取 Top10
                products.sort(key=lambda p: p["sales_30d"], reverse=True)
                top10 = products[:10]

                avg_sales = (
                    sum(p["sales_30d"] for p in top10 if p["sales_30d"])
                    / len([p for p in top10 if p["sales_30d"]])
                    if any(p["sales_30d"] for p in top10) else 0
                )

                # 商品总数（页面可能因懒加载不完整，暂用可见数）
                total_in_page = len(product_cards)

                db.add_factory_snapshot(
                    factory_id=factory_id,
                    total_products=total_in_page,
                    top10_avg_sales=avg_sales,
                )
                db.add_product_snapshots(factory_id, top10)

                logger.info(
                    "  ✅ Top10 均销 %.1f, 最高 %d",
                    avg_sales, top10[0]["sales_30d"] if top10 else 0
                )
                success += 1

            except Exception as e:
                logger.warning("  ⚠️  %s: %s", shop_name, type(e).__name__)

        if page:
            page.close()

    db.close()
    return success


def main():
    n = collect_offers()
    print(f"\n✅ 采集完成，{n} 家工厂成功入库")


if __name__ == "__main__":
    main()

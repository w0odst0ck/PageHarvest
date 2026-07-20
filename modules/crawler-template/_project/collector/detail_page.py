"""
【模板】详情页/子页面采集

功能：
  - 读取 items 表中带 detail_url 的条目
  - 逐一打开详情页 → 提取结构化数据 → 写入快照表

使用前：
  1. 修改 extract_detail_fields() 中的页面选择器
  2. 修改 add_snapshot() 的参数匹配你的表字段

用法：
    python -m collector.detail_page
"""

import logging
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser import BrowserManager
from core.db import ProjectDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PLATFORM = "目标平台"
DB_PATH = "data/monitor.db"
LOGIN_URL = "https://example.com/login"
CHECK_URL = "https://example.com"


# ═══════════════════════════════════════════════════════
# 【修改点】详情页解析逻辑
# ═══════════════════════════════════════════════════════

def extract_detail_fields(page) -> dict:
    """从详情页提取结构化数据

    修改点：
      - 字段选择器和提取逻辑
      - 返回的 dict keys 匹配 add_snapshot() 的参数
    """
    # 示例：提取标题、价格、销量
    title_el = page.query_selector(".title-selector")
    price_el = page.query_selector(".price-selector")
    sales_el = page.query_selector(".sales-selector")

    title = title_el.inner_text().strip() if title_el else ""
    price_str = price_el.inner_text().strip() if price_el else "0"

    try:
        price = float(price_str)
    except ValueError:
        price = 0.0

    sales_text = sales_el.inner_text().strip() if sales_el else ""
    sales = 0
    m = re.search(r"(\d+)", sales_text)
    if m:
        sales = int(m.group(1))

    return {
        "field_a": price,      # 数值：价格
        "field_b": sales,      # 整数：销量
        "field_c": title,      # 文本：标题
        "description": f"¥{price} / 销量{sales}",
    }


def handle_lazy_load(page, max_scrolls: int = 5) -> int:
    """处理懒加载页面：滚动到底部加载更多

    Args:
        page: Playwright Page
        max_scrolls: 最多滚动次数

    Returns:
        最终可见元素数
    """
    prev_count = 0
    for _ in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(1.5)
        cards = page.query_selector_all(".card-selector")
        if len(cards) == prev_count:
            break
        prev_count = len(cards)
    return prev_count


def collect_details() -> int:
    """采集所有待处理条目的详情，返回成功入库数"""
    db = ProjectDB(DB_PATH)
    db.ensure_schema()
    items = db.get_items_with_detail()

    if not items:
        logger.warning("无待采集条目（请先运行 collector.list_page）")
        db.close()
        return 0

    logger.info("待采集: %d 条", len(items))
    success = 0

    with BrowserManager(headless=True, login_url=LOGIN_URL) as bm:
        # 登录检查（可选）
        if not bm.check_login(check_url=CHECK_URL):
            logger.warning("Cookie 无效，请先登录")
            bm.restart(headless=False)
            bm.wait_for_login()
            bm.restart(headless=True)

        page = None
        for item in items:
            detail_url = item["detail_url"]
            item_id = item["id"]
            name = item["name"]

            try:
                # 复用 page 对象，用 goto 导航
                if page is None:
                    page = bm.new_page(detail_url, wait_until="domcontentloaded")
                else:
                    page.goto(detail_url, wait_until="domcontentloaded",
                              timeout=15000)
                time.sleep(3)

                fields = extract_detail_fields(page)

                db.add_snapshot(item_id=item_id, **fields)
                logger.info("  ✅ %s: %s", name,
                            fields.get("description", ""))
                success += 1

            except Exception as e:
                logger.warning("  ⚠️  %s: %s", name, type(e).__name__)
                continue  # 单个失败不影响后续

        if page:
            page.close()

    db.close()
    return success


def main():
    n = collect_details()
    print(f"\n✅ 采集完成，{n} 条成功入库")


if __name__ == "__main__":
    main()

"""
【模板】列表页/搜索页采集

功能：
  - 构造搜索 URL（注意中文编码）
  - 打开搜索页 → 等待渲染
  - 提取卡片列表 → 逐项解析 → 写入 items 表
  - 打开子页面补全 detail_url（如名片页→产品目录页）

使用前：
  1. 修改 PLATFORM 常量
  2. 修改 _ENCODING（1688 用 gbk，其他一般 utf-8）
  3. 修改 SEARCH_URL_TEMPLATE 和卡片选择器
  4. 修改字段提取逻辑 match 你的页面结构
  5. 修改 upsert_item() 调用匹配你的业务表结构

用法：
    python -m collector.list_page --keyword 关键词 --pages 3
    python -m collector.list_page --compile-detail   # 补全 detail_url
"""

import argparse
import logging
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser import BrowserManager
from core.db import ProjectDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════
# 【修改点】平台相关常量
# ═══════════════════════════════════════════════════════

PLATFORM = "目标平台"           # 仅用于日志
_ENCODING = "utf-8"            # 1688 工厂搜索用 "gbk"
DB_PATH = "data/monitor.db"
LOGIN_URL = "https://example.com/login"
CHECK_URL = "https://example.com"

# 搜索 URL 模板，用 {keyword} 和 {page} 占位
SEARCH_URL_TEMPLATE = (
    "https://example.com/search"
    "?keywords={keyword}&page={page}"
)

# 每页最大条目数，用于翻页空时判断跳过后续页
MAX_PER_PAGE = 50


# ═══════════════════════════════════════════════════════
# 【修改点】页面元素解析
# ═══════════════════════════════════════════════════════

def extract_items_from_page(page) -> list[dict]:
    """从搜索页提取条目列表

    修改点：
      - query_selector_all 的选择器
      - 每个字段的提取逻辑
      - 返回的 dict 结构和 keys
    """
    cards = page.query_selector_all(".card-selector")
    items = []
    for card in cards:
        name_el = card.query_selector(".name-selector")
        url_el = card.query_selector("a[href]")

        name = name_el.inner_text().strip() if name_el else ""
        url = url_el.get_attribute("href") or "" if url_el else ""

        items.append({"name": name, "url": url})
    return items


def extract_detail_url(page) -> str:
    """从名片页/详情页提取详情 URL

    修改点：
      - 定位详情链接的选择器
    """
    link = page.query_selector('a[data-attr*="detail"]')
    return link.get_attribute("href") or "" if link else ""


def collect_list_page(keyword: str, pages: int = 5) -> int:
    """采集搜索页并写入 items 表，返回入库数"""
    db = ProjectDB(DB_PATH)
    db.ensure_schema()
    total_written = 0

    with BrowserManager(headless=True, login_url=LOGIN_URL) as bm:
        # ── 登录检查 ──
        if not bm.check_login(check_url=CHECK_URL):
            logger.warning("Cookie 无效，切换到有头模式登录...")
            bm.restart(headless=False)
            bm.wait_for_login()
            # 登录后切回无头
            bm.restart(headless=True)

        for page_num in range(1, pages + 1):
            url = SEARCH_URL_TEMPLATE.format(
                keyword=quote(keyword, encoding=_ENCODING),
                page=page_num
            )
            # 【注意】1688 等平台网络慢，用 "domcontentloaded" 避免长连接超时
            page = bm.new_page(url, wait_until="domcontentloaded")
            time.sleep(3)  # 等 JS 渲染

            items = extract_items_from_page(page)
            if not items:
                logger.info("第 %d 页无数据，翻页结束", page_num)
                page.close()
                break
            logger.info("第 %d 页: %d 条", page_num, len(items))

            for item in items:
                try:
                    db.upsert_item(
                        name=item["name"],
                        url=item["url"],
                    )
                    total_written += 1
                except Exception as e:
                    logger.warning("  写入失败: %s — %s",
                                   item.get("name", "?"), e)

            page.close()

        # ── 补全 detail_url（如需要）──
        _compile_detail_urls(bm, db)

    db.close()
    return total_written


def _compile_detail_urls(bm: BrowserManager, db: ProjectDB):
    """遍历无 detail_url 的条目，打开子页面补全

    模式：打开条目页面 → 定位详情入口 → 提取 URL → 回填
    """
    items = db.get_items_without_detail()
    if not items:
        return
    logger.info("开始补全详情 URL（%d 条）...", len(items))

    page = None
    for item in items:
        url = item["url"]
        try:
            if page is None:
                page = bm.new_page(url, wait_until="domcontentloaded")
            else:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(2)

            detail_url = extract_detail_url(page)
            if not detail_url:
                logger.debug("  无详情入口: %s", item["name"])
                continue

            db.upsert_item(name=item["name"], url=item["url"],
                           detail_url=detail_url)
            logger.info("  ✅ %s → %s", item["name"],
                        detail_url[:60])
        except Exception as e:
            logger.warning("  ⚠️  %s: %s", item["name"],
                           type(e).__name__)
            continue

    if page:
        page.close()


def main():
    parser = argparse.ArgumentParser(description=f"{PLATFORM} 列表页采集")
    parser.add_argument("--keyword", default="关键词", help="搜索关键词")
    parser.add_argument("--pages", type=int, default=5, help="搜索页数")
    parser.add_argument("--compile-detail", action="store_true",
                        help="仅补全 detail_url（不重新搜索）")
    parser.add_argument("--headless", action="store_true", default=True,
                        help="无头模式")
    args = parser.parse_args()

    if args.compile_detail:
        db = ProjectDB(DB_PATH)
        with BrowserManager(headless=args.headless, login_url=LOGIN_URL) as bm:
            _compile_detail_urls(bm, db)
        db.close()
        print("✅ 详情 URL 补全完成")
        return

    n = collect_list_page(args.keyword, args.pages)
    print(f"\n✅ 采集完成，共 {n} 条")


if __name__ == "__main__":
    main()

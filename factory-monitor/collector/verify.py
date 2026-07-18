"""
⚠️  废弃说明

此文件是项目搭建阶段的一次性全链路验证脚本。
全链路验证通过后，已被正式采集脚本替代：
  - collector/search.py  （搜索页采集）
  - collector/offers.py  （产品目录采集）
  - cli/run.py           （一键编排）

保留此文件仅作为 DOM 选择器参考，不再使用。
"""

"""

流程：
  1. 有头浏览器 → 自动登录（或有 Cookie 则跳过）
  2. 搜索"小夜灯"
  3. 提取第一页工厂卡片 → 打印 → 你确认
  4. 打开名片页 → 进入产品目录页 → 打印 → 你确认
  5. 打开产品目录页 → 提取商品总数 + 商品 → 打印 → 你确认
  6. 写入 SQLite data/verify.db

用法：
  cd 1688-factory-monitor
  .venv/bin/python3 -m collector.verify
"""

import json
import logging
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

# 1688 工厂搜索页使用 GBK 编码中文关键词
_ENCODING = "gbk"

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.browser import BrowserManager
from core.db import MonitorDB

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = "data/verify.db"
KEYWORD = "小夜灯"
PAGES = 1  # 仅第一页

PAUSE = "\n  ⏸  确认上述数据后输入 y 继续（或 n 退出）: "


def confirm(prompt: str = PAUSE) -> bool:
    """交互式确认"""
    while True:
        resp = input(prompt).strip().lower()
        if resp == "y":
            return True
        if resp == "n":
            print("  ❌ 退出验证")
            sys.exit(0)


def extract_card_url(card) -> str:
    """从工厂卡片的 data-aplus-report 提取 memberId 拼名片页 URL"""
    report = card.get_attribute("data-aplus-report") or ""
    m = re.search(r"item_id@([^\^]+)", report)
    if m:
        return f"https://sale.1688.com/factory/card.html?memberId={m.group(1)}"
    return ""


def main():
    db = MonitorDB(DB_PATH)
    db.ensure_schema()
    logger.info("数据库初始化完成: %s", DB_PATH)

    with BrowserManager(headless=False) as bm:
        # ── 1. 登录（如有 Cookie 则跳过）──
        print("\n" + "=" * 60)
        print("  步骤 1/5: 1688 登录")
        print("=" * 60)
        if bm.cookie_path.exists():
            print("  检测到已有 Cookie，跳过登录步骤")
            check_page = bm.new_page("https://www.1688.com/")
            time.sleep(2)
            if "login.1688.com" in check_page.url:
                print("  ⚠️  Cookie 已过期，请删除 data/cookies.json 后重试")
                sys.exit(1)
            check_page.close()
            print("  ✅ Cookie 有效")
        else:
            print("  浏览器已打开，请在浏览器中手动登录 1688")
            page = bm.new_page("https://www.1688.com/")
            input("  登录完成后请按 Enter 继续...")
            bm.save_cookies()
            print("  ✅ Cookie 已保存")

        # ── 2. 搜索页 ──
        print("\n" + "=" * 60)
        print(f"  步骤 2/5: 搜索「{KEYWORD}」工厂")
        print("=" * 60)

        search_url = (
            f"https://s.1688.com/company/pc/factory_search.htm"
            f"?keywords={quote(KEYWORD, encoding=_ENCODING)}"
            f"&spm=a260k.22462580.searchbox.0&beginPage=1"
        )
        page = bm.new_page(search_url, wait_until="domcontentloaded")
        time.sleep(3)  # 等待 JS 渲染

        print(f"  当前 URL: {page.url}")
        print(f"  页面标题: {page.title()}")

        # 提取工厂卡片
        cards = page.query_selector_all(".space-factory-card")
        n_cards = len(cards)
        print(f"\n  找到 {n_cards} 家工厂卡片")
        if n_cards == 0:
            body_snippet = page.evaluate(
                "document.body?.innerText?.substring(0, 300) || '(空)'"
            )
            print(f"  页面正文(前300字): {body_snippet[:300]}")

        factories_raw = []
        for i, card in enumerate(cards[:5]):  # 仅展示前 5 家
            title_el = card.query_selector(".title")
            city_el = card.query_selector(".city")
            cert_el = card.query_selector(".super-text")
            year_el = card.query_selector(".year-text")
            rates = card.query_selector_all(".rate")

            name = title_el.inner_text().strip() if title_el else "?"
            city = city_el.inner_text().strip() if city_el else "?"
            cert = cert_el.inner_text().strip() if cert_el else "?"
            year = year_el.inner_text().strip() if year_el else "?"
            response = rates[0].inner_text().strip() if len(rates) >= 1 else "?"
            fulfillment = rates[1].inner_text().strip() if len(rates) >= 2 else "?"
            repurchase = rates[2].inner_text().strip() if len(rates) >= 3 else "?"
            card_url = extract_card_url(card)

            factories_raw.append({
                "name": name, "city": city, "cert": cert, "year": year,
                "response": response, "fulfillment": fulfillment,
                "repurchase": repurchase, "card_url": card_url,
            })

            print(f"\n  [{i+1}] {name}")
            print(f"      城市: {city}  认证: {cert}  开店: {year}")
            print(f"      响应: {response}  履约: {fulfillment}  回头: {repurchase}")
            print(f"      名片: {card_url[:80]}...")

        confirm()

        # 写入所有 24 家到 factories 表
        for f in factories_raw:
            db.upsert_factory(
                shop_name=f["name"],
                shop_url="",
                card_url=f["card_url"],
                cert_level=f["cert"],
                location=f["city"],
                years_on_1688=int(re.search(r"\d+", f["year"]).group()) if re.search(r"\d+", f["year"]) else 0,
            )
        for card in cards[5:]:
            title_el = card.query_selector(".title")
            city_el = card.query_selector(".city")
            cert_el = card.query_selector(".super-text")
            year_el = card.query_selector(".year-text")

            name = title_el.inner_text().strip() if title_el else "?"
            city = city_el.inner_text().strip() if city_el else "?"
            cert = cert_el.inner_text().strip() if cert_el else "?"
            year = year_el.inner_text().strip() if year_el else "?"
            card_url = extract_card_url(card)

            db.upsert_factory(
                shop_name=name, shop_url="", card_url=card_url,
                cert_level=cert, location=city,
                years_on_1688=int(re.search(r"\d+", year).group()) if re.search(r"\d+", year) else 0,
            )

        print(f"\n  ✅ {n_cards} 家工厂已写入 factories 表")

        # ── 3. 名片页 → 产品目录页 ──
        print("\n" + "=" * 60)
        print("  步骤 3/5: 从名片页进入产品目录页")
        print("=" * 60)

        # 遍历工厂，跳过 alias ID，自动重试下一家
        chosen_factory = None
        catalog_url = ""
        total_products = -1
        for candidate in factories_raw:
            c_url = candidate["card_url"]
            if "b2b-" not in c_url:
                print(f"  跳过 alias ID: {candidate['name']} ({c_url[:60]}...)")
                continue
            print(f"  正在打开: {candidate['name']}")
            print(f"  名片页: {c_url}")
            try:
                page.goto(c_url, wait_until="load", timeout=15000)
                time.sleep(2)

                # 通过 data-btrack 找产品目录链接
                cat_link = page.query_selector('a[data-btrack*="pc-card-shop-gallery-btn"]')
                if not cat_link:
                    print(f"  ⚠️  未找到产品目录入口，试下一家")
                    continue

                catalog_url = cat_link.get_attribute("href") or ""
                # 从链接文字提取商品总数（共741个商品）
                total_text = cat_link.inner_text().strip()
                m = re.search(r"(\d+)", total_text)
                if m:
                    total_products = int(m.group(1))
                    print(f"  商品总数: {total_products}")

                print(f"  产品目录: {catalog_url}")
                page.goto(catalog_url, wait_until="load", timeout=15000)
                time.sleep(3)
                chosen_factory = candidate
                print(f"  ✅ 进入产品目录页成功")
                break
            except Exception as e:
                print(f"  ⚠️  加载失败 ({type(e).__name__})，试下一家")

        if not chosen_factory:
            print("  ❌ 所有工厂均无法进入产品目录页，退出")
            sys.exit(1)

        print(f"  当前 URL: {page.url}")
        print(f"  页面标题: {page.title()}")

        confirm()

        # ── 4. 产品目录页采集 ──
        print("\n" + "=" * 60)
        print("  步骤 4/5: 产品目录页采集")
        print("=" * 60)

        # 产品目录 URL（步骤 3 存储在 catalog_url）
        actual_url = page.url
        actual_title = page.title()
        print(f"  产品目录 URL: {actual_url}")
        print(f"  页面标题: {actual_title}")

        # 提取商品总数（优先用名片页提取的值，页面选择器兜底）
        if total_products <= 0:
            total_el = page.query_selector(".sectionCount")
            total_products = int(total_el.inner_text().strip()) if total_el else -1
        print(f"\n  商品总数: {total_products}")

        # 提取商品卡片
        product_cards = page.query_selector_all(".galleyItemLink")
        n_products = len(product_cards)
        print(f"  可见商品卡片: {n_products} 个")

        top_products = []
        for card in product_cards:
            href = card.get_attribute("href") or ""
            product_id = ""
            m = re.search(r"/offer/(\d+)", href)
            if m:
                product_id = m.group(1)

            title_el = card.query_selector(".galleyName")
            title = title_el.inner_text().strip() if title_el else "?"

            price_el = card.query_selector(".price")
            price_str = price_el.inner_text().strip() if price_el else "0"
            try:
                price = float(price_str)
            except ValueError:
                price = 0.0

            # 销量解析：「销205个」→ 205
            price_right = card.query_selector(".priceRight")
            right_text = price_right.inner_text().strip() if price_right else ""
            sales = 0
            m2 = re.search(r"销(\d+)", right_text)
            if m2:
                sales = int(m2.group(1))

            # 销量排名标签
            market_tag_el = card.query_selector(".marketTag")
            sales_tag = market_tag_el.inner_text().strip() if market_tag_el else ""

            # 品类标签
            sample_tags = card.query_selector_all(".sampleTag")
            category_tags = [t.inner_text().strip() for t in sample_tags]

            top_products.append({
                "product_id": product_id,
                "title": title,
                "price": price,
                "sales_30d": sales,
                "sales_tag": sales_tag,
                "category_tags": json.dumps(category_tags, ensure_ascii=False),
            })

        # 按销量排序取 Top10
        top_products.sort(key=lambda p: p["sales_30d"], reverse=True)
        top10 = top_products[:10]

        print(f"\n  按销量排序 Top10:")
        print(f"  {'排名':>3} {'销量':>5} {'价格':>8}  标题")
        print(f"  {'-'*3} {'-'*5} {'-'*8}  {'-'*30}")
        for i, p in enumerate(top10):
            sales_str = f"{p['sales_30d']}" if p['sales_30d'] else "N/A"
            print(f"  {i+1:>3} {sales_str:>5} ¥{p['price']:>6.2f}  {p['title'][:35]}")

        confirm()

        # ── 5. 写库 ──
        print("\n" + "=" * 60)
        print("  步骤 5/5: 写入 SQLite")
        print("=" * 60)

        factory_id = db.get_all_factories()[0]["id"]
        avg_sales = (
            sum(p["sales_30d"] for p in top10 if p["sales_30d"])
            / len([p for p in top10 if p["sales_30d"]])
            if any(p["sales_30d"] for p in top10) else 0
        )

        db.add_factory_snapshot(
            factory_id=factory_id,
            total_products=total_products if total_products > 0 else None,
            top10_avg_sales=avg_sales,
        )
        db.add_product_snapshots(factory_id, top10)

        print(f"  ✅ factory_snapshot 已写入")
        print(f"  ✅ {len(top10)} 条 product_snapshots 已写入")
        print(f"  Top10 平均销量: {avg_sales:.1f}")

        page.close()

    # ── 完成 ──
    print("\n" + "=" * 60)
    print("  全链路验证完成 ✅")
    print("=" * 60)
    print(f"\n  数据库: {DB_PATH}")
    print(f"  工厂数: {len(db.get_all_factories())}")
    print(f"  可通过以下命令查看:")
    print(f"    python -m cli.query list")

    db.close()


if __name__ == "__main__":
    main()

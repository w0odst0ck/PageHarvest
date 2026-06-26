"""
用 Selenium 从1688搜索页获取商品详情页URL（精确匹配版）
"""

import csv
import os
import sys
import re
import time
from collections import Counter
from urllib.parse import quote

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_top_products(category, top_n=10):
    csv_path = os.path.join(PROJECT_DIR, "data", category, "cleaned_products.csv")
    if not os.path.exists(csv_path):
        print(f"错误: 未找到 {csv_path}")
        return []
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    shop_counter = Counter(r['shop_name'] for r in rows if r['shop_name'])
    top_shops = [s for s, _ in shop_counter.most_common(top_n)]
    targets = []
    for shop in top_shops:
        shop_products = [r for r in rows if r['shop_name'] == shop]
        priced = []
        for r in shop_products:
            try:
                priced.append((float(r['price']), r))
            except:
                pass
        if not priced:
            continue
        priced.sort(key=lambda x: x[0])
        target = priced[len(priced) // 2][1]
        targets.append({
            'shop_name': shop,
            'title': target['title'],
            'price': target['price'],
            'product_count': shop_counter[shop],
        })
    return targets


def do_search(driver, keywords):
    """在1688搜索框输入关键词并点击搜索"""
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys

    try:
        search_box = driver.find_element(By.ID, 'ali-search-box')
    except:
        try:
            search_box = driver.find_element(By.CLASS_NAME, 'ali-search-box')
        except:
            try:
                search_box = driver.find_element(By.CSS_SELECTOR, 'input[type="text"]')
            except:
                print("    找不到搜索框")
                return

    # 用JavaScript清空和赋值，避免clear()报错
    driver.execute_script("arguments[0].value = '';", search_box)
    time.sleep(0.5)
    driver.execute_script(f"arguments[0].value = '{keywords}';", search_box)
    time.sleep(0.5)
    search_box.send_keys(Keys.RETURN)
    time.sleep(5)

    # 检查是否跳转到搜索结果页
    if 'offer_search' not in driver.current_url and '搜索' not in driver.title:
        print(f"    ⚠ 搜索可能未触发，当前URL: {driver.current_url[:60]}")
        time.sleep(3)


def parse_offers_from_html(html, target_shop_name):
    """从渲染后的搜索页HTML中提取所有商品，匹配店铺名"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')

    offers = []
    seen_oids = set()

    # 找到所有店铺链接的<a>标签
    shop_links = soup.find_all('a', href=re.compile(r'//([^.]+)\.1688\.com'))
    for link in shop_links:
        link_html = str(link)
        # 向上找父容器
        parent = link
        for _ in range(10):
            if parent and parent.name == 'div':
                parent_html = str(parent)
                oid_match = re.search(r'offerId=(\d+)', parent_html)
                if oid_match:
                    oid = oid_match.group(1)
                    if oid in seen_oids:
                        break
                    shop_name = link.get_text(strip=True) or link.get('title', '')
                    # 标题
                    title_el = parent.find('div', class_=re.compile(r'title-text|title-row'))
                    title = title_el.get_text(strip=True) if title_el else ''
                    # 价格
                    price_el = parent.find('div', class_=re.compile(r'price'))
                    price = ''
                    if price_el:
                        pm = re.search(r'[\d.]+', price_el.get_text(strip=True))
                        if pm:
                            price = pm.group()

                    seen_oids.add(oid)
                    offers.append({
                        'offer_id': oid,
                        'shop_name': shop_name,
                        'title': title,
                        'price': price,
                    })
                    break
            if parent:
                parent = parent.parent
            else:
                break

    return offers


def search_and_match(title, shop_name, driver):
    """搜索并精确匹配店铺名"""
    # 关键词 = 店铺名 + 标题前部分（更精准）
    keywords = f"{shop_name} {title[:15]}"
    print(f"  搜索: {keywords}")

    try:
        # 先回首页
        driver.get("https://www.1688.com/")
        time.sleep(3)

        do_search(driver, keywords)
        # 等渲染
        for _ in range(8):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
        time.sleep(2)
        driver.execute_script("window.scrollTo(0, 0)")
        time.sleep(1)

        html = driver.page_source
        offers = parse_offers_from_html(html, shop_name)

        if not offers:
            print(f"    页面未解析到商品")
            return None, None

        print(f"    解析到 {len(offers)} 个商品")

        # 精确匹配
        matched = [o for o in offers if o['shop_name'] == shop_name or shop_name in o['shop_name']]
        if matched:
            o = matched[0]
            url = f"https://detail.1688.com/offer/{o['offer_id']}.html"
            print(f"    ✅ 店铺: {o['shop_name']} → {url}")
            return o['offer_id'], url

        # 标题匹配
        title_kw = title[:8]
        matched2 = [o for o in offers if title_kw in o['title']]
        if matched2:
            o = matched2[0]
            url = f"https://detail.1688.com/offer/{o['offer_id']}.html"
            print(f"    ⚠ 标题匹配: {o['shop_name']} / {o['title'][:25]}")
            return o['offer_id'], url

        print(f"    未匹配到 [{shop_name}]")
        for o in offers[:3]:
            print(f"      结果: {o['shop_name']} | {o['title'][:30]}")
        return None, None

    except Exception as e:
        print(f"    ✗ 异常: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def setup_driver():
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    chromedriver_path = os.path.join(PROJECT_DIR, 'chromedriver-win32', 'chromedriver.exe')
    service = Service(chromedriver_path)
    options = webdriver.ChromeOptions()
    options.add_argument(f'--user-data-dir={os.path.join(PROJECT_DIR, "chrome_profile")}')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    return webdriver.Chrome(service=service, options=options)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='获取1688商品详情页URL')
    parser.add_argument('--cat', default='投光灯', help='品类名')
    parser.add_argument('--top', type=int, default=10, help='取前N个供应商')
    args = parser.parse_args()

    targets = get_top_products(args.cat, args.top)
    if not targets:
        return

    print(f"\n{'='*60}")
    print(f"目标: {args.cat} 品类 Top {args.top} 供应商")
    print(f"{'='*60}")
    for i, t in enumerate(targets, 1):
        print(f"  {i}. {t['shop_name']} ({t['product_count']}个)")
        print(f"     代表: {t['title'][:40]}")
    print()

    driver = setup_driver()

    # 登录检查
    driver.get("https://www.1688.com/")
    time.sleep(3)
    if '登录' in driver.title or 'login' in driver.current_url:
        print("⚠ 请手动登录1688后按回车继续...")
        driver.get("https://login.1688.com/")
        input()
    else:
        print("✅ 已登录")

    results = []
    for i, t in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {t['shop_name']}")
        oid, url = search_and_match(t['title'], t['shop_name'], driver)
        results.append({
            'shop_name': t['shop_name'],
            'title': t['title'],
            'detail_url': url or '',
            'offer_id': oid or '',
        })

    driver.quit()

    print(f"\n{'='*60}")
    print("结果汇总")
    print(f"{'='*60}")
    found = [r for r in results if r['detail_url']]
    print(f"成功: {len(found)}/{len(results)}")
    for r in results:
        status = '✅' if r['detail_url'] else '❌'
        print(f"  {status} {r['shop_name']}")
        if r['detail_url']:
            print(f"      {r['detail_url']}")

    out_path = os.path.join(PROJECT_DIR, "data", args.cat, "top_products_urls.csv")
    with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=['shop_name', 'title', 'detail_url', 'offer_id'])
        writer.writeheader()
        writer.writerows(results)
    print(f"\n已保存: {out_path}")


if __name__ == '__main__':
    main()

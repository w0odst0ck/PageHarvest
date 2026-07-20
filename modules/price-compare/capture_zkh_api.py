"""
拦截 ZKH 搜索 API

打开浏览器加载首页（无滑块），你在搜索框里手动搜一次，
Playwright 后台拦截所有 API 请求，找出搜索接口。
"""

import sys, json, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.browser import BrowserManager

# 收集所有 API 请求
all_apis = []

with BrowserManager(headless=False) as browser:
    page = browser.new_page("zkh")

    def on_response(resp):
        url = resp.url
        if resp.status < 400 and "servezkhApi" in url:
            method = resp.request.method
            all_apis.append({"method": method, "url": url, "time": time.time()})
            # 如果是搜索相关的，直接打出来
            if any(kw in url.lower() for kw in ["search", "query", "product", "list"]):
                try:
                    data = resp.json()
                    print(f"\n🔍 [{method}] {url[:120]}")
                    print(f"   JSON: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
                except Exception:
                    print(f"\n🔍 [{method}] {url[:120]}")

    page.on("response", on_response)

    # 1. 加载首页
    page.goto("https://www.zkh.com/", wait_until="networkidle", timeout=30000)
    print(f"✅ 首页已加载: {page.url}")
    print(f"\n{'='*50}")
    print("请在浏览器中手动输入搜索词并搜索")
    print("例如输入：敏华 M-ZFZD-E5W3004")
    print("搜索完成后回到终端按 Enter")
    print(f"{'='*50}")
    input("\n按 Enter 继续...")

    # 2. 等待异步请求收尾
    time.sleep(3)

    # 3. 输出结果
    print(f"\n{'='*50}")
    print(f"拦截到 {len(all_apis)} 个 servezkhApi 请求")
    print(f"{'='*50}")

    # 按时间排序
    all_apis.sort(key=lambda x: x["time"])

    search_apis = [a for a in all_apis if "search" in a["url"].lower()]
    product_apis = [a for a in all_apis if "product" in a["url"].lower() and a not in search_apis]
    other = [a for a in all_apis if a not in search_apis and a not in product_apis]

    if search_apis:
        print(f"\n🔍 搜索 API:")
        for a in search_apis:
            print(f"   [{a['method']}] {a['url']}")

    if product_apis:
        print(f"\n📦 商品 API:")
        for a in product_apis:
            print(f"   [{a['method']}] {a['url']}")

    if other:
        print(f"\n📋 其他 ({len(other)} 个):")
        for a in other[:10]:
            print(f"   [{a['method']}] {a['url'][:120]}")

    # 保存
    path = Path("output/zkh_api_capture.json")
    path.parent.mkdir(exist_ok=True)
    with open(path, "w") as f:
        json.dump(all_apis, f, ensure_ascii=False, indent=2)
    print(f"\n已保存: {path}")

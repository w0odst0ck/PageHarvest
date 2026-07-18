"""
最小验证：headed 模式加载 ZKH 搜索页，看是否弹滑块
"""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.browser import BrowserManager

with BrowserManager(headless=False) as browser:
    print("🚀 打开浏览器...")
    page = browser.new_page("zkh", stealth=True)

    url = "https://www.zkh.com/search.html?keywords=%E6%95%8F%E5%8D%8E%20M-ZFZD-E5W3004"
    print(f"📌 加载: {url}")
    page.goto(url, wait_until="networkidle", timeout=30000)

    html = page.content()
    final_url = page.url
    print(f"   最终 URL: {final_url}")
    print(f"   HTML 大小: {len(html)} 字节")

    # 检测滑块/验证码
    text = html.lower()
    keywords = ["验证码", "滑块", "人机验证", "captcha", "verify", "受限", "cloudflare"]
    for kw in keywords:
        if kw in text:
            print(f"   ⛔ 检测到: {kw}")
            break
    else:
        print(f"   ✅ 无验证码")

    # 检查 SSR 数据
    has_data = "__INITIAL_DATA__" in html
    has_price = "sku-price-wrap-new" in html
    print(f"   含 SSR 数据: {has_data}")
    print(f"   含价格元素: {has_price}")

    input("\n按 Enter 关闭浏览器...")

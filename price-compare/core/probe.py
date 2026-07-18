"""
平台探测脚本

在 Playwright 浏览器中实际访问平台搜索页，输出真实 DOM 结构和 API 响应。

探测策略：
  1688: 直接搜索 URL → 弹滑块则让用户手动过一次 → 保存 state → 提取 DOM
  ZKH:  移除 WAF 遮罩 → JS 注入搜索 → 拦截 API

用法：
    python3 -m core.probe 1688
    python3 -m core.probe zkh
"""

import sys
import json
import time
import urllib.parse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.browser import BrowserManager


# ═══════════════════════════════════════════════════════════════
#  1688 探测
# ═══════════════════════════════════════════════════════════════

def _is_captcha_page(page_url: str, html: str = "") -> bool:
    """检测页面是否被风控/验证码拦截（URL + HTML 双重检测）"""
    url_lower = page_url.lower()
    if any(x in url_lower for x in ["captcha", "verify", "nc", "slider", "login"]):
        return True
    if not html:
        return False
    text = html.lower()
    keywords = [
        "验证码", "滑块", "人机验证", "captcha", "verify",
        "访问受限", "请求太频繁", "身份验证",
        "很抱歉", "访问出错", "系统检测到",
        "请滑动", "拖动滑块", "安全验证",
    ]
    for kw in keywords:
        if kw.lower() in text:
            return True
    return False


def _probe_1688(browser, keyword: str):
    print(f"\n{'='*60}")
    print(f"🔍 1688 平台探测")
    print(f"{'='*60}")

    platform = "1688"

    # ── 1. 登录 ──
    print(f"\n📌 1. 登录状态")
    if browser.has_state(platform):
        print(f"   已保存 ✅")
    else:
        browser.login(platform, "https://www.1688.com/",
                      check_logged_in=lambda p: "我的阿里" in p.content())

    # ── 2. 搜索 ──
    # URL 编码 keyword，防止中文/空格导致乱码和截断
    encoded_kw = urllib.parse.quote(keyword, safe='')
    search_url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={encoded_kw}"
    print(f"\n📌 2. 搜索")
    print(f"   关键词: {keyword}")
    print(f"   URL:    {search_url}")

    page = browser.new_page(platform, stealth=True)

    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        html = page.content()
        final_url = page.url

        # ── 3. 滑块/验证码处理（最多重试 3 次） ──
        captcha_retries = 0
        max_captcha_retries = 3

        while _is_captcha_page(final_url, html) and captcha_retries < max_captcha_retries:
            captcha_retries += 1
            print(f"\n   ⛔ 检测到验证码（第 {captcha_retries}/{max_captcha_retries} 次）")
            print(f"   请在浏览器中手动完成验证")
            print(f"   完成后回到终端按 Enter 继续")

            input("   → 按 Enter 继续...")
            time.sleep(2)

            # 先检查 URL 是否已跳转
            final_url = page.url
            if not _is_captcha_page(final_url):
                html = page.content()
                print(f"   ✅ 验证通过，URL 已跳转")
                break

            # URL 没变 → reload 让服务器用验证 token 放行
            print(f"   URL 未变，尝试 reload...")
            page.reload(wait_until="networkidle", timeout=20000)
            time.sleep(3)
            html = page.content()
            final_url = page.url

            if not _is_captcha_page(final_url, html):
                print(f"   ✅ reload 后验证通过")
                break

            print(f"   ❌ reload 后仍在验证页")

        if _is_captcha_page(final_url, html):
            print(f"\n   ❌ 验证码重试 {max_captcha_retries} 次未通过，探测终止")
            page.close()
            return

        # ── 4. 确认到了搜索结果页 ──
        print(f"\n📌 3. 页面分析")
        print(f"   最终 URL: {final_url}")
        print(f"   HTML 大小: {len(html)} 字节")

        if "offer_search" in final_url or "selloffer" in final_url:
            print(f"   ✅ 搜索成功 ✅")
            # 确认到结果页了才保存 state
            browser.save_state(platform)
            print(f"   登录态已保存（后续运行自动跳过验证码）")
            _analyze_1688_dom(html, keyword)
            _save_html("1688_search", keyword, html)
        else:
            print(f"   ⚠ 未跳转到搜索结果页，实际 URL: {final_url}")
            _save_html("1688_unexpected", keyword, html)

    except Exception as e:
        print(f"\n   ❌ 异常: {e}")
        try:
            _save_html("1688_error", keyword, page.content())
        except Exception:
            pass

    finally:
        page.close()


def _analyze_1688_dom(html: str, keyword: str):
    """解析 1688 搜索页 HTML"""
    from bs4 import BeautifulSoup
    import re

    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    print(f"\n   页面标题: {title_tag.get_text(strip=True) if title_tag else '(无)'}")

    # ── 容器探测 ──
    candidates = []
    tests = [
        ("class", "offer-list-row",   ".offer-list-row"),
        ("class", "offer-list-item",  ".offer-list-item"),
        ("class", "sm-offer-item",    ".sm-offer-item"),
        ("class", "grid-item",        ".grid-item"),
        ("class", "result-item",      ".result-item"),
        ("class", "offer-card",       ".offer-card"),
        ("class", "product-item",     ".product-item"),
        ("class", "list-item",        ".list-item"),
        ("class", "item",             ".item"),
        ("class", "card",             ".card"),
        ("id",    "offer-list",       "#offer-list"),
        ("id",    "search-content",   "#search-content"),
        ("id",    "list-view",        "#list-view"),
        ("tag",   "li",               "li"),
    ]

    for match_type, value, selector in tests:
        if match_type == "class":
            els = soup.find_all(class_=value)
        elif match_type == "id":
            el = soup.find(id=value)
            els = [el] if el else []
        elif match_type == "tag":
            els = soup.find_all(value)
        else:
            els = []

        if els:
            if selector == "li" and len(els) < 3:
                continue
            candidates.append((selector, len(els)))

    if candidates:
        print(f"\n📌 4. 候选容器:")
        for sel, count in candidates:
            print(f"   {sel} → {count} 个")
    else:
        print(f"\n📌 4. 无已知容器，class 分布（前 30）:")
        classes = {}
        for el in soup.find_all(class_=True):
            for c in el.get("class", []):
                classes[c] = classes.get(c, 0) + 1
        for c, n in sorted(classes.items(), key=lambda x: -x[1])[:30]:
            print(f"   .{c}: {n}")
        return

    # ── 提取前 3 个商品 ──
    best_sel = candidates[0][0]
    print(f"\n📌 5. 前 3 个商品（容器: {best_sel}）")

    if best_sel.startswith("."):
        items = soup.find_all(class_=best_sel[1:])
    elif best_sel.startswith("#"):
        el = soup.find(id=best_sel[1:])
        items = el.find_all(["div", "li", "a"], recursive=False) if el else []
    elif best_sel == "li":
        items = soup.find_all("li")
    else:
        items = []

    for idx, item in enumerate(items[:3]):
        _extract_item(item, idx + 1)


def _extract_item(item, idx: int):
    """从单个商品元素中提取字段"""
    import re

    print(f"\n   --- 商品 {idx} ---")

    # 标题 + 链接
    title_el, link = None, None
    for a in item.find_all("a", href=True):
        txt = a.get_text(strip=True)
        if txt and len(txt) > 5:
            title_el = a
            link = a["href"]
            break

    if title_el:
        print(f"   标题: {title_el.get_text(strip=True)[:80]}")
    else:
        print(f"   标题: (未找到)")

    if link:
        print(f"   链接: {link[:150]}")

    # 价格
    price_text = None
    price_tag = None
    for el in item.find_all(["span", "div", "strong", "em"]):
        txt = el.get_text(strip=True)
        if re.search(r'[¥￥]?\d+\.?\d*', txt):
            price_text = txt[:30]
            price_tag = f"<{el.name} class=\"{' '.join(el.get('class', []))}\">"
            break

    if price_text:
        print(f"   价格: {price_text}")
        if price_tag:
            print(f"   价格标签: {price_tag}")

    # 店铺
    for sel in ["[class*='company']", "[class*='shop']", "[class*='seller']",
                "[class*='store']", "[class*='supplier']"]:
        s = item.select_one(sel)
        if s and s.get_text(strip=True):
            print(f"   店铺: {s.get_text(strip=True)[:30]}")
            print(f"   店铺标签: <{s.name} class=\"{' '.join(s.get('class', []))}\">")
            break

    # 销量
    for sel in ["[class*='deal']", "[class*='sale']", "[class*='count']",
                "[class*='volume']", "[class*='order']", "[class*='trade']"]:
        s = item.select_one(sel)
        if s and s.get_text(strip=True):
            print(f"   销量: {s.get_text(strip=True)[:30]}")
            break

    # 图片
    img = item.find("img")
    if img and img.get("src"):
        print(f"   图片: {img['src'][:100]}")

    links = item.find_all("a", href=True)
    imgs = item.find_all("img")
    print(f"   统计: {len(links)} 链接, {len(imgs)} 图片")


# ═══════════════════════════════════════════════════════════════
#  ZKH 探测
# ═══════════════════════════════════════════════════════════════

# WAF 遮罩移除脚本（在页面加载前注入）
WAF_REMOVE_JS = """
(function() {
    const observer = new MutationObserver(function(mutations) {
        for (const m of mutations) {
            for (const node of m.addedNodes) {
                if (node.nodeType === 1 && (node.id === 'waf_nc_block' || node.querySelector && node.querySelector('#waf_nc_block'))) {
                    const target = node.id === 'waf_nc_block' ? node : node.querySelector('#waf_nc_block');
                    if (target) {
                        target.style.display = 'none';
                        target.style.pointerEvents = 'none';
                        // 也移除蒙层的父级遮挡
                        if (target.parentElement) {
                            target.parentElement.style.pointerEvents = 'auto';
                        }
                    }
                }
            }
        }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    // 立即检查是否已存在
    const existing = document.getElementById('waf_nc_block');
    if (existing) {
        existing.style.display = 'none';
        existing.style.pointerEvents = 'none';
    }
})();
"""


def _probe_zkh(browser, keyword: str):
    print(f"\n{'='*60}")
    print(f"🔍 震坤行 (ZKH) 平台探测")
    print(f"{'='*60}")

    platform = "zkh"

    # ── 1. 登录 ──
    print(f"\n📌 1. 登录状态")
    if browser.has_state(platform):
        print(f"   已保存 ✅")
    else:
        browser.login(platform, "https://www.zkh.com/",
                      check_logged_in=lambda p: "退出" in p.content() or "我的" in p.content())

    # ── 2. 加载主页 + 注入 WAF 移除 ──
    print(f"\n📌 2. 加载主页 + 预移除 WAF 遮罩")

    # 创建 context 时预注入 WAF 移除脚本
    browser._close_context()
    browser._ensure_context(platform)
    page = browser._context.new_page()
    page.add_init_script(WAF_REMOVE_JS)

    intercepted_apis = []
    captured_search = []

    def on_response(resp):
        url = resp.url
        if "servezkhApi" in url and resp.status < 400:
            entry = {"url": url, "status": resp.status, "method": resp.request.method}
            intercepted_apis.append(entry)
            if "search" in url.lower():
                try:
                    data = resp.json()
                    captured_search.append({"url": url, "data": data})
                except Exception:
                    pass

    page.on("response", on_response)

    try:
        page.goto("https://www.zkh.com/", wait_until="networkidle", timeout=25000)
        print(f"   主页已加载: {page.url}")
        print(f"   WAF 遮罩已移除")

    except Exception as e:
        print(f"   主页加载异常: {e}")

    # ── 3. 通过 JS 注入搜索 ──
    print(f"\n📌 3. JS 注入搜索: {keyword}")

    try:
        # 3a. JS 设置搜索框值
        result = page.evaluate(f"""
            () => {{
                const input = document.querySelector('input[placeholder*="请输入"]');
                if (!input) return {{ found: false, html: document.body.innerHTML.substring(0, 500) }};

                // 设置值
                const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                    window.HTMLInputElement.prototype, 'value'
                ).set;
                nativeInputValueSetter.call(input, '{keyword}');

                // 触发 React/Vue 的事件绑定
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));

                return {{ found: true, value: input.value }};
            }}
        """)

        if result.get("found"):
            print(f"   输入框已填值: '{result.get('value', '')}'")
        else:
            print(f"   ❌ 未找到搜索框")
            print(f"   HTML 片段: {result.get('html', '')[:200]}")
            page.close()
            return

        # 3b. 等搜索建议出现（如果有）
        time.sleep(2)

        # 3c. 尝试搜索建议点击
        suggested = False
        for sel in ["[class*='suggest']", ".search-suggestion", "[class*='dropdown']"]:
            try:
                items = page.locator(sel).first
                if items.is_visible(timeout=2000):
                    # 点击第一条建议
                    first_item = page.locator(f"{sel} li, {sel} div").first
                    first_item.click(timeout=2000)
                    print(f"   点击搜索建议: {sel}")
                    suggested = True
                    break
            except Exception:
                continue

        if not suggested:
            # 按回车
            page.keyboard.press("Enter")
            print(f"   无搜索建议，回车搜索")

        # 3d. 等页面跳转 + API
        page.wait_for_load_state("networkidle", timeout=20000)
        time.sleep(3)
        final_url = page.url
        print(f"   搜索结果 URL: {final_url}")

        # 额外等待异步请求
        time.sleep(2)

    except Exception as e:
        print(f"   ❌ 搜索异常: {e}")

    page.close()

    # ── 4. 分析 API ──
    print(f"\n📌 4. 拦截到的 servezkhApi 请求 ({len(intercepted_apis)} 个)")

    if not intercepted_apis:
        print(f"   无")
        return

    # 分组：搜索类 vs 其他
    search_apis = [r for r in intercepted_apis if "search" in r["url"].lower()]
    other_apis = [r for r in intercepted_apis if "search" not in r["url"].lower()]

    if search_apis:
        print(f"\n   🔍 搜索相关 API ({len(search_apis)} 个):")
        for r in search_apis:
            print(f"     ✅ [{r['status']}] {r['method']} {r['url'][:160]}")
    if other_apis:
        print(f"\n   其他 API ({len(other_apis)} 个):")
        for r in other_apis[:8]:
            print(f"     ✅ [{r['status']}] {r['method']} {r['url'][:120]}")

    # ── 5. 搜索 API JSON ──
    print(f"\n📌 5. 搜索 API 响应内容")

    if captured_search:
        for entry in captured_search:
            print(f"\n   API: {entry['url'][:120]}")
            data_str = json.dumps(entry['data'], ensure_ascii=False, indent=2)
            print(f"   响应 JSON (前 3000 字):")
            print(data_str[:3000])
            _save_json("zkh_search_api", keyword, entry['data'])
    else:
        print(f"   未捕获到搜索 API 响应")

        # ── 5b. 页面内容检查 ──
        print(f"\n📌 5b. 检查搜索后页面")

        page2 = browser._context.new_page()
        page2.add_init_script(WAF_REMOVE_JS)
        page2.goto("https://www.zkh.com/", wait_until="networkidle", timeout=15000)

        # 检查 SPA 状态
        spa_data = page2.evaluate("""
            () => {
                // 尝试提取 SPA 的运行时数据
                const data = {};
                if (window.__NUXT__) data.nuxt = JSON.stringify(window.__NUXT__).substring(0, 500);
                if (window.__INITIAL_STATE__) data.state = JSON.stringify(window.__INITIAL_STATE__).substring(0, 500);
                if (window.__NEXT_DATA__) data.next = JSON.stringify(window.__NEXT_DATA__).substring(0, 500);
                data.html = document.title;
                return data;
            }
        """)
        print(f"   页面标题: {spa_data.get('html', '(无)')}")
        for k, v in spa_data.items():
            if k != "html" and v:
                print(f"   {k}: {v[:200]}")

        page2.close()

        # ── 5c. hash 路由尝试 ──
        print(f"\n📌 5c. hash 路由搜索尝试")
        page3 = browser._context.new_page()
        page3.add_init_script(WAF_REMOVE_JS)
        page3.goto("https://www.zkh.com/", wait_until="networkidle", timeout=15000)

        def on_resp2(resp):
            if "servezkhApi/search" in resp.url and resp.status < 400:
                try:
                    captured_search.append({"url": resp.url, "data": resp.json()})
                except Exception:
                    pass

        page3.on("response", on_resp2)
        page3.evaluate(f"location.hash = '#/search?keyword={keyword.split()[0]}'")
        time.sleep(5)
        page3.close()

        if captured_search:
            print(f"   ✅ hash 路由后捕获到搜索 API:")
            for entry in captured_search:
                print(f"   {entry['url'][:120]}")
                print(json.dumps(entry['data'], ensure_ascii=False, indent=2)[:2000])
                _save_json("zkh_search_api", keyword, entry['data'])
        else:
            print(f"   ❌ hash 路由仍未触发搜索 API")

    # ── 6. 保存首页 HTML ──
    print(f"\n📌 6. 页面快照")
    page4 = browser._context.new_page()
    page4.add_init_script(WAF_REMOVE_JS)
    page4.goto("https://www.zkh.com/", wait_until="networkidle", timeout=15000)
    html = page4.content()
    page4.close()
    _save_html("zkh_homepage", keyword, html)

    # 最终统计
    print(f"\n📌 7. 汇总")
    all_search_urls = [r["url"] for r in search_apis] if search_apis else []
    print(f"   搜索 API 候选:")
    if all_search_urls:
        for u in all_search_urls:
            print(f"     {u}")
    else:
        print(f"     (未触发)")


# ═══════════════════════════════════════════════════════════════
#  工具
# ═══════════════════════════════════════════════════════════════

def _save_html(prefix: str, keyword: str, html: str):
    out_dir = PROJECT_ROOT / "output" / "probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}_{keyword[:20].replace(' ', '_')}.html"
    path = out_dir / name
    path.write_text(html[:200000], encoding="utf-8")
    print(f"   HTML 已保存: {path}")


def _save_json(prefix: str, keyword: str, data):
    out_dir = PROJECT_ROOT / "output" / "probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{prefix}_{keyword[:20].replace(' ', '_')}.json"
    path = out_dir / name
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   JSON 已保存: {path}")


# ═══════════════════════════════════════════════════════════════
#  入口
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="平台探测工具")
    parser.add_argument("platform", choices=["1688", "zkh"],
                        help="要探测的平台")
    parser.add_argument("--keyword", default="敏华 M-ZFZD-E5W3004",
                        help="搜索关键词")
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"  PageHarvest — 平台探测工具 (Probe v3)")
    print(f"{'='*60}")
    print(f"  平台: {args.platform}")
    print(f"  关键词: {args.keyword}")

    with BrowserManager(headless=False) as browser:
        if args.platform == "1688":
            _probe_1688(browser, args.keyword)
        elif args.platform == "zkh":
            _probe_zkh(browser, args.keyword)

    print(f"\n{'='*60}")
    print(f"  探测完成")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

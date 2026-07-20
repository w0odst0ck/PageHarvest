"""
ZKH API 验证 v3
"""
import sys, json, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.browser import BrowserManager

WAF_REMOVE_JS = """
(function() {
    const observer = new MutationObserver(function(mutations) {
        for (const m of mutations) {
            for (const node of m.addedNodes) {
                if (node.nodeType === 1 && (node.id === 'waf_nc_block' || node.querySelector && node.querySelector('#waf_nc_block'))) {
                    const target = node.id === 'waf_nc_block' ? node : node.querySelector('#waf_nc_block');
                    if (target) { target.style.display = 'none'; target.style.pointerEvents = 'none'; }
                }
            }
        }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    const existing = document.getElementById('waf_nc_block');
    if (existing) { existing.style.display = 'none'; existing.style.pointerEvents = 'none'; }
})();
"""

keyword = "敏华"

with BrowserManager(headless=False) as browser:
    print(f"🚀 启动浏览器...")
    browser._close_context()
    browser._ensure_context('zkh')

    # 在 context 层注入 WAF 移除（所有页面生效）
    browser._context.add_init_script(WAF_REMOVE_JS)

    captured_search = []
    all_apis = set()

    def on_response(resp):
        if resp.status < 400 and "servezkhApi" in resp.url:
            all_apis.add(resp.url[:120])
            if "search" in resp.url.lower():
                try:
                    data = resp.json()
                    captured_search.append({"url": resp.url, "data": data})
                    print(f"\n  🔍 搜索 API: {resp.url[:100]}")
                except Exception:
                    pass

    page = browser._context.new_page()
    page.on("response", on_response)

    page.goto("https://www.zkh.com/", wait_until="networkidle", timeout=25000)
    print(f"\n📌 主页已加载: {page.url}")

    # ====== 诊断：搜索框附近结构 ======
    print(f"\n📌 搜索框诊断:")
    diag = page.evaluate("""
        () => {
            const input = document.querySelector('input[placeholder*="请输入"]');
            if (!input) return { found: false };

            const parent = input.parentElement;
            const parentHTML = parent ? parent.innerHTML.substring(0, 2000) : '';

            // 附近的按钮
            const buttons = [];
            parent.querySelectorAll('button, a, [role="button"], .el-button').forEach(b => {
                buttons.push({
                    tag: b.tagName,
                    text: (b.textContent || '').trim().substring(0, 20),
                    class: (b.className || '').substring(0, 60),
                    visible: b.offsetParent !== null,
                });
            });

            return {
                found: true,
                inputId: input.id,
                inputClass: input.className.substring(0, 80),
                parentTag: parent ? parent.tagName : '',
                parentClass: parent ? (parent.className || '').substring(0, 80) : '',
                buttons: buttons,
                parentHTML: parentHTML,
            };
        }
    """)

    if diag.get("found"):
        print(f"   input id: {diag.get('inputId', '(无)')}")
        print(f"   input class: {diag.get('inputClass', '(无)')}")
        print(f"   父容器: <{diag.get('parentTag', '')} class=\"{diag.get('parentClass', '')}\">")
        if diag.get("buttons"):
            for b in diag["buttons"]:
                print(f"   附近按钮: <{b['tag']}> text=\"{b['text']}\" visible={b['visible']}")
        else:
            print(f"   搜索框附近无按钮元素")
    else:
        print(f"   ❌ 未找到搜索框")
        page.close()
        exit(1)

    # ====== 方式 1: 点搜索按钮 ======
    print(f"\n{'='*50}")
    print(f"📌 方式 1: 填搜索框 + 点搜索按钮")

    page.evaluate(f"""
        () => {{
            const input = document.querySelector('input[placeholder*="请输入"]');
            if (!input) return;
            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            s.call(input, '{keyword}');
            input.dispatchEvent(new Event('input', {{bubbles: true}}));
            input.dispatchEvent(new Event('change', {{bubbles: true}}));
            // 额外触发 keyup
            input.dispatchEvent(new KeyboardEvent('keyup', {{key: 'Enter', bubbles: true}}));
        }}
    """)
    time.sleep(2)

    # 尝试点击所有可见的附近按钮
    clicked = False
    for sel in [
        "input[type='submit']",
        "button[type='submit']",
        "button:not([type])",
        "[class*='search-btn']",
        "[class*='searchBtn']",
        "[class*='search-button']",
        "button",
        "a[class*='search']",
    ]:
        try:
            btns = page.locator(sel).all()
            for btn in btns:
                if btn.is_visible(timeout=500):
                    txt = btn.text_content() or ""
                    if any(x in txt.lower() for x in ["搜索", "搜", "查找", "go", "找"]):
                        print(f"   找到搜索按钮: <{sel}> text=\"{txt[:20]}\"")
                        btn.click()
                        clicked = True
                        break
            if clicked:
                break
        except Exception:
            continue

    if not clicked:
        print(f"   未找到搜索按钮，按回车")
        page.keyboard.press("Enter")

    time.sleep(5)
    print(f"   当前 URL: {page.url}")

    if captured_search:
        print(f"\n✅ 方式 1 成功!")
        _save(captured_search)
        page.close()
        exit(0)

    # ====== 方式 2: 逐字输入 ======
    print(f"\n{'='*50}")
    print(f"📌 方式 2: 清空后逐字真实输入")
    input_box = page.locator("input[placeholder*='请输入']").first
    input_box.click()
    input_box.fill("")
    time.sleep(0.3)
    # 逐字输入
    for ch in keyword:
        input_box.type(ch, delay=150)
    time.sleep(3)
    page.keyboard.press("Enter")
    time.sleep(5)
    print(f"   当前 URL: {page.url}")

    if captured_search:
        print(f"\n✅ 方式 2 成功!")
        _save(captured_search)
        page.close()
        exit(0)

    # ====== 收集所有 API ======
    print(f"\n{'='*50}")
    print(f"📌 页面所有 servezkhApi 调用:")
    seen = set()
    for url in sorted(all_apis):
        if url not in seen:
            seen.add(url)
            print(f"   {url}")

    if not captured_search:
        print(f"\n❌ 所有方式均未触发搜索 API")

    page.close()

print(f"\n测试完成")


def _save(data):
    path = PROJECT_ROOT / "output" / "zkh_api_result.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"   已保存: {path}")

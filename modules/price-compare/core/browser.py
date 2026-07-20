"""
Playwright 浏览器管理器（单例模式）

统一管理浏览器生命周期，提供两种搜索模式：
  - render_mode: 打开页面 → 等待渲染 → 返回 HTML
  - api_mode:    打开页面 → 拦截 API 响应 → 返回 JSON

单例设计：多个平台共用同一个浏览器实例，避免反复启动/关闭。
"""

import json
import time
import atexit
from pathlib import Path
from typing import Optional, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = PROJECT_ROOT / "cookies"

# ── 单例状态 ──
_playwright = None
_browser = None
_ref_count = 0


def _cleanup():
    global _playwright, _browser
    if _browser:
        try:
            _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright:
        try:
            _playwright.stop()
        except Exception:
            pass
        _playwright = None


atexit.register(_cleanup)

# ── Stealth 脚本：隐藏 headless 特征 ──
STEALTH_JS = """
// 1. 隐藏 webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. 模拟 plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// 3. 模拟 languages
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en'],
});

// 4. chrome.runtime
window.chrome = { runtime: {} };

// 5. permissions query 覆盖
const _origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : _origQuery(parameters)
);
"""


class BrowserManager:
    """
    Playwright 浏览器管理器（单例）。

    用法：
        with BrowserManager() as browser:
            html = browser.search_render(url, platform="1688")
            data = browser.search_api(url, api_pattern="/api/v1/search", platform="zkh")
            browser.switch_platform("zkh")
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._context = None
        self._stealth_applied = False

    # ── 生命周期 ──

    def __enter__(self):
        global _playwright, _browser, _ref_count
        from playwright.sync_api import sync_playwright

        if _playwright is None:
            _playwright = sync_playwright().start()
        if _browser is None:
            _browser = _playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
        _ref_count += 1
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        global _ref_count
        self._close_context()
        _ref_count -= 1

    @staticmethod
    def shutdown():
        global _playwright, _browser, _ref_count
        _ref_count = 0
        _cleanup()

    # ── 上下文管理 ──

    def _state_path(self, platform: str) -> Path:
        return STATE_DIR / f"playwright_state_{platform}.json"

    def _ensure_context(self, platform: str, stealth: bool = True):
        """
        创建或复用 browser context。

        Args:
            platform: 平台标识
            stealth:   是否注入 stealth 脚本（默认 True，针对 1688 等检测站）
        """
        global _browser
        if self._context:
            return
        if _browser is None:
            raise RuntimeError("BrowserManager 未启动，请使用 with 语句")

        state_file = self._state_path(platform)
        kwargs = {
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
        }
        if state_file.exists():
            kwargs["storage_state"] = str(state_file)
        self._context = _browser.new_context(**kwargs)

        # 注入 stealth 脚本至所有页面
        if stealth:
            self._context.add_init_script(STEALTH_JS)

    def _close_context(self):
        if self._context:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None

    def new_page(self, platform: str = "", stealth: bool = True):
        """创建新页面（自动 ensure_context + stealth）"""
        self._ensure_context(platform, stealth=stealth)
        return self._context.new_page()

    def save_state(self, platform: str):
        if not self._context:
            return
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state = self._context.storage_state()
        path = self._state_path(platform)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def has_state(self, platform: str) -> bool:
        return self._state_path(platform).exists()

    def switch_platform(self, platform: str):
        """关闭当前 context，创建新 context（加载目标平台 storage state）"""
        self._close_context()
        self._ensure_context(platform)

    # ── 登录辅助 ──

    def login(self, platform: str, login_url: str,
              check_logged_in: Optional[Callable] = None,
              timeout: int = 300):
        """打开浏览器让用户手动登录，登录态自动持久化。"""
        page = self.new_page(platform)

        page.goto(login_url, wait_until="networkidle")

        if check_logged_in and check_logged_in(page):
            print(f"[{platform}] 检测到已登录，跳过")
            page.close()
            self.save_state(platform)
            return

        print(f"\n✦ 请在打开的浏览器中登录 {platform}")
        print(f"  登录后回到终端，按 Enter 继续...")
        print(f"  超时: {timeout} 秒\n")

        deadline = time.time() + timeout
        logged_in = False
        while time.time() < deadline:
            try:
                if check_logged_in and check_logged_in(page):
                    logged_in = True
                    break
            except Exception:
                pass
            time.sleep(2)

        page.close()

        if logged_in:
            self.save_state(platform)
            print(f"[{platform}] 登录态已保存")
        else:
            print(f"[{platform}] ⚠ 未检测到登录态")

    # ── 滑块等待 ──

    def wait_for_captcha_solve(self, page, timeout: int = 120) -> bool:
        """
        检测到滑块验证码时进入等待模式，让用户手动滑动验证。
        回到终端按 Enter 继续，或等待 timeout 秒后退出。

        Returns:
            True 表示验证通过，False 表示超时
        """
        print(f"\n⛔ 检测到滑块/验证码")
        print(f"   请在浏览器中手动完成验证...")
        print(f"   完成后回到终端按 Enter 继续（超时: {timeout}s）\n")

        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                html = page.content()
                if "滑块" not in html and "滑动" not in html and "验证码" not in html:
                    print(f"   验证通过 ✅")
                    return True
            except Exception:
                pass
            time.sleep(1)

        print(f"   验证超时 ⏰")
        return False

    # ── API 拦截模式 ──

    def search_api(self, url: str, api_pattern: str, platform: str,
                   timeout: int = 30, stealth: bool = True) -> dict:
        """
        API 拦截模式：打开页面 → 拦截匹配的 API 响应 → 返回 JSON。

        Returns:
            {"success": bool, "data": dict|None, "error": str|None,
             "status": int|None, "page_url": str|None}
        """
        page = self.new_page(platform, stealth=stealth)

        result = {"success": False, "data": None, "error": None,
                  "status": None, "page_url": None}

        try:
            with page.expect_response(
                lambda resp: api_pattern in resp.url
                             and resp.status < 400,
                timeout=timeout * 1000
            ) as response_info:
                page.goto(url, wait_until="domcontentloaded",
                          timeout=timeout * 1000)

            response = response_info.value
            result["status"] = response.status
            result["page_url"] = page.url

            if response.ok:
                try:
                    result["data"] = response.json()
                    result["success"] = True
                except Exception as e:
                    result["error"] = f"JSON 解析失败: {e}"
            else:
                result["error"] = f"API 返回 {response.status}"

        except Exception as e:
            result["error"] = str(e)

        finally:
            page.close()

        return result

    # ── 渲染模式 ──

    def search_render(self, url: str, platform: str,
                      wait_selector: Optional[str] = None,
                      wait_timeout: int = 30,
                      stealth: bool = True) -> dict:
        """
        渲染模式：打开页面 → 等 JS 渲染完成 → 返回 HTML。

        Returns:
            {"success": bool, "html": str|None, "error": str|None,
             "url": str|None, "blocked": str|None}
        """
        page = self.new_page(platform, stealth=stealth)

        result = {"success": False, "html": None, "error": None,
                  "url": None, "blocked": None}

        try:
            if wait_selector:
                page.goto(url, wait_until="domcontentloaded",
                          timeout=wait_timeout * 1000)
                page.wait_for_selector(wait_selector,
                                       timeout=wait_timeout * 1000)
            else:
                page.goto(url, wait_until="networkidle",
                          timeout=wait_timeout * 1000)

            result["url"] = page.url
            html = page.content()

            blocked = self._check_blocked(html)
            if blocked:
                result["blocked"] = blocked
                result["html"] = html
            else:
                result["success"] = True
                result["html"] = html

        except Exception as e:
            result["error"] = str(e)
            try:
                result["url"] = page.url
            except Exception:
                pass

        finally:
            page.close()

        return result

    # ── 交互式搜索（主页搜索框版） ──

    def search_via_homepage(self, homepage_url: str, platform: str,
                            keyword: str,
                            search_input_selector: str = "",
                            search_btn_selector: str = "",
                            result_selector: str = "",
                            submit_by_enter: bool = True,
                            timeout: int = 30) -> dict:
        """
        交互式搜索：加载主页 → 找到搜索框 → 输入关键词 → 触发搜索 → 等结果。

        适用于 1688 等直接访问搜索 URL 会被拦截的站点。
        这种流程更接近真实用户，风控概率更低。

        Args:
            homepage_url: 主页 URL
            platform: 平台标识
            keyword: 搜索关键词
            search_input_selector: 搜索框 CSS 选择器
            search_btn_selector: 搜索按钮 CSS 选择器（submit_by_enter=False 时用）
            result_selector: 结果容器的 CSS 选择器（用于等待渲染）
            submit_by_enter: True=输入后回车；False=点搜索按钮
            timeout: 等待结果超时

        Returns:
            {"success": bool, "html": str|None, "error": str|None,
             "url": str|None, "blocked": str|None}
        """
        page = self.new_page(platform, stealth=True)

        result = {"success": False, "html": None, "error": None,
                  "url": None, "blocked": None}

        try:
            # 1. 打开主页
            page.goto(homepage_url, wait_until="networkidle",
                      timeout=timeout * 1000)

            # 2. 找搜索框
            if search_input_selector:
                page.wait_for_selector(search_input_selector,
                                       timeout=timeout * 1000)
                search_box = page.locator(search_input_selector)
                search_box.click()
                search_box.fill(keyword)
            else:
                # 无指定选择器时，尝试找 input[type=text] 或 placeholder 含搜索/关键词的
                for sel in ["input[placeholder*='搜索']",
                            "input[placeholder*='关键词']",
                            "input.search-keyword",
                            "#search-input",
                            ".search-box input",
                            "input[type=text]"]:
                    try:
                        box = page.locator(sel).first
                        if box.is_visible():
                            box.click()
                            box.fill(keyword)
                            break
                    except Exception:
                        continue

            time.sleep(1)

            # 3. 触发搜索
            if submit_by_enter:
                page.keyboard.press("Enter")
            else:
                if search_btn_selector:
                    page.locator(search_btn_selector).click()
                else:
                    # 尝试多种按钮选择器
                    for sel in ["button.search-btn", ".search-button",
                                "input[type=submit]", "button[type=submit]"]:
                        try:
                            btn = page.locator(sel).first
                            if btn.is_visible():
                                btn.click()
                                break
                        except Exception:
                            continue
                    else:
                        page.keyboard.press("Enter")

            # 4. 等结果
            if result_selector:
                page.wait_for_selector(result_selector,
                                       timeout=timeout * 1000)
            else:
                page.wait_for_load_state("networkidle",
                                         timeout=timeout * 1000)

            result["url"] = page.url
            html = page.content()

            blocked = self._check_blocked(html)
            if blocked:
                result["blocked"] = blocked
                result["html"] = html
            else:
                result["success"] = True
                result["html"] = html

        except Exception as e:
            result["error"] = str(e)
            try:
                result["url"] = page.url
            except Exception:
                pass

        finally:
            page.close()

        return result

    # ── 工具 ──

    @staticmethod
    def _check_blocked(html: str) -> Optional[str]:
        if not html:
            return "空页面"
        text = html.lower()
        keywords = [
            "验证码", "滑块", "人机验证", "captcha", "verify",
            "访问受限", "请求太频繁", "身份验证",
            "很抱歉", "访问出错", "系统检测到",
            "请滑动", "拖动滑块", "安全验证",
        ]
        for kw in keywords:
            if kw.lower() in text:
                return kw
        return None

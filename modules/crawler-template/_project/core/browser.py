"""
Crawler Template — Playwright 浏览器管理器

职责：
  - 浏览器实例的启动/关闭/复用
  - Cookie 持久化（手动登录 → 保存 → 自动加载）
  - 页面默认设置（超时/视口/反爬头）

用法：
    with BrowserManager(headless=True) as bm:
        page = bm.new_page("https://example.com")
        # ... 干活 ...

首次运行会弹出浏览器让你手动登录，登录后 Cookie 持久化到 data/cookies.json，
后续运行静默化。
"""

import json
import logging
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

# ── 默认配置 ──────────────────────────────────────────
DEFAULT_COOKIE_PATH = Path("data/cookies.json")
DEFAULT_TIMEOUT = 30_000  # ms
STEALTH_JS = """
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    window.chrome = { runtime: {} };
"""
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)


class BrowserManager:
    """Playwright 浏览器单例管理器

    Attributes:
        headless: 有头/无头模式。设为 False 用于首次登录、排障
        cookie_path: Cookie 持久化路径
        login_url: 登录页 URL，用于 wait_for_login()
    """

    def __init__(self, headless: bool = True,
                 cookie_path: str | Path = DEFAULT_COOKIE_PATH,
                 login_url: str = ""):
        self.headless = headless
        self.cookie_path = Path(cookie_path)
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        self.login_url = login_url

        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    # ── 生命周期 ────────────────

    def start(self):
        """启动浏览器，创建共享上下文"""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=DEFAULT_UA,
        )
        self._context.set_default_timeout(DEFAULT_TIMEOUT)
        logger.info("浏览器已启动 (headless=%s)", self.headless)
        self._load_cookies()
        return self

    def close(self):
        if self._context:
            self._context.close()
            self._context = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
        logger.info("浏览器已关闭")

    def __enter__(self):
        return self.start()

    def __exit__(self, *args):
        self.close()

    def restart(self, headless: bool | None = None):
        """重启浏览器，可选切换有头/无头模式"""
        self.close()
        if headless is not None:
            self.headless = headless
        return self.start()

    # ── 页面 ────────────────

    def new_page(self, url: str = "", wait_until: str = "load") -> Page:
        """创建新页面（使用共享上下文），注入反爬脚本

        Args:
            url: 可选，打开后跳转到该 URL
            wait_until: 导航等待条件。
                'load' 安全选项，等所有资源加载完。
                'domcontentloaded' 更快，适合不需要图片/CSS的页面。
                遇到长连接页面不要用 'networkidle'。

        Returns:
            Page 对象
        """
        assert self._context is not None, "浏览器未启动，请先调用 start()"
        page = self._context.new_page()
        page.add_init_script(STEALTH_JS)
        page.evaluate(STEALTH_JS)
        if url:
            page.goto(url, wait_until=wait_until)
        return page

    # ── Cookie ────────────────

    def _load_cookies(self):
        """从 JSON 文件加载 Cookie"""
        if not self.cookie_path.exists():
            logger.info("Cookie 文件不存在，需要手动登录: %s", self.cookie_path)
            return
        with open(self.cookie_path) as f:
            cookies = json.load(f)
        self._context.add_cookies(cookies)
        logger.info("已加载 %d 条 Cookie", len(cookies))

    def save_cookies(self):
        """将当前上下文所有 Cookie 保存到 JSON 文件"""
        assert self._context is not None
        cookies = self._context.cookies()
        with open(self.cookie_path, "w") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logger.info("已保存 %d 条 Cookie", len(cookies))

    def delete_cookies(self):
        """删除 Cookie 文件（重新登录时用）"""
        if self.cookie_path.exists():
            self.cookie_path.unlink()
            logger.info("Cookie 文件已删除")

    # ── 登录辅助 ────────────────

    def wait_for_login(self, url: str = "", timeout_s: int = 300) -> bool:
        """打开登录页，等待用户手动登录

        Args:
            url: 登录页 URL，默认用 self.login_url
            timeout_s: 最长等待秒数

        Returns:
            True=登录成功, False=超时
        """
        url = url or self.login_url
        assert url, "需要指定登录页 URL"

        page = self.new_page(url)
        logger.info("请在打开的浏览器中完成登录（超时 %ds）", timeout_s)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if "login" not in page.url.lower():
                self.save_cookies()
                page.close()
                logger.info("登录成功，Cookie 已保存")
                return True
            time.sleep(2)
        page.close()
        logger.warning("登录超时")
        return False

    def check_login(self, check_url: str = "") -> bool:
        """检查当前 Cookie 是否有效（通过检测是否跳转到登录页判断）

        Args:
            check_url: 用于检查的 URL，默认用 login_url 对应的首页

        Returns:
            True=Cookie 有效, False=已过期
        """
        target = check_url or (self.login_url.rsplit("/login", 1)[0] if self.login_url else "https://example.com")
        page = self.new_page(target)
        time.sleep(3)
        valid = "login" not in page.url.lower()
        page.close()
        return valid

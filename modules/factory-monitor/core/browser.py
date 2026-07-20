"""
1688 Factory Monitor — Playwright 浏览器管理器

职责：
  - 浏览器实例的启动/关闭/复用
  - Cookie 持久化（手动登录 → 保存 → 自动加载）
  - 页面默认设置（超时/视口/反爬头）
"""

import json
import logging
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)

COOKIE_PATH = Path("data/cookies.json")
DEFAULT_TIMEOUT = 30_000  # ms


class BrowserManager:
    """Playwright 浏览器单例管理器"""

    def __init__(self, headless: bool = True,
                 cookie_path: str | Path = COOKIE_PATH):
        self.headless = headless
        self.cookie_path = Path(cookie_path)
        self.cookie_path.parent.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    # ── 生命周期 ──

    def start(self):
        """启动浏览器（无头/有头），创建共享上下文"""
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )
        # 创建共享上下文，所有页面共用
        self._context = self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
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

    # ── 页面 ──

    def new_page(self, url: str = "", wait_until: str = "load") -> Page:
        """创建新页面（使用共享上下文），设置默认参数

        Args:
            url: 可选，打开后跳转到该 URL
            wait_until: 导航等待条件，默认 'load'。
                        如需更快可传 'domcontentloaded'，
                        遇到长连接页面不要用 'networkidle'。
        """
        assert self._context is not None, "浏览器未启动，请先调用 start()"
        page = self._context.new_page()
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
        """)
        if url:
            page.goto(url, wait_until=wait_until)
        return page

    # ── Cookie ──

    def _load_cookies(self):
        """从文件加载 Cookie 到共享上下文（如文件存在）"""
        if not self.cookie_path.exists():
            logger.info("Cookie 文件不存在，需要手动登录: %s", self.cookie_path)
            return
        with open(self.cookie_path) as f:
            cookies = json.load(f)
        self._context.add_cookies(cookies)
        logger.info("已加载 %d 条 Cookie", len(cookies))

    def save_cookies(self):
        """将共享上下文的 Cookie 保存到文件"""
        assert self._context is not None
        cookies = self._context.cookies()
        with open(self.cookie_path, "w") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)
        logger.info("已保存 %d 条 Cookie", len(cookies))

    # ── 登录辅助 ──

    def wait_for_login(self, url: str = "https://login.1688.com/",
                       timeout_s: int = 300) -> bool:
        """
        打开登录页，等待用户手动登录。
        适用于首次运行或 Cookie 过期。

        Args:
            url: 登录页 URL
            timeout_s: 超时秒数

        Returns:
            True=登录成功, False=超时
        """
        page = self.new_page(url)
        logger.info("请在打开的浏览器中完成 1688 登录（超时 %ds）", timeout_s)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if "login.1688.com" not in page.url:
                self.save_cookies()
                page.close()
                logger.info("登录成功，Cookie 已保存")
                return True
            time.sleep(2)
        page.close()
        logger.warning("登录超时")
        return False

    def check_login(self) -> bool:
        """检查当前 Cookie 是否有效"""
        page = self.new_page("https://www.1688.com/")
        time.sleep(3)
        valid = "login.1688.com" not in page.url
        page.close()
        return valid

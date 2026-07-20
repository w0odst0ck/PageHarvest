"""
共享反检测 Stealth JS 脚本

Playwright 反自动化检测的统一脚本源。
crawler-template 和 price-compare 都引用这个，不重复写。

使用：
    from lib.stealth import STEALTH_JS, DEFAULT_UA
    page.add_init_script(STEALTH_JS)
"""

STEALTH_JS = """
// 1. 隐藏 webdriver 特征
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. 模拟 plugins（真实浏览器有 5 个 plugin）
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5],
});

// 3. 设置语言
Object.defineProperty(navigator, 'languages', {
    get: () => ['zh-CN', 'zh', 'en'],
});

// 4. 模拟 chrome.runtime
window.chrome = { runtime: {} };

// 5. 覆盖 permissions query（防止被检测到 headless）
const _origQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : _origQuery(parameters)
);

// 6. 覆盖 webgl 渲染器（防止 WebGL fingerprinting）
const _getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(p) {
    if (p === 37445) return 'Intel Inc.';
    if (p === 37446) return 'Intel Iris OpenGL Engine';
    return _getParameter(p);
};
"""

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

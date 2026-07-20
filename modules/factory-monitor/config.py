"""
项目全局配置

所有硬编码常量集中在此。各模块统一 from config import xxx。
改参数只改这一个文件。
"""

from pathlib import Path

# ── 路径 ──
PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = str(PROJECT_ROOT / "data" / "monitor.db")
COOKIE_PATH = str(PROJECT_ROOT / "data" / "cookies.json")

# ── 浏览器 ──
PAGE_TIMEOUT_MS = 30_000       # 页面加载超时
PAGE_WAIT_UNTIL = "load"       # 导航等待条件: load / domcontentloaded
BROWSER_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
]
VIEWPORT = {"width": 1920, "height": 1080}
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/150.0.0.0 Safari/537.36"
)

# ── 采集延时（秒）──
WAIT_AFTER_NAV = 3.0           # 页面导航后等待渲染
WAIT_AFTER_CARD_NAV = 2.0      # 卡片/详情页导航后等待
SCROLL_WAIT = 1.5              # 滚动后等待加载
NAV_TIMEOUT_S = 15             # 单次导航超时

# ── 重试 ──
RETRY_COUNT = 2                # 失败后重试次数
RETRY_BASE_DELAY = 2.0         # 首次重试等待秒数（指数退避）

# ── 搜索 ──
DEFAULT_PAGES = 5              # 默认搜索页数
DEFAULT_ENCODING = "gbk"       # 1688 使用 gbk

# ── 过滤 ──
FILTER_THRESHOLD = 2           # 商品标题命中标签数达到此值判 active
DEFAULT_FILTER_TAGS = [        # 品类无配置时的默认过滤词
    "灯", "照明", "灯具", "LED", "光源"
]

# ── 预警 ──
DEFAULT_DROP_THRESHOLD = 0.30  # 商品数减少 ≥30% → 红色预警
DEFAULT_SURGE_THRESHOLD = 0.50 # 销量增长 ≥50% → 蓝色预警

# ── 工厂消失检测 ──
DISAPPEAR_CONSECUTIVE = 2      # 连续 N 次未出现判消失

# 全局配置

# 输入/输出路径
INPUT_FILE = "input/整单7月份询价单.xls"
OUTPUT_DIR = "output"

# Cookie 目录
COOKIE_DIR = "cookies"

# 运行模式
DRY_RUN = False
FORCE_RERUN = False

# 日志
LOG_LEVEL = "INFO"

# ============================================================
# 反爬/安全策略
# ============================================================

# 热身期：前 N 次请求用更慢的间隔，模拟"人刚开始浏览"
WARMUP_COUNT = 10
WARMUP_DELAY = (5, 8)       # 秒

# 正常请求间隔
NORMAL_DELAY = (3, 5)       # 秒

# 长暂停：每 N 次请求后插入一次
LONG_PAUSE_EVERY = 10
LONG_PAUSE = (10, 15)       # 秒

# 速率限制：每分钟不超过 N 次
MAX_RATE_PER_MIN = 15

# 重试策略：指数退避
RETRY_DELAYS = [3, 8, 20]   # 第1/2/3次重试前的等待秒数
MAX_RETRIES = 3             # 最大重试次数（超过后跳过该商品）

# 异常关键词：响应用于检测是否被风控拦截
BLOCK_KEYWORDS = [
    '验证码', '滑块', '人机验证',
    'captcha', 'verify',
    '访问受限', '请求太频繁',
    '封号', '账号异常',
]

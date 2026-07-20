"""平台名称和搜索URL模板"""

PLATFORM_NAME = "平台名称"

# 搜索URL模板，{keyword} 会被替换
SEARCH_URL = "https://example.com/search?q={keyword}"

# 请求配置
DELAY_RANGE = (2, 4)        # 请求间隔(秒)
TIMEOUT = 10                 # 超时秒数
RETRY = 2                    # 失败重试次数

# Cookie 文件路径（相对于项目根目录）
COOKIE_FILE = "cookies/xxx_cookies.txt"

# 自定义请求头
HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

# 风控拦截关键词（各平台自定义）
BLOCK_KEYWORDS = []

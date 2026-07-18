"""1688 平台配置"""

PLATFORM_NAME = "1688"

SEARCH_URL = "https://s.1688.com/selloffer/offer_search.htm?keywords={keyword}"

DELAY_RANGE = (3, 5)
TIMEOUT = 10
RETRY = 2

COOKIE_FILE = "cookies/1688_cookies.txt"

HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

# 风控拦截关键词
BLOCK_KEYWORDS = [
    '验证码', '滑块', '人机验证', 'captcha', 'verify',
    '访问受限', '请求太频繁', '身份验证',
    '很抱歉', '访问出错', '系统检测到',
]

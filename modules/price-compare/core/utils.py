"""核心工具：UA池、延时、限速、异常检测"""

import time
import random
import json
import os
import re

# 真实浏览器 UA 池（Chrome/Edge/Firefox 多版本）
USER_AGENTS = [
    # Chrome 126 (Win)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
    # Chrome 125 (Win)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
    # Chrome 124 (Win)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    # Edge 126 (Win)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edge/126.0.0.0 Safari/537.36",
    # Edge 125 (Win)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edge/125.0.0.0 Safari/537.36",
    # Firefox 128 (Win)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    # Firefox 127 (Win)
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]


class RequestTracker:
    """请求追踪器：记录已发请求数，判断是否在热身期"""

    def __init__(self):
        self.count = 0
        self.minute_bucket = time.time()
        self.minute_count = 0

    def is_warmup(self) -> bool:
        return self.count < 10  # 对应 config WARMUP_COUNT

    def should_long_pause(self) -> bool:
        return self.count > 0 and self.count % 10 == 0  # 对应 LONG_PAUSE_EVERY

    def record(self):
        self.count += 1
        now = time.time()
        if now - self.minute_bucket >= 60:
            self.minute_bucket = now
            self.minute_count = 0
        self.minute_count += 1


# 全局追踪器
_tracker = RequestTracker()


def random_ua() -> str:
    """随机返回一个 User-Agent"""
    return random.choice(USER_AGENTS)


def random_referrer(platform: str) -> str:
    """随机返回一个 Referer，模拟正常浏览路径"""
    refs = {
        '1688': [
            'https://www.1688.com/',
            'https://www.1688.com/cp/',
            'https://www.1688.com/chanpin/',
        ],
        '震坤行': [
            'https://www.zkh.com/',
            'https://www.zkh.com/category/',
        ],
    }
    pool = refs.get(platform, ['https://www.google.com/'])
    return random.choice(pool)


def adaptive_delay(warmup_delay=(5, 8), normal_delay=(3, 5),
                   long_pause_every=10, long_pause=(10, 15)):
    """
    智能延时：
    - 热身期用慢速
    - 每 N 次插入一次长暂停
    - 正常期用常规速度
    """
    if _tracker.is_warmup():
        lo, hi = warmup_delay
    elif _tracker.should_long_pause():
        lo, hi = long_pause
    else:
        lo, hi = normal_delay
    _tracker.record()
    time.sleep(random.uniform(lo, hi))


def check_blocked(html: str, keywords: list[str]) -> str | None:
    """
    检测是否被风控拦截
    返回 None 表示正常，返回匹配到的关键词表示被拦截
    """
    if not html:
        return '空响应'
    text = html.lower()
    for kw in keywords:
        if kw.lower() in text:
            return kw
    return None


def exponential_retry(func, retry_delays: list[int], *args, **kwargs):
    """
    指数退避重试
    func: 要执行的函数
    retry_delays: 每次重试前的等待时间 [3, 8, 20]
    返回: (成功=True/False, 结果, 最终异常)
    """
    last_exc = None
    for attempt, delay in enumerate(retry_delays + [0]):
        try:
            result = func(*args, **kwargs)
            return True, result, None
        except Exception as e:
            last_exc = e
            if attempt < len(retry_delays):
                time.sleep(delay)
    return False, None, last_exc


def load_cookie(path: str) -> dict:
    """从文件加载 Cookie（格式：key=value; key2=value2）"""
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read().strip()
    cookies = {}
    for pair in text.split(';'):
        if '=' in pair:
            k, v = pair.split('=', 1)
            cookies[k.strip()] = v.strip()
    return cookies


def shuffle_products(products: list[dict]) -> list[dict]:
    """打乱商品列表顺序，避免固定搜索规律"""
    shuffled = products.copy()
    random.shuffle(shuffled)
    return shuffled


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def save_json(data, path: str):
    ensure_dir(os.path.dirname(path))
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

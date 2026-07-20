"""Crawler template — utilities"""

import json
import logging
import random
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def safe_float(value: str, default: float = 0.0) -> float:
    """安全地将字符串转为 float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: str, default: int = 0) -> int:
    """安全地将字符串转为 int"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def extract_number(text: str) -> int:
    """从字符串中提取第一个数字"""
    import re
    m = re.search(r"(\d+)", text or "")
    return int(m.group(1)) if m else 0


def random_delay(min_s: float = 1.0, max_s: float = 3.0):
    """随机延时，避免频率检测"""
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
]


def random_ua() -> str:
    """返回随机 UA"""
    return random.choice(USER_AGENTS)

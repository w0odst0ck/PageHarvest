"""HTML 解析模块 —— 从搜索结果页提取商品信息"""

from bs4 import BeautifulSoup
from core.logger import get_logger

log = get_logger()


def parse(html: str) -> list[dict]:
    """
    解析搜索结果 HTML，提取商品列表

    Args:
        html: 搜索结果页 HTML

    Returns:
        [
            {"title": "敏华xxx", "price": 30.5, "url": "https://...", "shop": "xxx旗舰店"},
            ...
        ]
    """
    soup = BeautifulSoup(html, 'lxml')
    candidates = []

    # TODO: 根据平台HTML结构提取商品列表

    log.debug("", f"解析到 {len(candidates)} 个候选商品")
    return candidates

"""
平台适配器抽象基类
定义所有电商平台适配器必须实现的接口。

子类只需继承 PlatformAdapter 并实现抽象方法，
然后用 @register("平台名") 装饰即可自动注册。
"""

from abc import ABC, abstractmethod
from typing import Optional
from core.schema import UnifiedProduct, UnifiedDetail


class PlatformAdapter(ABC):
    """所有电商平台适配器必须实现此接口"""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """返回平台名称，如 '1688'、'京东'"""
        ...

    # ═══════════════ 采集 ═══════════════

    @abstractmethod
    def collect_search(self, keyword: str, page: int = 1) -> str:
        """
        采集搜索页 HTML。
        返回原始 HTML 字符串，供后续 parse_search 解析。
        """
        ...

    @abstractmethod
    def collect_detail(self, product_id: str) -> str:
        """
        采集商品详情页 HTML。
        返回原始 HTML 字符串。
        """
        ...

    # ═══════════════ 解析 ═══════════════

    @abstractmethod
    def parse_search(self, html: str, keyword: str) -> list[UnifiedProduct]:
        """
        搜索页 HTML → 统一数据结构
        """
        ...

    @abstractmethod
    def parse_detail(self, html: str) -> Optional[UnifiedDetail]:
        """
        详情页 HTML → 统一数据结构
        返回 None 表示解析失败。
        """
        ...

    # ═══════════════ URL 模板 ═══════════════

    @abstractmethod
    def search_url(self, keyword: str, page: int = 1) -> str:
        """生成搜索页 URL"""
        ...

    @abstractmethod
    def product_url(self, product_id: str) -> str:
        """生成商品详情页 URL"""
        ...

    # ═══════════════ 平台能力声明 ═══════════════

    @property
    def capabilities(self) -> set[str]:
        """
        返回该平台支持的能力集合。
        默认支持搜索页和详情页，子类可覆盖。
        """
        return {"search", "detail"}

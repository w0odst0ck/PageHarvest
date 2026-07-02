"""
平台适配器注册表
以装饰器方式注册平台，运行时按名称获取适配器实例。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from platforms.base import PlatformAdapter

_registry: dict[str, type['PlatformAdapter']] = {}


def register(name: str):
    """装饰器：将适配器类注册到注册表"""
    def decorator(cls):
        _registry[name] = cls
        return cls
    return decorator


def get_platform(name: str) -> 'PlatformAdapter':
    """工厂方法：按平台名称获取适配器实例"""
    if name not in _registry:
        available = ', '.join(_registry.keys())
        raise KeyError(
            f"未知平台: '{name}'。已注册平台: [{available}]"
        )
    return _registry[name]()


def list_platforms() -> list[str]:
    """返回所有已注册的平台名称列表"""
    return list(_registry.keys())


def get_registry():
    """返回原始注册表（用于内省）"""
    return dict(_registry)

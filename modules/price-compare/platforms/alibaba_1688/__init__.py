"""1688 平台模块"""

from . import crawler, parser, matcher
from .config import PLATFORM_NAME


def run(products: list[dict]) -> dict:
    from platforms._template import run as template_run
    return template_run(products)

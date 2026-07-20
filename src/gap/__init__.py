"""
gap/ — 商品缺口分析模块

跨平台比对 PageHarvest 选品清单与目标平台在售商品库，
找出缺失商品，输出结构化 Excel 报告供采购决策。

适用场景：
  - 震坤行选品清单 ↔ 河姆渡在售商品
  - 任意平台选品清单 ↔ 任意平台在售商品库（自定义列名）

用法：
    python -m gap.runner --fuzzy

核心文件：
    config.py    配置管理
    analyzer.py  6步分析流水线（读取→标准化→差集→模糊匹配→导出）
    runner.py    CLI 入口
"""

from gap.analyzer import (
    read_listing,
    read_inventory,
    read_csv_wizard,
    standardize_keys,
    find_gaps,
    fuzzy_verify,
    export_report,
    run_pipeline,
)
from gap.config import GapConfig

__all__ = [
    "read_listing",
    "read_inventory",
    "read_csv_wizard",
    "standardize_keys",
    "find_gaps",
    "fuzzy_verify",
    "export_report",
    "run_pipeline",
    "GapConfig",
]

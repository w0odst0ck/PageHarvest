#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快速验证：检查项目依赖和目录结构
"""
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

print("=" * 50)
print("price-compare 基建验证")
print("=" * 50)

# 1. 目录结构
expected = [
    'input', 'output/raw', 'core', 'cookies', 'docs',
    'platforms/alibaba_1688', 'platforms/zkh',
    'platforms/jd_industrial', 'platforms/gongpinhui', 'platforms/ehsy',
    'platforms/_template',
]
for d in expected:
    path = os.path.join(PROJECT_ROOT, d)
    status = 'OK' if os.path.isdir(path) else 'MISSING'
    print(f"  [{status}] {d}")

# 2. 核心文件
files = [
    'main.py', 'config.py', 'README.md', 'requirements.txt',
    'core/loader.py', 'core/exporter.py', 'core/logger.py', 'core/utils.py',
    'platforms/__init__.py',
    'platforms/alibaba_1688/__init__.py', 'platforms/alibaba_1688/config.py',
    'platforms/zkh/__init__.py', 'platforms/zkh/config.py',
    'platforms/_template/__init__.py', 'platforms/_template/config.py',
    'platforms/_template/crawler.py', 'platforms/_template/parser.py', 'platforms/_template/matcher.py',
    'docs/ARCHITECTURE.md', 'docs/HOW_TO_ADD_PLATFORM.md',
]
for f in files:
    path = os.path.join(PROJECT_ROOT, f)
    status = 'OK' if os.path.isfile(path) else 'MISSING'
    print(f"  [{status}] {f}")

# 3. 输入文件
input_path = os.path.join(PROJECT_ROOT, 'input', '整单7月份询价单.xls')
if os.path.exists(input_path):
    from core.loader import load
    products = load(input_path)
    print(f"\n  [INPUT] 整单7月份询价单.xls → {len(products)} 条商品")
else:
    print(f"\n  [INPUT] 文件缺失: {input_path}")

# 4. 平台注册表
from platforms import get_active, get_all
active = get_active()
all_p = get_all()
print(f"\n  [REGISTRY] 已注册: {len(all_p)} 个平台")
for p in all_p:
    flag = 'ACTIVE' if p['enabled'] else 'PLANNED'
    print(f"    {flag} [{p['tier']}] {p['name']} ({p['status']})")

# 5. Python 依赖
try:
    import requests
    import bs4
    import lxml
    import pandas
    import openpyxl
    import xlrd
    print(f"\n  [DEPS] 所有依赖已安装 ✓")
except ImportError as e:
    print(f"\n  [DEPS] 缺少依赖: {e}")

print(f"\n{'=' * 50}")
print("基建验证完成")
print(f"{'=' * 50}")

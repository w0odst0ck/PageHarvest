# -*- mode: python ; coding: utf-8 -*-
"""
PageHarvest 构建脚本
用法: pyinstaller build.spec
"""

import sys
from pathlib import Path

try:
    ROOT = Path(__file__).resolve().parent
except NameError:
    ROOT = Path(sys.argv[0]).resolve().parent

# 需要包含的 Python 包
PACKAGES = ['api', 'core', 'platforms', 'selection', 'gap']

# 资源文件
DATAS = []
for pkg in PACKAGES:
    src = ROOT / pkg
    if src.is_dir():
        DATAS.append((str(src), pkg))

# Web 前端资源
for res in ['web/templates', 'web/static']:
    src = ROOT / res
    if src.is_dir():
        DATAS.append((str(src), res))

a = Analysis(
    ['web/app.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=DATAS,
    hiddenimports=[
        'flask', 'werkzeug', 'jinja2', 'markupsafe', 'click',
        'itsdangerous', 'blinker', 'flask_cors',
        'openpyxl', 'pandas', 'bs4', 'charset_normalizer',
        'soupsieve', 'chardet',
    ],
    excludes=['tkinter', 'unittest', 'pdb', 'test', 'distutils',
              'setuptools', 'pip', 'numpy', 'matplotlib', 'scipy',
              'selenium', 'undetected_chromedriver'],
    hookspath=[], hooksconfig={}, runtime_hooks=[], noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(pyz, a.scripts, a.binaries, a.datas, [],
          name='PageHarvest', debug=False, bootloader_ignore_signals=False,
          strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None,
          console=True, disable_windowed_traceback=False,
          argv_emulation=False, contents_directory='_internal')

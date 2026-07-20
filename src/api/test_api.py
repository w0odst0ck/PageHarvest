"""
PageHarvest API 集成测试
测试所有平台 × 页面类型组合
"""

import sys
import io
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.engine import process_upload, Job
from api.engine import run_search_pipeline, run_detail_pipeline


def make_zip(file_paths: list[Path]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for fp in file_paths:
            zf.write(str(fp), fp.name)
    buf.seek(0)
    return buf.getvalue()


def test(name, platform, files, expected_type="search"):
    print(f"\n{'='*60}")
    print(f"  [{name}] {platform} — {expected_type}")
    print(f"  Files: {[f.name for f in files]}")
    print(f"{'='*60}")

    if not files:
        print(f"  ⚠ SKIP: no files")
        return

    zip_data = make_zip(files)
    result = process_upload(zip_data)

    print(f"  Success:    {result.success}")
    print(f"  Platform:   {result.platform}")
    print(f"  PageType:   {result.page_type}")
    print(f"  Error:      {result.error}")
    print(f"  Count:      {result.product_count}")
    print(f"  CSV lines:  {len(result.csv_content.split(chr(10))) if result.csv_content else 0}")
    if result.txt_content:
        preview = result.txt_content[:200].replace(chr(10), "\\n")
        print(f"  TXT:        {preview}...")
    if result.xlsx_bytes:
        print(f"  XLSX bytes: {len(result.xlsx_bytes)}")

    if result.success:
        print(f"  ✅ PASS")
    else:
        print(f"  ❌ FAIL")
    return result.success


# ── 数据目录 ──
DATA = ROOT / "data"
ZKH_DIR = DATA / "ZKH" / "分析-灯具"
JD_DIR = DATA / "JD" / "搜索页"
A1688_XLSX = sorted((DATA / "1688" / "插件导出").glob("*.xlsx"))
A1688_HTML = sorted((DATA / "1688" / "搜索页").glob("*.html"))

total = 0
passed = 0

# 测试 1: 震坤行搜索页 (HTML)
try:
    r = test("ZKH 搜索页", "震坤行", sorted(ZKH_DIR.glob("*.html")), "search")
    total += 1; passed += r
except Exception as e:
    print(f"  ❌ EXCEPTION: {e}"); total += 1

# 测试 2: 京东搜索页 (HTML)
try:
    r = test("JD 搜索页", "京东", sorted(JD_DIR.glob("*.html")), "search")
    total += 1; passed += r
except Exception as e:
    print(f"  ❌ EXCEPTION: {e}"); total += 1

# 测试 3: 1688 搜索页 (XLSX)
try:
    r = test("1688 XLSX", "1688", A1688_XLSX, "search")
    total += 1; passed += r
except Exception as e:
    print(f"  ❌ EXCEPTION: {e}"); total += 1

# 测试 4: 1688 搜索页 (HTML)
try:
    r = test("1688 HTML", "1688", A1688_HTML, "search")
    total += 1; passed += r
except Exception as e:
    print(f"  ❌ EXCEPTION: {e}"); total += 1

# 测试 5: 空 ZIP
print(f"\n{'='*60}")
print(f"  [Empty ZIP]")
print(f"{'='*60}")
empty_buf = io.BytesIO()
with zipfile.ZipFile(empty_buf, 'w'):
    pass
empty_result = process_upload(empty_buf.getvalue())
print(f"  Success: {empty_result.success}, Error: {empty_result.error}")
total += 1

# 测试 6: 混合 XLSX + HTML（1688）
try:
    mixed = A1688_XLSX[:2] + A1688_HTML[:2]
    r = test("1688 混合 XLSX+HTML", "1688", mixed, "search")
    total += 1; passed += r
except Exception as e:
    print(f"  ❌ EXCEPTION: {e}"); total += 1

print(f"\n{'='*60}")
print(f"  总计: {passed}/{total} 通过")
if passed == total:
    print(f"  ✅ ALL PASSED")
else:
    print(f"  ⚠ {total - passed} 项失败")

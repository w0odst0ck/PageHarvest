"""
ZKH 平台模块验证脚本

用 Playwright 加载搜索结果页，验证 parser 能正确提取商品数据。
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from platforms.zkh.crawler import search
from platforms.zkh.parser import parse

keyword = "敏华 M-ZFZD-E5W3004"
print(f"🔍 搜索: {keyword}")

html = search(keyword)
if not html:
    print("❌ 搜索失败")
    exit(1)

print(f"✅ 搜索成功，HTML: {len(html)} 字节")

candidates = parse(html)
print(f"\n📦 解析到 {len(candidates)} 个候选商品")

for i, c in enumerate(candidates[:5]):
    print(f"\n--- 商品 {i+1} ---")
    print(f"  标题: {c['title'][:60]}")
    print(f"  价格: {c['price']}")
    print(f"  品牌: {c['brand']}")
    print(f"  型号: {c['model']}")
    print(f"  链接: {c['url'][:80]}")
    print(f"  编码: {c['sku']}")

# 保存结果
out_dir = PROJECT_ROOT / "output"
out_dir.mkdir(exist_ok=True)
path = out_dir / "zkh_parse_result.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(candidates, f, ensure_ascii=False, indent=2)
print(f"\n✅ 已保存: {path}")

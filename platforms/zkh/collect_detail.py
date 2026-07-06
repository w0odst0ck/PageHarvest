"""
ZKH 详情页处理工具 — 解析已下载的 HTML 文件
=============================================

工作流：下载 HTML → 放入目录 → 批量解析

用法:
  # 解析单个文件
  python -m platforms.zkh.collect_detail path/to/detail.html

  # 批量解析目录下所有 HTML
  python -m platforms.zkh.collect_detail data/ZKH/震坤行/details/ --batch

  # 批量 + 输出 CSV
  python -m platforms.zkh.collect_detail data/ZKH/震坤行/details/ --batch --output result.csv
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 默认详情页存放目录
DEFAULT_DETAILS_DIR = str(PROJECT_ROOT / "data" / "ZKH" / "震坤行" / "details")


def parse_single(html_path: str, json_output: bool = False) -> dict | None:
    """解析单个 ZKH 详情页 HTML 文件。"""
    from platforms.zkh.detail_parser import parse_detail, to_unified_detail

    if not os.path.exists(html_path):
        print(f"❌ 文件不存在: {html_path}")
        return None

    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    result = parse_detail(html)
    detail_dict = to_unified_detail(result)

    if json_output:
        # 转换为可序列化 dict
        import dataclasses
        for v in result.sku_variants:
            if hasattr(v, '__dataclass_fields__'):
                pass
        output = dataclasses.asdict(result)
        output["raw_data"] = {"html_size": result.raw_data.get("html_size", 0)}
        output["_summary"] = detail_dict
        return output

    return detail_dict


def main():
    parser = argparse.ArgumentParser(
        description="ZKH 详情页处理工具 — 解析已下载的 HTML 文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
工作流:
  1. 浏览器打开商品详情页 → Ctrl+S 保存为"网页，仅HTML"
  2. 放入 data/ZKH/震坤行/details/
  3. 运行批量解析:
     python -m platforms.zkh.collect_detail data/ZKH/震坤行/details/ --batch

示例:
  python -m platforms.zkh.collect_detail detail.html
  python -m platforms.zkh.collect_detail detail.html --json
  python -m platforms.zkh.collect_detail data/ZKH/震坤行/details/ --batch
  python -m platforms.zkh.collect_detail data/ZKH/震坤行/details/ --batch --output 缺品明细.csv
        """,
    )
    parser.add_argument("target", help="HTML 文件路径 或 目录（配合 --batch）")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON")
    parser.add_argument("--batch", "-b", action="store_true",
                        help="批量解析目录下所有 .html 文件")
    parser.add_argument("--output", "-o", default="",
                        help="批量输出 CSV 文件路径")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    # ── 批量模式 ──
    if args.batch and os.path.isdir(args.target):
        html_files = sorted([
            os.path.join(args.target, f)
            for f in os.listdir(args.target)
            if f.endswith(".html")
        ])
        if not html_files:
            print("⚠ 目录下无 .html 文件")
            sys.exit(0)

        print(f"📂 找到 {len(html_files)} 个 HTML 文件\n")

        import csv
        from platforms.zkh.detail_parser import parse_detail, ZkhDetail

        all_results = []
        for fpath in html_files:
            fname = os.path.basename(fpath)
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()

            result = parse_detail(html)
            if result and result.title:
                all_results.append(result)
                print(f"  ✅ {fname[:45]:45} {result.brand or '-':14} ¥{result.price:>7.2f}  {len(result.attributes)}属性  {len(result.sku_variants)}SKU")
            else:
                print(f"  ❌ {fname[:45]:45} 解析失败")

        if not all_results:
            print("\n⚠ 没有成功解析的商品")
            sys.exit(0)

        ok = len(all_results)
        print(f"\n📊 {ok}/{len(html_files)} 成功")

        # CSV 输出
        if args.output:
            out_path = args.output
        else:
            out_dir = os.path.dirname(args.target) or DEFAULT_DETAILS_DIR
            out_path = os.path.join(out_dir, "parsed_details.csv")

        fieldnames = ["sku_code", "brand", "model", "title",
                       "price", "attributes_count", "sku_variants_count",
                       "main_images_count", "delivery_info", "tags", "status"]
        with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in all_results:
                w.writerow({
                    "sku_code": r.sku_code,
                    "brand": r.brand,
                    "model": r.model,
                    "title": r.title,
                    "price": r.price,
                    "attributes_count": len(r.attributes),
                    "sku_variants_count": len(r.sku_variants),
                    "main_images_count": len(r.main_images),
                    "delivery_info": r.delivery_info,
                    "tags": "|".join(r.tags),
                    "status": "OK",
                })

        # 同时保存 JSON（逐商品）
        json_dir = os.path.join(os.path.dirname(out_path), "_parsed")
        os.makedirs(json_dir, exist_ok=True)
        import dataclasses
        for r in all_results:
            jpath = os.path.join(json_dir, f"{r.sku_code or r.product_id}.json")
            with open(jpath, "w", encoding="utf-8") as f:
                data = dataclasses.asdict(r)
                json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"📁 CSV:  {out_path}")
        print(f"📁 JSON: {json_dir}/")
        return

    # ── 单文件模式 ──
    if not os.path.isfile(args.target):
        print(f"❌ 不是文件: {args.target}（需要 --batch 批量解析目录）")
        sys.exit(1)

    result = parse_single(args.target, json_output=args.json)
    if result is None:
        sys.exit(1)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        from platforms.zkh.detail_parser import _print_result
        _print_result(result)


if __name__ == "__main__":
    main()

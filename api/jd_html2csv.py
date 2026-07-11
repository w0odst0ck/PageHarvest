"""
京东搜索页 HTML → 标准 CSV（供 jd-picker 使用）
支持子进程调用或直接函数调用。
"""
import sys
import csv
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from api.brand import extract_brand
from platforms.jingdong.search_parser import parse_search_html, raw_to_unified


def convert(data_dir: str, output: str) -> int:
    """京东 HTML 目录 → CSV，返回商品数"""
    data_path = Path(data_dir)
    html_files = sorted(data_path.rglob("*.html"))
    if not html_files:
        raise RuntimeError("未找到 HTML 文件")

    all_raw = []
    for fp in html_files:
        html = fp.read_text(encoding="utf-8", errors="replace")
        all_raw.extend(parse_search_html(html, ""))

    if not all_raw:
        raise RuntimeError("未提取到商品数据")

    products = raw_to_unified(all_raw)

    for p in products:
        if not p.brand:
            p.brand = extract_brand(p.title, p.shop_name)

    rows = [{
        "brand": p.brand,
        "title": p.title,
        "price_min": p.price_min,
        "price_max": p.price_max,
        "sales_text": p.sales_text,
        "product_url": p.product_url,
        "is_self_operated": str(p.is_self_operated),
    } for p in products]

    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="京东搜索页 HTML → CSV")
    parser.add_argument("data_dir", help="HTML 文件所在目录")
    parser.add_argument("-o", "--output", help="输出 CSV 路径（默认 stdout）")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式（调试用）")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    html_files = sorted(data_dir.rglob("*.html"))
    if not html_files:
        print("未找到 HTML 文件", file=sys.stderr)
        sys.exit(1)

    all_raw = []
    for fp in html_files:
        html = fp.read_text(encoding="utf-8", errors="replace")
        all_raw.extend(parse_search_html(html, ""))

    if not all_raw:
        print("未提取到商品数据", file=sys.stderr)
        sys.exit(1)

    products = raw_to_unified(all_raw)

    for p in products:
        if not p.brand:
            p.brand = extract_brand(p.title, p.shop_name)

    rows = [{
        "brand": p.brand,
        "title": p.title,
        "price_min": p.price_min,
        "price_max": p.price_max,
        "sales_text": p.sales_text,
        "product_url": p.product_url,
        "is_self_operated": str(p.is_self_operated),
    } for p in products]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_fh = open(out_path, "w", encoding="utf-8-sig", newline="")
    else:
        out_fh = sys.stdout

    writer = csv.DictWriter(out_fh, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

    if args.output:
        out_fh.close()

    print(f"✅ 转换完成: {len(rows)} 条商品 → {args.output or 'stdout'}", file=sys.stderr)


if __name__ == "__main__":
    main()

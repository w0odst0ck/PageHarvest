"""
详情页解析器注册表 (Detail Parser Registry)
============================================

统一管理各平台的详情页解析器，支持自动检测来源平台并路由到正确的解析器。

设计目标：
  - 各平台自行实现解析函数，通过 @register 注册
  - 输入 HTML → 自动检测平台 → 路由到解析器 → 输出 UnifiedDetail
  - 支持离线批量解析（不依赖采集器）

用法：
    from core.detail_parser import parse_detail

    # 自动检测平台（推荐）
    detail = parse_detail(html)

    # 手动指定平台
    detail = parse_detail(html, platform="震坤行")
"""

import re
import logging
from typing import Optional, Callable

from core.schema import UnifiedDetail

logger = logging.getLogger(__name__)

# ── 注册表：platform → parser_function ──
# parser_function(html: str) -> Optional[UnifiedDetail]
_parsers: dict[str, Callable] = {}

# ── 平台检测标记 ──
# 每个平台定义一组在 HTML 中唯一存在的标记词
_PLATFORM_SIGNATURES: dict[str, list[str]] = {
    "震坤行": [
        "zkh.com",
        "震坤行",
        "private.zkh.com/PRODUCT/BIG",
        "行家精选",
        "订货编码",
        "sku-number",
        "gallery-slick-box",
    ],
    "1688": [
        "1688.com",
        "detail.1688.com/offer/",
        "module-od-product-attributes",
        "ant-descriptions-item-label",
        "cbu01.alicdn.com",
    ],
    "京东": [
        "jd.com",
        "item.jd.com",
        "pageConfig",
        "data-sku",
        "360buyimg.com",
        "plugin_goodsCardWrapper",
    ],
}


# ═══════════════════════════════════════════════════════════════
#  注册 & 路由
# ═══════════════════════════════════════════════════════════════

def register_parser(platform: str):
    """装饰器：注册一个平台的详情页解析器。

    被装饰的函数签名必须为: func(html: str) -> Optional[dict]
    返回的 dict 应与 UnifiedDetail 字段对齐。
    """
    def decorator(func: Callable):
        _parsers[platform] = func
        logger.debug("详情解析器已注册: %s → %s", platform, func.__name__)
        return func
    return decorator


def detect_platform(html: str) -> str | None:
    """从 HTML 内容自动检测来源平台。

    按注册平台顺序检查签名标记，匹配最多标记的平台胜出。
    """
    scores = {}
    for platform, signatures in _PLATFORM_SIGNATURES.items():
        score = sum(1 for sig in signatures if sig in html)
        if score > 0:
            scores[platform] = score

    if not scores:
        return None

    # 得分最高的平台
    winner = max(scores, key=scores.get)
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug("平台检测: %s (得分: %s)", winner, scores)
    return winner


def parse_detail(
    html: str,
    platform: str | None = None,
) -> Optional[UnifiedDetail]:
    """解析详情页 HTML，路由到对应平台解析器。

    Args:
        html: 详情页 HTML 内容
        platform: 平台名称（None = 自动检测）

    Returns:
        UnifiedDetail 对象，解析失败返回 None
    """
    if not html or len(html.strip()) < 100:
        logger.warning("HTML 内容过短，跳过解析")
        return None

    # 自动检测
    if platform is None:
        platform = detect_platform(html)
        if not platform:
            logger.warning("无法自动检测来源平台（HTML 前 200 字符: %s...）", html[:200])
            return None

    # 查找解析器
    parser = _parsers.get(platform)
    if not parser:
        available = ", ".join(_parsers.keys())
        logger.warning("平台 '%s' 未注册解析器。已注册: [%s]", platform, available)
        return None

    try:
        # 执行解析
        logger.info("解析详情页: %s", platform)
        result = parser(html)

        if result is None:
            logger.warning("%s 解析器返回 None", platform)
            return None

        # 如果是字典，转换为 UnifiedDetail
        if isinstance(result, dict):
            return UnifiedDetail(**result)
        return result

    except Exception as e:
        logger.error("%s 详情解析异常: %s", platform, e)
        return None


def list_parsers() -> list[str]:
    """列出所有已注册的解析器"""
    return list(_parsers.keys())


# ═══════════════════════════════════════════════════════════════
#  注册各平台解析器
# ═══════════════════════════════════════════════════════════════

@register_parser("震坤行")
def _parse_zkh_detail(html: str) -> Optional[dict]:
    """震坤行详情页解析器"""
    from platforms.zkh.detail_parser import parse_detail as zkh_parse, to_unified_detail
    result = zkh_parse(html)
    return to_unified_detail(result)


@register_parser("1688")
def _parse_1688_detail(html: str) -> Optional[dict]:
    """1688 详情页解析器（专用解析器）"""
    from platforms.alibaba.detail_parser import parse_detail as ali_parse, to_unified_detail
    result = ali_parse(html)
    return to_unified_detail(result)


@register_parser("京东")
def _parse_jd_detail(html: str) -> Optional[dict]:
    """京东详情页解析器"""
    from platforms.jingdong.detail_parser import parse_detail as jd_parse, to_unified_detail
    result = jd_parse(html)
    return to_unified_detail(result)


def _dataclass_to_dict(obj) -> dict:
    """将 dataclass 转换为 dict（递归）"""
    import dataclasses
    return dataclasses.asdict(obj)


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="详情页解析器 — 自动检测平台并解析",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 单文件解析
  python -m core.detail_parser detail.html
  python -m core.detail_parser detail.html --json

  # 批量解析目录下的所有 HTML
  python -m core.detail_parser data/ZKH/震坤行/details/ --batch
  python -m core.detail_parser data/ZKH/震坤行/details/ --batch --output result.csv
        """,
    )
    parser.add_argument("target", help="HTML 文件路径 或 目录（配合 --batch）")
    parser.add_argument("--platform", "-p", choices=list(_parsers.keys()),
                        help="指定平台（默认自动检测）")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON")
    parser.add_argument("--batch", "-b", action="store_true",
                        help="批量解析目录下所有 .html 文件")
    parser.add_argument("--output", "-o", default="",
                        help="批量输出 CSV 文件路径（默认: 打印摘要）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    args = parser.parse_args()

    import sys, os, json as json_module, csv
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    if not os.path.exists(args.target):
        print(f"❌ 路径不存在: {args.target}")
        sys.exit(1)

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

        print(f"📂 找到 {len(html_files)} 个 HTML 文件")

        results = []
        for fpath in html_files:
            fname = os.path.basename(fpath)
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
            result = parse_detail(html, platform=args.platform)
            if result and result.title:
                results.append({
                    "file": fname,
                    "platform": result.platform,
                    "product_id": result.product_id,
                    "title": result.title,
                    "brand": result.brand,
                    "spec": result.spec,
                    "price": result.price_min,
                    "price_max": result.price_max,
                    "attributes": len(result.attributes),
                    "sku_count": result.sku_count,
                    "image_count": len(result.main_images),
                    "status": "OK",
                })
                print(f"  ✅ {fname[:50]:50} {result.brand or '-':12} ¥{result.price_min:>7.2f}  {len(result.attributes)}属性")
            else:
                results.append({
                    "file": fname,
                    "platform": detect_platform(html) or "?",
                    "status": "FAIL",
                })
                print(f"  ❌ {fname[:50]:50} 解析失败")

        # 输出
        out_dir = os.path.dirname(args.output) if args.output else args.target
        out_dir = out_dir or "."

        os.makedirs(out_dir, exist_ok=True)

        # CSV 汇总
        csv_path = os.path.join(out_dir, "parsed_summary.csv")
        fieldnames = ["file", "platform", "product_id", "title", "brand", "spec",
                      "price", "price_max", "attributes", "sku_count", "image_count", "status"]
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
        print(f"\n📁 CSV 汇总: {csv_path}")

        # 每商品完整 JSON
        parsed_dir = os.path.join(out_dir, "_parsed")
        os.makedirs(parsed_dir, exist_ok=True)
        for fpath, r in zip(html_files, results):
            if r["status"] != "OK":
                continue
            safe_id = r["product_id"] or os.path.splitext(r["file"])[0]
            json_path = os.path.join(parsed_dir, f"{safe_id}.json")
            if os.path.exists(json_path):
                continue  # 避免重复解析
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
            detail = parse_detail(html, platform=args.platform)
            if detail:
                data = _dataclass_to_dict(detail)
                with open(json_path, "w", encoding="utf-8") as jf:
                    json_module.dump(data, jf, ensure_ascii=False, indent=2)
                print(f"  📄 JSON: {json_path}")

        ok = sum(1 for r in results if r["status"] == "OK")
        print(f"\n📊 {ok}/{len(results)} 成功")
        return

    # ── 单文件模式 ──
    if not os.path.isfile(args.target):
        print(f"❌ 不是文件: {args.target}（需要 --batch 批量解析目录）")
        sys.exit(1)

    with open(args.target, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    result = parse_detail(html, platform=args.platform)

    if result is None:
        print("❌ 解析失败")
        sys.exit(1)

    if args.json:
        data = _dataclass_to_dict(result)
        print(json_module.dumps(data, ensure_ascii=False, indent=2))
    else:
        if result.title:
            print(f"  平台:     {result.platform}")
            print(f"  商品ID:   {result.product_id or '-'}")
            print(f"  标题:     {result.title[:60]}")
            print(f"  品牌:     {result.brand or '-'}")
            print(f"  型号:     {result.spec or '-'}")
            print(f"  价格:     ¥{result.price_min:.2f}" if result.price_min else "  价格:     -")
            print(f"  主图:     {len(result.main_images)} 张")
            print(f"  属性数:   {len(result.attributes)} 项")
            print(f"  SKU 数:   {result.sku_count}")
        else:
            print("  解析完成，但未提取到有效商品数据")


if __name__ == "__main__":
    main()

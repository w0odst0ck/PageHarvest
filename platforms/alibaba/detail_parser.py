"""
1688 详情页解析器
==================
从浏览器渲染后的 1688 详情页 HTML 提取结构化数据。

输入：浏览器保存的 detail.1688.com/offer/{id}.html（含 _files/ 目录）
输出：ZkhDetail → UnifiedDetail

提取项：
  - product_id  从 URL 提取
  - title       <h1> 标签
  - brand       商品属性 → 品牌
  - model       商品属性 → 货号 / 制造商型号
  - price       <span class="currency"> 拼接
  - attributes  商品属性表 (ant-descriptions)
  - sku_variants SKU 规格（颜色/功率等）
  - main_images cbu01.alicdn.com/img/ibank/ 图片
  - description 描述区 HTML
"""

import re
import os
import logging
from typing import Optional
from urllib.parse import urlparse
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


# ── 数据模型 ────────────────────────────────────────────────

@dataclass
class SkuVariant:
    spec: str       # 规格名称，如 "JK-1款-金色-单个装"
    price: float    # 单价
    spec_type: str = ""  # 规格类型，如 "灯光颜色" / "光源功率"


@dataclass
class AttributeItem:
    name: str       # 属性名，如 "品牌" / "电压"
    value: str      # 属性值，如 "锦明" / "≤36V（V）"


@dataclass
class AlibabaDetail:
    product_id: str = ""
    title: str = ""
    brand: str = ""
    model: str = ""
    price_min: float = 0.0
    price_max: float = 0.0
    attributes: list = field(default_factory=list)       # [AttributeItem]
    sku_variants: list = field(default_factory=list)     # [SkuVariant]
    main_images: list = field(default_factory=list)      # [str]
    sku_count: int = 0
    description: str = ""


# ═══════════════════════════════════════════════════════════════
#  核心解析
# ═══════════════════════════════════════════════════════════════

def validate_input(html: str) -> Optional[str]:
    """三重输入校验：拒绝其他平台 / 拒绝搜索页 / 确认 1688 详情页特征

    Returns:
        str | None: 通过校验返回完整 HTML，失败返回 None
    """
    if not html or len(html.strip()) < 200:
        logger.warning("HTML 内容过短")
        return None

    # 1. 平台检测：必须是 1688
    alibaba_signatures = [
        "detail.1688.com/offer/",
        "1688.com",
        "cbu01.alicdn.com",
    ]
    if not any(sig in html for sig in alibaba_signatures):
        logger.warning("非 1688 页面，拒绝解析")
        return None

    # 2. 拒绝搜索页
    search_signatures = [
        "offer_search.htm",
        "selloffer/offer_search",
        'class="goods-item-wrap-new"',
    ]
    if any(sig in html for sig in search_signatures):
        logger.warning("检测到搜索页特征，拒绝解析")
        return None

    # 3. 确认详情页特征
    detail_signatures = [
        "detail.1688.com/offer/",
        "module-od-product-attributes",
    ]
    if not any(sig in html for sig in detail_signatures):
        logger.warning("缺少详情页特征，拒绝解析")
        return None

    return html


def parse_detail(html: str) -> Optional[AlibabaDetail]:
    """解析 1688 详情页 HTML → AlibabaDetail"""
    validated = validate_input(html)
    if validated is None:
        return None

    detail = AlibabaDetail()

    # 1. Product ID: 从 URL 提取
    detail.product_id = _extract_product_id(html)

    # 2. 标题
    detail.title = _extract_title(html)

    # 3. 价格
    detail.price_min, detail.price_max = _extract_price(html)

    # 4. 商品属性
    detail.attributes = _extract_attributes(html)

    # 5. 品牌 / 型号（从属性表查找）
    for attr in detail.attributes:
        if attr.name == "品牌" and not detail.brand:
            detail.brand = attr.value
        elif attr.name == "货号" and not detail.model:
            detail.model = attr.value

    # 6. SKU 变体
    detail.sku_variants = _extract_sku_variants(html)
    detail.sku_count = len(detail.sku_variants)

    # 7. 主图
    detail.main_images = _extract_main_images(html)

    # 8. 描述
    detail.description = _extract_description(html)

    return detail


# ═══════════════════════════════════════════════════════════════
#  提取辅助函数
# ═══════════════════════════════════════════════════════════════

def _extract_product_id(html: str) -> str:
    """从 URL 或 HTML 中提取 offer ID"""
    # 1. 从 saved-from-url 提取
    m = re.search(r'detail\.1688\.com/offer/(\d+)', html)
    if m:
        return m.group(1)

    # 2. 从 "offerId":数字 提取
    m = re.search(r'"offerId"\s*:\s*(\d+)', html)
    if m:
        return m.group(1)

    return ""


def _extract_title(html: str) -> str:
    """提取商品标题（第二个 h1，或 title 标签）"""
    # 先找 <h1> 标签（排除第一个是店铺名）
    titles = re.findall(r'<h1[^>]*>(?:[^<]*<[^>]*>)*([^<]+)</h1>', html)
    for t in titles:
        t = t.strip()
        # 跳过明显是店铺名的（短的、不含关键词的）
        if len(t) >= 8 and "经营部" not in t and "公司" not in t:
            return t

    # 兜底：取 title 标签（去掉 "- 阿里巴巴" 后缀）
    m = re.search(r'<title>([^<]+)</title>', html)
    if m:
        title = m.group(1).strip()
        title = re.sub(r'\s*-\s*阿里巴巴.*$', '', title)
        return title

    return ""


def _extract_price(html: str) -> tuple:
    """提取价格区间

    1688 已渲染页面中价格通常以 <span class="currency"> 分割展示：
      <span class="currency">21</span>
      <span class="currency">.90</span>
    多个连续 .currency 片段拼接成一个完整价格。

    多个价格片段代表价格区间。
    """
    prices = re.findall(r'<span class="currency">([\d.]+)</span>', html)

    # 拼接连续价格片段
    parsed = []
    buf = ""
    for p in prices:
        if p.startswith("."):
            buf += p
        elif buf:
            parsed.append(float(buf))
            buf = p
        else:
            buf = p
    if buf:
        parsed.append(float(buf))

    if not parsed:
        return (0.0, 0.0)

    return (min(parsed), max(parsed))


def _extract_attributes(html: str) -> list:
    """从商品属性表提取键值对

    结构：
      <th class="ant-descriptions-item-label"><span>属性名</span></th>
      <td class="ant-descriptions-item-content"><span><span class="field-value">属性值</span></span></td>
    """
    # 一次性提取所有 label/value 对
    pattern = (
        r'<th[^>]*class="ant-descriptions-item-label"[^>]*>'
        r'\s*<span>([^<]+)</span>\s*</th>'
        r'\s*<td[^>]*class="ant-descriptions-item-content"[^>]*>'
        r'\s*<span>\s*<span[^>]*class="field-value"[^>]*>([^<]+)</span>\s*</span>\s*</td>'
    )
    matches = re.findall(pattern, html, re.DOTALL)

    attrs = []
    for name, value in matches:
        name = name.strip()
        value = value.strip()
        if name and value:
            attrs.append(AttributeItem(name=name, value=value))

    return attrs


def _extract_sku_variants(html: str) -> list:
    """提取 SKU 变体

    1688 详情页 SKU 分为两种规格类型（如"灯光颜色"和"光源功率"）：

    1. 规格选项（灯光颜色）：
       <button class="sku-filter-button ...">
         <span class="label-name">JK-1款-金色-单个装</span>
       </button>

    2. 价格规格（光源功率）：
       <span class="item-label" title="3M胶粘贴不带灯泡">
       <span class="item-price">...<span class="currency">25</span><span class="currency">.00</span>
    """
    variants = []

    # 从 sku-filter-button 提取规格选项（灯光颜色等图片选项）
    spec_pattern = re.findall(
        r'<button[^>]*class="sku-filter-button[^"]*"[^>]*>'
        r'(?:<div[^>]*><img[^>]*></div>)?'
        r'\s*<span[^>]*class="label-name"[^>]*>([^<]+)</span>',
        html
    )
    for spec in spec_pattern:
        spec = spec.strip()
        if spec:
            variants.append(SkuVariant(spec=spec, price=0.0, spec_type="规格"))

    # 从 item-label 提取功率/价格选项（光源功率）
    # 模式: item-label → item-price 连续结构
    power_pattern = re.compile(
        r'<span[^>]*class="item-label"[^>]*title="([^"]*)"[^>]*>.*?</span>'
        r'\s*<span[^>]*class="item-price[^"]*"[^>]*>'
        r'(.*?)</span>',
        re.DOTALL
    )
    for m in power_pattern.finditer(html):
        label = m.group(1).strip()
        price_html = m.group(2)
        # 提取价格
        prices = re.findall(r'<span class="currency">([\d.]+)</span>', price_html)
        if prices:
            try:
                price_str = "".join(prices)
                price = float(price_str)
            except ValueError:
                price = 0.0
        else:
            price = 0.0

        if label:
            variants.append(SkuVariant(spec=label, price=price, spec_type="价格"))

    return variants


def _extract_main_images(html: str) -> list:
    """提取主图 CDN 链接

    1688 渲染后的 HTML 包含 cbu01.alicdn.com 直链。
    排除 logo、图标等小图（<176px 宽的排除）。
    """
    images = re.findall(
        r'src="(https://cbu01\.alicdn\.com/img/ibank/[^"]+)"',
        html
    )

    # 排除小图标和缩略图
    result = []
    for url in images:
        # 排除 _88x88 缩略图
        if '_88x88' in url:
            continue
        # 排除 svg logo
        if url.endswith('.svg'):
            continue
        result.append(url)

    return result


def _extract_description(html: str) -> str:
    """提取商品描述区 HTML（简要提取）"""
    # 查找 html-description 区域
    m = re.search(
        r'<v-detail-c\s+class="html-description"[^>]*>'
        r'(.*?)'
        r'</v-detail-c>',
        html,
        re.DOTALL
    )
    if m:
        desc = m.group(1)
        # 截取前 1000 字符作为摘要
        return desc[:1000]

    return ""


# ═══════════════════════════════════════════════════════════════
#  统一输出转换
# ═══════════════════════════════════════════════════════════════

def to_unified_detail(alibaba_detail: Optional[AlibabaDetail]) -> Optional[dict]:
    """将 AlibabaDetail 转为 UnifiedDetail 兼容的字典"""
    if alibaba_detail is None:
        return None

    # 整理属性为 key: value 字典
    attrs_dict = {a.name: a.value for a in alibaba_detail.attributes}

    # 整理 SKU 变体
    sku_list = []
    seen_specs = set()
    for v in alibaba_detail.sku_variants:
        if v.spec not in seen_specs:
            seen_specs.add(v.spec)
            sku_list.append({
                "spec": v.spec,
                "price": v.price,
                "spec_type": v.spec_type,
            })

    return {
        "platform": "1688",
        "product_id": alibaba_detail.product_id,
        "product_url": f"https://detail.1688.com/offer/{alibaba_detail.product_id}.html" if alibaba_detail.product_id else "",
        "title": alibaba_detail.title,
        "brand": alibaba_detail.brand,
        "spec": alibaba_detail.model,
        "product_code": alibaba_detail.model,
        "price_min": alibaba_detail.price_min,
        "price_max": alibaba_detail.price_max,
        "attributes": attrs_dict,
        "sku_count": len(sku_list),
        "sku_matrix": sku_list,
        "main_images": alibaba_detail.main_images,
        "raw_data": {
            "description": alibaba_detail.description[:500],
            "attributes_list": [
                {"name": a.name, "value": a.value}
                for a in alibaba_detail.attributes
            ],
        },
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    import json

    parser = argparse.ArgumentParser(description="1688 详情页解析器")
    parser.add_argument("target", help="HTML 文件路径或目录（--batch）")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON")
    parser.add_argument("--batch", "-b", action="store_true", help="批量解析目录")
    parser.add_argument("--output", "-o", default="", help="批量输出 CSV")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.batch and os.path.isdir(args.target):
        html_files = sorted([
            os.path.join(args.target, f)
            for f in os.listdir(args.target)
            if f.endswith(".html")
        ])
        print(f"📂 找到 {len(html_files)} 个 HTML 文件")

        results = []
        for fpath in html_files:
            fname = os.path.basename(fpath)
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                html = f.read()
            detail = parse_detail(html)
            if detail and detail.title:
                results.append({
                    "file": fname,
                    "product_id": detail.product_id,
                    "title": detail.title,
                    "brand": detail.brand,
                    "price": detail.price_min,
                    "price_max": detail.price_max,
                    "attrs": len(detail.attributes),
                    "skus": detail.sku_count,
                    "images": len(detail.main_images),
                    "status": "OK",
                })
                print(f"  ✅ {fname[:50]:50} {detail.brand or '-':8} ¥{detail.price_min:>7.2f}  {len(detail.attributes)}属性/{detail.sku_count}SKU")
            else:
                results.append({"file": fname, "status": "FAIL"})
                print(f"  ❌ {fname[:50]:50} 解析失败")

        if args.output:
            import csv
            fieldnames = ["file", "product_id", "title", "brand", "price",
                          "price_max", "attrs", "skus", "images", "status"]
            with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames)
                w.writeheader()
                w.writerows(results)
            print(f"\n📁 已保存: {args.output}")

        ok = sum(1 for r in results if r["status"] == "OK")
        print(f"📊 {ok}/{len(results)} 成功")
        return

    # 单文件
    if not os.path.isfile(args.target):
        print(f"❌ 路径无效: {args.target}")
        return

    with open(args.target, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    detail = parse_detail(html)
    if detail is None:
        print("❌ 解析失败")
        return

    if args.json:
        print(json.dumps(to_unified_detail(detail), ensure_ascii=False, indent=2))
    else:
        print(f"  商品ID:   {detail.product_id or '-'}")
        print(f"  标题:     {detail.title[:60] if detail.title else '-'}")
        print(f"  品牌:     {detail.brand or '-'}")
        print(f"  货号:     {detail.model or '-'}")
        print(f"  价格:     ¥{detail.price_min:.2f} ~ ¥{detail.price_max:.2f}" if detail.price_min > 0 else "  价格:     -")
        print(f"  属性数:   {len(detail.attributes)} 项")
        for a in detail.attributes[:10]:
            print(f"      {a.name}: {a.value}")
        print(f"  SKU 数:   {detail.sku_count}")
        for v in detail.sku_variants[:5]:
            print(f"      {v.spec}: ¥{v.price:.2f}" if v.price else f"      {v.spec}")
        print(f"  主图:     {len(detail.main_images)} 张")


if __name__ == "__main__":
    main()

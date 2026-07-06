"""
ZKH 详情页解析器 (ZhenKunHang Detail Parser)
=============================================

解析浏览器渲染后的 ZKH 商品详情页 HTML，提取结构化商品信息。
支持两种输入：
  1. 浏览器渲染后的完整 HTML（Playwright / 手动保存）
  2. 直接从网站获取的 SPA 壳 HTML（备用，仅返回基础信息）

用法:
    python -m platforms.zkh.detail_parser <html_file>
    python -m platforms.zkh.detail_parser <html_file> --json

图片 CDN 基础 URL（搜索页已知）:
    https://private.zkh.com/PRODUCT/BIG/{filename}
"""

import os
import re
import sys
import json
import logging
from typing import Optional
from dataclasses import dataclass, field, asdict

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
#  中间模型（不依赖 core.schema，可独立使用）
# ═══════════════════════════════════════════════════════════════

@dataclass
class ZkhDetail:
    """ZKH 详情页解析结果"""
    product_id: str = ""             # 商品 ID（URL 中的 ID）
    sku_code: str = ""               # 订货编码（AE 开头）
    title: str = ""
    brand: str = ""
    model: str = ""                  # 制造商型号
    price: float = 0.0              # 官网价/默认 SKU 价格
    price_display: str = ""          # 原始价格文本（含单位）
    min_order: int = 1
    ship_from: str = ""              # 发货地
    delivery_info: str = ""          # 发货时间说明
    main_images: list = field(default_factory=list)     # CDN URL 列表
    attributes: dict = field(default_factory=dict)       # 参数键值对
    sku_variants: list = field(default_factory=list)     # SKU 变体列表
    stock_status: str = ""           # 库存状态
    description: str = ""            # 详情描述文本
    tags: list = field(default_factory=list)             # 标签（行家精选等）
    raw_data: dict = field(default_factory=dict)         # 原始解析中间数据


@dataclass
class ZkhSkuVariant:
    """SKU 变体"""
    sku_code: str = ""           # 订货编码
    model: str = ""              # 制造商型号
    price: float = 0.0
    price_unit: str = "个"       # 单位
    delivery_days: str = ""      # 发货天数


# ═══════════════════════════════════════════════════════════════
#  图片 URL 重构
# ═══════════════════════════════════════════════════════════════

ZKH_IMAGE_CDN = "https://private.zkh.com/PRODUCT/BIG"


def reconstruct_image_url(src: str) -> str:
    """从图片 src 重构 CDN URL。

    - 已有完整 URL ✅ 直接返回
    - 相对路径 ./xxx_files/BIG_XX.jpg → CDN URL
    - 纯文件名 BIG_XX.jpg → CDN URL
    """
    if not src:
        return ""
    src = src.strip()
    # 已经是完整 URL
    if src.startswith("http://") or src.startswith("https://"):
        return src
    # 提取文件名
    filename = os.path.basename(src)
    if filename.startswith("BIG_") and (filename.endswith(".jpg") or filename.endswith(".jpeg") or filename.endswith(".png") or filename.endswith(".webp")):
        return f"{ZKH_IMAGE_CDN}/{filename}"
    return src  # 无法重构，原样返回


# ═══════════════════════════════════════════════════════════════
#  主解析函数
# ═══════════════════════════════════════════════════════════════

def parse_detail(html: str, product_id: str = "") -> ZkhDetail:
    """解析 ZKH 商品详情页 HTML。

    Args:
        html: 浏览器渲染后的完整 HTML
        product_id: 商品 ID（可选，自动从 HTML 推断）

    Returns:
        ZkhDetail 对象
    """
    if BeautifulSoup is None:
        raise ImportError("需要安装 beautifulsoup4: pip install beautifulsoup4")

    soup = BeautifulSoup(html, "html.parser")
    result = ZkhDetail(product_id=product_id)

    # 保存原始数据
    result.raw_data["html_size"] = len(html)

    # ── 1. 标题 ──
    title_tag = soup.find("title")
    if title_tag:
        raw_title = title_tag.get_text(strip=True)
        # 去掉尾部 "-震坤行"
        result.title = re.sub(r"-震坤行$", "", raw_title).strip()
    else:
        # 兜底：从页面元素找
        for sel in [".goods-title", ".name", ".item-header", "h1", ".product-name", ".goods-name", ".product-title"]:
            el = soup.select_one(sel)
            if el:
                result.title = el.get_text(strip=True)
                break

    # ── 2. 产品 ID ──
    if not result.product_id:
        # 从订货编码推断？不行，product_id 是 URL 中的
        # 尝试从 HTML 中的隐藏字段获取
        for pat in [
            r'\"productId\":\s*\"([A-Z0-9]+)\"',
            r'\"proGroupNo\":\s*\"([A-Z0-9]+)\"',
        ]:
            m = re.search(pat, html)
            if m:
                result.product_id = m.group(1)
                break

    # ── 3. SKU 编码（订货编码） ──
    first_sku = soup.select_one(".clearfix.sku-number")
    if first_sku:
        sku_text = first_sku.get_text(strip=True)
        m = re.search(r'([A-Z]{2}\d+)', sku_text)
        if m:
            result.sku_code = m.group(1)

    # ── 4. 品牌 ──
    brand_el = _find_param(soup, "品牌")
    if brand_el:
        result.brand = _extract_param_value(brand_el.get_text(strip=True))

    # ── 5. 制造商型号 ──
    model_el = _find_param(soup, "制造商型号")
    if model_el:
        result.model = _extract_param_value(model_el.get_text(strip=True))

    # ── 6. 价格 ──
    price_areas = soup.select(".sku-price-wrap-new")
    for pa in price_areas:
        price_text = pa.get_text(strip=True)
        # 跳过推荐商品的 SKU 价格
        parent = pa.parent
        if parent and "recommend" in str(parent.get("class", "")):
            continue
        # 提取数字
        m = re.search(r'[¥￥]?([\d.]+)\s*/\s*(\S+)', price_text)
        if m:
            try:
                result.price = float(m.group(1))
                result.price_display = price_text
            except ValueError:
                pass
            break

    # 兜底：从页面文本找"官网价￥xxx"
    if result.price == 0.0:
        m = re.search(r'官网价[¥￥]([\d.]+)', html)
        if m:
            try:
                result.price = float(m.group(1))
            except ValueError:
                pass

    # ── 7. 属性参数 ──
    params = soup.select(".params-wrap .params-item, .params-wrap .param-item")
    for p in params:
        text = p.get_text(strip=True, separator=" ")
        key, val = _parse_kv(text)
        if key and val:
            result.attributes[key] = val

    # ── 8. 主图 ──
    seen_images = set()
    # 优先从 gallery 取
    for sel in [".gallery-wrap img", ".img-wrap img", ".gallery-slick-box img", ".img-zoom-base-wrap img"]:
        for img in soup.select(sel):
            src = img.get("src", img.get("data-src", ""))
            cdn_url = reconstruct_image_url(src)
            if cdn_url and cdn_url not in seen_images:
                # 过滤非商品图
                base = os.path.basename(cdn_url)
                if base.startswith("BIG_") or base.startswith("default"):
                    if "default-img" not in cdn_url:
                        seen_images.add(cdn_url)
                        result.main_images.append(cdn_url)

    # 如果 gallery 没找到，从本地 files 目录推断
    if not result.main_images:
        # 从 HTML 中找所有图片文件名
        for m in re.finditer(r'src="([^"]*BIG_[^"]+\.(?:jpg|jpeg|png))"', html):
            cdn_url = reconstruct_image_url(m.group(1))
            if cdn_url and cdn_url not in seen_images:
                seen_images.add(cdn_url)
                result.main_images.append(cdn_url)

    # ── 9. SKU 变体 ──
    # 每个 SKU 项的结构：.sku-number + .sku-price-wrap-new 配对
    sku_numbers = soup.select(".clearfix.sku-number")
    sku_prices = soup.select(".sku-price-wrap-new")

    for i, sku_num in enumerate(sku_numbers):
        # 跳过推荐商品区域
        parent_classes = str(sku_num.parent.get("class", "")) if sku_num.parent else ""
        if "recommend" in parent_classes or "recommend" in str(sku_num.parent_previous_sibling):
            continue

        sku_text = sku_num.get_text(strip=True)
        sku_m = re.search(r'订货编码[：:]\s*([A-Z]{2}\d+)', sku_text)
        model_m = re.search(r'制造商型号[：:]\s*([^，,]+)', sku_text)
        sku_code = sku_m.group(1) if sku_m else ""

        # 找对应价格
        if i < len(sku_prices):
            price_text = sku_prices[i].get_text(strip=True)
            p_m = re.search(r'[¥￥]?([\d.]+)\s*/\s*(\S+)', price_text)
        else:
            p_m = None

        variant = ZkhSkuVariant(
            sku_code=sku_code,
            model=model_m.group(1) if model_m else "",
            price=float(p_m.group(1)) if p_m else 0.0,
            price_unit=p_m.group(2) if p_m else "",
        )

        # 查找该 SKU 的发货信息
        delivery_parent = sku_num.find_next("div", class_=lambda x: x and "sku-stock" in x)
        if delivery_parent:
            variant.delivery_days = delivery_parent.get_text(strip=True)

        # 跳过相似商品页的 SKU
        if not sku_code and not variant.model:
            continue
        result.sku_variants.append(variant)

    # ── 10. 发货/配送信息 ──
    stock = soup.select_one(".sku-stock-wrap")
    if stock:
        result.delivery_info = stock.get_text(strip=True)
        # 识别库存状态
        if "现货" in result.delivery_info:
            result.stock_status = "现货"
        elif "预定" in result.delivery_info or "预售" in result.delivery_info:
            result.stock_status = "预售"
        else:
            result.stock_status = result.delivery_info[:20]

    # ── 11. 发货地 ──
    # 从配送区域选择推断（上海市...）
    city_els = soup.select("#detailCity, .zkh-code, [class*=city]")
    for el in city_els:
        text = el.get_text(strip=True)
        provinces = ["北京", "上海", "天津", "重庆", "河北", "山西", "内蒙古",
                      "辽宁", "吉林", "黑龙江", "江苏", "浙江", "安徽", "福建",
                      "江西", "山东", "河南", "湖北", "湖南", "广东", "广西",
                      "海南", "四川", "贵州", "云南", "西藏", "陕西", "甘肃",
                      "青海", "宁夏", "新疆"]
        for p in provinces:
            if p in text:
                result.ship_from = p
                break
        if result.ship_from:
            break

    # ── 12. 标签 ──
    if "行家精选" in html:
        result.tags.append("行家精选")
    if "行家甄选" in html:
        result.tags.append("行家甄选")
    if "热销" in html:
        result.tags.append("热销")

    # ── 13. 详情描述 ──
    desc_area = soup.select_one(".product-introduce-wrap, #product-introduce-wrap, .detail-area-wrap")
    if desc_area:
        result.description = desc_area.get_text(strip=True, separator="\n")[:2000]

    # ── 14. 起批量（默认为1） ──
    mo_m = re.search(r'起批[量\s]*(\d+)', html)
    if mo_m:
        try:
            result.min_order = int(mo_m.group(1))
        except ValueError:
            pass

    return result


# ═══════════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════════

def _find_param(soup, key: str):
    """在参数区查找指定 key 的元素"""
    for item in soup.select(".params-wrap .params-item, .params-wrap .param-item"):
        text = item.get_text(strip=True)
        if text.startswith(key) or text.startswith(f"{key} "):
            return item
    return None


def _extract_param_value(text: str) -> str:
    """从 '品牌 ：FSL/佛山照明' 提取值"""
    # 去掉前缀 key
    text = re.sub(r'^[^：:]*[：:]', "", text).strip()
    # 去掉尾部多余的 key-value（比如产品名称也被拼进去了）
    text = re.split(r'\s{2,}', text)[0].strip()
    return text


def _parse_kv(text: str) -> tuple:
    """从 '品牌 ：FSL/佛山照明' 解析 key: value"""
    m = re.match(r'^(.+?)\s*[：:]\s*(.+)$', text)
    if m:
        key = m.group(1).strip()
        val = m.group(2).strip()
        # 过滤非参数（如"可搭配使用商品..."）
        if len(key) > 1 and len(val) > 0 and len(key) < 30:
            return key, val
    return None, None


# ═══════════════════════════════════════════════════════════════
#  转换到 UnifiedDetail
# ═══════════════════════════════════════════════════════════════

def to_unified_detail(zkh: ZkhDetail) -> dict:
    """转换为 core.schema.UnifiedDetail 兼容的字典"""
    total_images = sum(1 for v in zkh.sku_variants)  # placeholder
    return {
        "platform": "震坤行",
        "product_id": zkh.product_id or zkh.sku_code,
        "product_url": "",
        "title": zkh.title,
        "brand": zkh.brand,
        "spec": zkh.model,
        "product_code": zkh.sku_code,
        "price_min": zkh.price,
        "price_max": max((v.price for v in zkh.sku_variants), default=zkh.price),
        "min_order": zkh.min_order,
        "ship_from": zkh.ship_from,
        "sales_count": 0,
        "main_images": zkh.main_images,
        "detail_images": [],
        "attributes": zkh.attributes,
        "sku_count": len(zkh.sku_variants),
        "sku_matrix": [asdict(v) for v in zkh.sku_variants],
        "raw_data": zkh.raw_data,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="ZKH 详情页解析器 — 从浏览器渲染后的 HTML 提取结构化商品信息",
    )
    parser.add_argument("html_file", help="详情页 HTML 文件路径")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON")
    parser.add_argument("--product-id", "-p", help="商品 ID（可选）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    if not os.path.exists(args.html_file):
        print(f"❌ 文件不存在: {args.html_file}")
        sys.exit(1)

    with open(args.html_file, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    result = parse_detail(html, product_id=args.product_id or "")

    if args.json:
        output = asdict(result)
        # 移除原始数据中的大字段
        output["raw_data"] = {
            k: v for k, v in result.raw_data.items()
            if isinstance(v, (str, int, float, bool))
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        _print_result(result)


def _print_result(r: ZkhDetail):
    print("═" * 55)
    print("  ZKH 详情页解析结果")
    print("═" * 55)
    print(f"  商品ID:    {r.product_id or '-'}")
    print(f"  订货编码:  {r.sku_code or '-'}")
    print(f"  标题:     {r.title[:60] if r.title else '-'}")
    print(f"  品牌:     {r.brand or '-'}")
    print(f"  型号:     {r.model or '-'}")
    print(f"  价格:     ¥{r.price:.2f}" if r.price else "  价格:     -")
    print(f"  起批量:   {r.min_order}")
    print(f"  发货地:   {r.ship_from or '-'}")
    print(f"  库存:     {r.stock_status or '-'}")
    print(f"  配送:     {r.delivery_info or '-'}")
    print(f"  标签:     {', '.join(r.tags) if r.tags else '-'}")
    print(f"  主图:     {len(r.main_images)} 张")
    print()

    if r.attributes:
        print("  ── 参数 ──")
        for k, v in r.attributes.items():
            print(f"    {k}: {v}")

    if r.sku_variants:
        print()
        print(f"  ── SKU 变体 ({len(r.sku_variants)}) ──")
        for v in r.sku_variants:
            print(f"    {v.sku_code:12}  {v.model:30}  ¥{v.price:>7.2f}/{v.price_unit}  {v.delivery_days}")

    print()
    print("═" * 55)


if __name__ == "__main__":
    main()

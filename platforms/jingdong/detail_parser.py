"""
京东详情页解析器 (JD Detail Parser)
====================================

专用于解析 **京东商品详情页**（item.jd.com/xxx.html）的浏览器渲染后 HTML。
**与京东搜索页（search.jd.com/Search）结构完全不同，切勿混用。**

平台隔离：
  - 拒绝其他平台（震坤行、1688）的 HTML，附明确提示
  - 拒绝京东搜索页 HTML，附明确提示
  - 三重校验通过后才进入解析

用法:
    python -m platforms.jingdong.detail_parser item.html
    python -m platforms.jingdong.detail_parser item.html --json
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
#  输入校验特征标记
# ═══════════════════════════════════════════════════════════════

# 其他平台独有的特征（京东详情页解析器遇到应直接拒绝）
_OTHER_PLATFORM_SIGNATURES = [
    # 震坤行
    "zkh.com",
    "震坤行",
    "private.zkh.com/PRODUCT/BIG",
    "行家精选",
    "订货编码",
    "gallery-slick-box",
    "sku-number",
    "proGroupNo",
    # 1688
    "1688.com",
    "detail.1688.com",
    "offer_search",
    "alibaba_parser",
    "alibaba.com",
]

# 京东搜索页独有的特征（传入详情页解析器时应拒绝）
_JD_SEARCH_SIGNATURES = [
    'search.jd.com/Search',
    'plugin_goodsCardWrapper',
    'searchMainConfig.isList',
    'searchShopConfig',
    'search-discover',
    '_goodsCardWrapper',
    '_product-list_',
]

# 京东详情页 item.jd.com 独有的特征（搜索页不含）
_JD_DETAIL_SIGNATURES = [
    # 新版 React 架构（2025+）
    'class="attrs"',                                   # 新版属性表
    'class="highlight-attrs"',                        # 新版高亮属性
    'class="top-name"',                               # 新版店铺名
    'waist-shop-title',                                # 新版进店逛逛
    'class="expert-selection-root"',                  # 新版达人选购
    'class="left-tabs-item"',                         # 新版左侧Tab
    'class="SPXQ-title"',                             # 新版商品详情
    # 旧版页面的特征
    r'window\.pageConfig\s*=\s*{\s*["product]',      # 商品级 pageConfig
    'itemInfo-wrap',                                  # 详情页信息区
    'summary-price',                                  # 价格摘要区
    'choose-attr-',                                   # SKU 选择器
    'parameter2 p-parameter-list',                    # 参数规格表
]


def validate_detail_html(html: str) -> tuple[bool, str]:
    """验证 HTML 是否为京东商品详情页格式。

    三重校验：
      1. 排除其他平台（震坤行 / 1688）
      2. 排除京东搜索页
      3. 确认含京东详情页特征

    Returns:
        (is_valid, reason)
        - (True, "ok")  — 通过
        - (False, msg)  — 拒绝，附原因
    """
    first_line = html[:300].strip()

    # ── 校验1: 排除其他平台 HTML ──
    for sig in _OTHER_PLATFORM_SIGNATURES:
        if sig in html:
            return False, (
                f"检测到其他平台特征 '{sig}'，京东详情页解析器不适用。\n"
                f"  你传的 HTML 可能来自 震坤行(zkh) 或 1688 平台。\n"
                f"  请使用对应平台的解析器：\n"
                f"    震坤行: python -m platforms.zkh.detail_parser\n"
                f"    1688:   通过 adapter.parse_detail()\n"
                f"    京东:   python -m platforms.jingdong.detail_parser (仅 item.jd.com)"
            )

    # ── 校验2: 从 saved-from URL 推断 ──
    if 'saved from url=' in first_line:
        url_match = re.search(r'https?://[^\s\'"]+', first_line)
        if url_match:
            url_str = url_match.group(0)
            if 'zkh.com' in url_str or '1688.com' in url_str:
                return False, f"检测到其他平台 URL: {url_str[:60]}... 京东详情页解析器不适用"
            if 'search.jd.com' in url_str or 're.jd.com' in url_str:
                return False, (
                    f"检测到搜索页 URL: {url_str[:60]}...\n"
                    f"  京东详情页解析器只接受 item.jd.com/xxx.html\n"
                    f"  搜索页解析请使用: python -m platforms.jingdong.collect_search"
                )

    # ── 校验3: 排除京东搜索页特征 ──
    for sig in _JD_SEARCH_SIGNATURES:
        if sig in html:
            return False, (
                f"检测到京东搜索页特征: '{sig}'\n"
                f"  详情页解析器只接受 item.jd.com/xxx.html\n"
                f"  搜索页请使用: python -m platforms.jingdong.collect_search"
            )

    # ── 校验4: 确认京东详情页特征 ──
    detail_hits = 0
    for sig in _JD_DETAIL_SIGNATURES:
        if re.search(sig, html):
            detail_hits += 1

    has_page_config = bool(re.search(
        r'window\.pageConfig.*?sku["\']?\s*[:=]\s*["\']?\d+', html, re.DOTALL
    ))
    has_sku_name = '.sku-name' in html

    # 新版页面特征：只要有属性表或店铺名就认为通过
    has_new_attrs = bool(re.search(r'class="attrs"', html)) and bool(re.search(r'class="top-name"', html))
    if has_new_attrs:
        return True, "ok"

    if detail_hits < 2 and not has_page_config and not has_sku_name:
        # 最后兜底：检查 URL 是否来自 item.jd.com
        url_m = re.search(r'item\.jd\.com/(\d+)', html)
        if url_m:
            return True, "ok"

        reasons = []
        reasons.append(f"京东详情页特征命中 {detail_hits}/{len(_JD_DETAIL_SIGNATURES)}")
        if not has_page_config:
            reasons.append("无 window.pageConfig.sku")
        if not has_sku_name:
            reasons.append("无 .sku-name")
        return False, (
            f"未能确认输入为京东商品详情页: {'; '.join(reasons)}\n"
            f"  请确保文件来自 item.jd.com/商品ID.html（浏览器渲染后保存）"
        )

    return True, "ok"


# ═══════════════════════════════════════════════════════════════
#  中间模型
# ═══════════════════════════════════════════════════════════════

@dataclass
class JdDetail:
    """京东详情页解析结果"""
    product_id: str = ""              # SKU
    title: str = ""
    brand: str = ""
    model: str = ""                   # 商品型号
    price_min: float = 0.0           # 到手价
    price_max: float = 0.0           # 划线价/原价
    shop_name: str = ""
    shop_type: str = ""               # 自营/旗舰店/第三方
    main_images: list = field(default_factory=list)
    attributes: dict = field(default_factory=dict)   # 参数规格表
    sku_specs: dict = field(default_factory=dict)    # SKU 选项（颜色/尺寸）
    description_images: list = field(default_factory=list)
    sales_count: str = ""             # 已售文本
    rating: str = ""                  # 好评率
    tags: list = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════
#  主解析函数
# ═══════════════════════════════════════════════════════════════

def parse_detail(html: str, product_id: str = "") -> JdDetail:
    """解析京东商品详情页 HTML。

    Args:
        html: 浏览器渲染后的京东商品详情页（item.jd.com/xxx.html）HTML
        product_id: SKU（可选，自动从 HTML 推断）

    Returns:
        JdDetail 对象

    Raises:
        ValueError: 如果传入的不是京东商品详情页 HTML
          （可能是其他平台的页面、或京东搜索页）
    """
    if BeautifulSoup is None:
        raise ImportError("需要安装 beautifulsoup4: pip install beautifulsoup4")

    # ── 输入校验：三重过滤 ──
    #   ① 排除其他平台（震坤行 / 1688）
    #   ② 排除京东搜索页
    #   ③ 确认符合京东详情页特征
    valid, reason = validate_detail_html(html)
    if not valid:
        raise ValueError(
            f"京东详情页解析器只接受 item.jd.com/xxx.html 格式的 HTML。\n"
            f"  拒绝原因: {reason}\n"
            f"  提示: 搜索页 HTML 请使用 collect_search.py 解析，\n"
            f"  详情页 HTML 请从 item.jd.com/商品ID.html 手动保存后传入"
        )

    soup = BeautifulSoup(html, "html.parser")
    result = JdDetail(product_id=product_id)
    result.raw_data["html_size"] = len(html)

    # ── 1. 从 pageConfig JSON 提取核心信息 ──
    _extract_page_config(html, result)

    # ── 2. 标题 ──
    _extract_title(soup, result)

    # ── 3. 品牌 ──
    _extract_brand(soup, result)

    # ── 4. 价格 ──
    _extract_price(soup, html, result)

    # ── 5. 店铺 ──
    _extract_shop(soup, result)

    # ── 6. 主图 ──
    _extract_images(soup, result)

    # ── 7. 属性参数 ──
    _extract_attributes(soup, result)

    # ── 新版页面额外提取（新版 JD 架构覆盖） ──
    _extract_new_attributes(html, result)
    _extract_new_shop_info(html, result)
    _extract_new_price(html, result)
    _extract_new_highlight_attrs(html, result)

    # ── 8. 销售数据 ──
    _extract_sales(soup, result)

    # ── 9. 标签 ──
    _extract_tags(soup, result)

    return result


# ═══════════════════════════════════════════════════════════════
#  各字段提取
# ═══════════════════════════════════════════════════════════════

def _extract_page_config(html: str, result: JdDetail):
    """从 <script> 中的 pageConfig JSON 提取 SKU"""
    m = re.search(r'window\.pageConfig\s*=\s*({.*?"product"\s*:\s*{.*?});', html, re.DOTALL)
    if m:
        try:
            config = json.loads(m.group(1))
            prod = config.get("product", {})
            if not result.product_id:
                result.product_id = prod.get("sku", "")
            if not result.title:
                result.title = prod.get("name", "")
            result.raw_data["pageConfig"] = {
                "sku": result.product_id,
                "name": result.title[:80] if result.title else "",
            }
        except json.JSONDecodeError:
            pass

    if not result.product_id:
        m = re.search(r'"sku"\s*:\s*"(\d+)"', html)
        if m:
            result.product_id = m.group(1)


    # ── 新版页面兜底（无 pageConfig） ──
    if not result.product_id:
        m = re.search(r'item\.jd\.com/(\d+)', html)
        if m:
            result.product_id = m.group(1)
    if not result.title:
        m = re.search(r'<title>([^<]+)</title>', html)
        if m:
            title = m.group(1).strip()
            title = re.sub(r'\s*【行情 报价 价格 评测】.*', '', title)
            title = re.sub(r'\s*-\s*京东$', '', title)
            result.title = title.strip()


def _extract_title(soup, result: JdDetail):
    """提取标题"""
    if result.title:
        return

    title_el = soup.select_one(".sku-name")
    if title_el:
        result.title = title_el.get_text(strip=True)
        return

    for sel in [".itemInfo-wrap .p-name", "#name h1", ".product-title"]:
        el = soup.select_one(sel)
        if el:
            result.title = el.get_text(strip=True)
            return

    title_tag = soup.find("title")
    if title_tag:
        raw = title_tag.get_text(strip=True)
        result.title = re.sub(r'\s*[-–—]\s*京东$', '', raw).strip()


def _extract_brand(soup, result: JdDetail):
    """提取品牌"""
    brand_el = _find_param(soup, "品牌")
    if brand_el:
        val = _param_value(brand_el)
        if val:
            result.brand = val
            return

    title = result.title or ""
    known_brands = ["松下", "Panasonic", "雷士", "NVC", "欧普", "OPPLE",
                    "佛山照明", "FSL", "飞利浦", "Philips", "小米", "米家",
                    "美的", "Midea", "欧派", "OPPEIN", "公牛", "霍尼韦尔",
                    "Honeywell", "拉伯塔", "LABOT", "奥普", "京黔"]
    for brand in known_brands:
        if brand in title:
            result.brand = brand
            break


def _extract_price(soup, html: str, result: JdDetail):
    """提取价格"""
    for sel in [".summary-price .price", ".p-price .price", ".summary-wrap .p-price"]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            prices = re.findall(r'¥?([\d.]+)', text)
            floats = [float(p) for p in prices if re.match(r'^\d+\.?\d*$', p) and 0.01 < float(p) < 100000]
            if floats:
                result.price_min = min(floats)
                result.price_max = max(floats)
                return

    m = re.search(r'"jdPrice"\s*:\s*"([\d.]+)"', html)
    if m:
        result.price_min = float(m.group(1))
        return

    prices = re.findall(r'¥?(\d+\.\d{2})', html)
    floats = [float(p) for p in prices if 0.1 < float(p) < 100000]
    if floats:
        result.price_min = min(floats)
        result.price_max = max(floats)


def _extract_shop(soup, result: JdDetail):
    """提取店铺信息"""
    for sel in [".J-hove-wrap .name a", ".shop .name a", ".J-p-comm .name",
                ".shop-name a", ".J-shop-name"]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if text and len(text) > 1:
                result.shop_name = text
                break

    if "自营" in str(soup):
        result.shop_type = "自营"
    if "旗舰店" in result.shop_name:
        result.shop_type = "旗舰店"
    elif "专卖店" in result.shop_name:
        result.shop_type = "专卖店"
    elif "专营店" in result.shop_name:
        result.shop_type = "专营店"
    elif not result.shop_type:
        result.shop_type = "普通店铺"


def _extract_images(soup, result: JdDetail):
    """提取主图

    尝试多种选择器兼容新旧版 JD 页面。
    新版页面保存后图片 src 可能变为本地化路径（_files/xxx.jpg），
    此时保留路径名供后续解析用。
    """
    seen = set()

    # 旧版 JD 选择器
    for sel in [".spec-items img", "#spec-list img", ".lh-wrap img",
                ".preview-thumb img", ".preview-scroll img"]:
        for img in soup.select(sel):
            src = img.get("data-src") or img.get("src", "")
            if src.startswith("//"):
                src = "https:" + src
            if src and src not in seen and "loading" not in src.lower():
                seen.add(src)
                result.main_images.append(src)

    # 新版 JD：spec-n1 容器（browser 保存后 src 本地化）
    if not seen:
        spec = soup.select_one("#spec-n1")
        if spec:
            for img in spec.find_all("img"):
                src = img.get("src", "") or img.get("data-src", "")
                if src and src not in seen and "loading" not in src.lower():
                    seen.add(src)
                    result.main_images.append(src)

    # 兜底：从整个页面搜 360buyimg 图片链接
    if not seen:
        import re
        for url in re.findall(r'https?://[^"\'\s>]+360buyimg[^"\'\s>]*\.(?:jpg|jpeg|png|webp)', str(soup)):
            if url not in seen and "loading" not in url.lower():
                seen.add(url)
                result.main_images.append(url)


def _extract_attributes(soup, result: JdDetail):
    """提取参数规格表"""
    attr_list = soup.select_one(".parameter2.p-parameter-list")
    if not attr_list:
        attr_list = soup.select_one("#product-detail-1 .Ptable-item")

    if attr_list:
        for li in attr_list.find_all("li"):
            text = li.get_text(strip=True)
            if "：" in text:
                key, val = text.split("：", 1)
            elif ":" in text:
                key, val = text.split(":", 1)
            else:
                continue
            key = key.strip()
            val = val.strip()
            if key and val and len(key) < 20:
                result.attributes[key] = val


def _extract_sales(soup, result: JdDetail):
    """提取销售数据"""
    for sel in [".J-sale-data", ".sale-data", ".comment-count .count",
                "#comment-count .count", ".sales-volume"]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            if re.search(r'[\d.万+]+', text):
                result.sales_count = text
                break

    for sel in [".good-rate", ".good-comment-percent", ".percent-con",
                ".comment-percent", ".J-comment-percent"]:
        el = soup.select_one(sel)
        if el:
            text = el.get_text(strip=True)
            m = re.search(r'(\d+%)', text)
            if m:
                result.rating = m.group(1)
                break


def _extract_tags(soup, result: JdDetail):
    """提取页面标签"""
    text = str(soup)
    for tag in ["自营", "百亿补贴", "政府补贴", "明日达",
                "京东秒杀", "京东超市", "仅换不修", "包邮",
                "品质认证", "放心购", "企业价"]:
        if tag in text and tag not in result.tags:
            result.tags.append(tag)


# ═══════════════════════════════════════════════════════════════
#  新版 JD 详情页额外提取函数（React 架构 2025+）
# ═══════════════════════════════════════════════════════════════

def _extract_new_attributes(html: str, result: JdDetail):
    """从新版 JD 属性表提取全部属性

    新版结构：
      <div class="attrs">
        <div class="item ">
          <div class="label"><span class="text"> 品牌</span></div>
          <div class="value"><div class="text" title="松下（Panasonic）">松下</div></div>
        </div>
      </div>
    """
    if 'class="attrs"' not in html:
        return

    attr_pattern = re.compile(
        r'<div\s+class="item[^"]*">\s*'
        r'<div\s+class="label">\s*<span\s+class="text">\s*([^<]+)\s*</span>\s*</div>\s*'
        r'<div\s+class="value">\s*<div\s+class="text"\s+title="([^"]*)"',
        re.DOTALL
    )
    for m in attr_pattern.finditer(html):
        name = m.group(1).strip()
        value = m.group(2).strip()
        if name and value:
            result.attributes[name] = value

    if not result.brand and "品牌" in result.attributes:
        result.brand = result.attributes["品牌"]
    if not result.model and "商品编号" in result.attributes:
        result.model = result.attributes["商品编号"]
    if not result.product_id and "商品编号" in result.attributes:
        result.product_id = result.attributes["商品编号"]


def _extract_new_shop_info(html: str, result: JdDetail):
    m = re.search(r'class="top-name"[^>]*title="([^"]*)"', html)
    if m:
        result.shop_name = m.group(1).strip()
        if "京东自营" in result.shop_name or "自营" in result.shop_name:
            result.shop_type = "自营"
        elif "旗舰店" in result.shop_name:
            result.shop_type = "旗舰店"
        else:
            result.shop_type = "第三方"


def _extract_new_price(html: str, result: JdDetail):
    prices = re.findall(r'<div\s+class="value">([\d.]+)</div>', html)
    if prices:
        vals = []
        for p in prices:
            try:
                vals.append(float(p))
            except ValueError:
                pass
        if vals:
            result.price_min = min(vals)
            result.price_max = max(vals)


def _extract_new_highlight_attrs(html: str, result: JdDetail):
    """提取新版高亮属性（显色指数、最大瓦数、供电方式等）"""
    highlight = re.compile(
        r'<div\s+class="item">\s*'
        r'<div\s+class="title[^"]*">([^<]+)</div>\s*'
        r'<div\s+class="desc">\s*<div\s+class="text[^"]*">([^<]+)</div>',
        re.DOTALL
    )
    for m in highlight.finditer(html):
        name = m.group(2).strip()
        value = m.group(1).strip()
        if name and value:
            result.attributes[name] = value


# ═══════════════════════════════════════════════════════════════
#  辅助函数
# ═══════════════════════════════════════════════════════════════

def _find_param(soup, key: str):
    for item in soup.select(".parameter2.p-parameter-list li"):
        text = item.get_text(strip=True)
        if text.startswith(key) or text.startswith(f"{key} "):
            return item
    return None


def _param_value(el) -> str:
    text = el.get_text(strip=True)
    m = re.match(r'^.+?[：:]\s*(.+)$', text)
    return m.group(1).strip() if m else ""


# ═══════════════════════════════════════════════════════════════
#  转换到 UnifiedDetail
# ═══════════════════════════════════════════════════════════════

def to_unified_detail(jd: JdDetail) -> dict:
    """转换为 core.schema.UnifiedDetail 兼容的字典"""
    return {
        "platform": "京东",
        "product_id": jd.product_id,
        "product_url": f"https://item.jd.com/{jd.product_id}.html" if jd.product_id else "",
        "title": jd.title,
        "brand": jd.brand,
        "spec": jd.model or "",
        "product_code": jd.product_id,
        "price_min": jd.price_min,
        "price_max": jd.price_max,
        "main_images": jd.main_images,
        "detail_images": jd.description_images,
        "attributes": jd.attributes,
        "sku_count": 0,
        "raw_data": jd.raw_data,
    }


# ═══════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="京东详情页解析器 — 只接受 item.jd.com/xxx.html 格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
注意:
  此工具只解析京东商品详情页（item.jd.com/xxx.html）。
  其他平台的页面会被主动拒绝。
  搜索页（search.jd.com/Search）请使用:
    python -m platforms.jingdong.collect_search 目录/ --batch

示例:
  python -m platforms.jingdong.detail_parser detail.html
  python -m platforms.jingdong.detail_parser detail.html --json
        """,
    )
    parser.add_argument("html_file", help="京东商品详情页 HTML 文件 (item.jd.com/xxx.html)")
    parser.add_argument("--json", "-j", action="store_true", help="输出 JSON")
    parser.add_argument("--sku", "-s", help="SKU（可选）")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")

    if not os.path.exists(args.html_file):
        print(f"❌ 文件不存在: {args.html_file}")
        sys.exit(1)

    with open(args.html_file, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    try:
        result = parse_detail(html, product_id=args.sku or "")
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    if args.json:
        output = asdict(result)
        output["raw_data"] = {
            k: v for k, v in result.raw_data.items()
            if isinstance(v, (str, int, float, bool))
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        _print_result(result)


def _print_result(r: JdDetail):
    print("═" * 55)
    print("  京东详情页解析结果")
    print("═" * 55)
    print(f"  SKU:      {r.product_id or '-'}")
    print(f"  标题:     {r.title[:60] if r.title else '-'}")
    print(f"  品牌:     {r.brand or '-'}")
    print(f"  价格:     ¥{r.price_min:.2f} ~ ¥{r.price_max:.2f}" if r.price_max else
          f"  价格:     ¥{r.price_min:.2f}" if r.price_min else "  价格:     -")
    print(f"  店铺:     {r.shop_name or '-'} ({r.shop_type})")
    print(f"  主图:     {len(r.main_images)} 张")
    print(f"  属性:     {len(r.attributes)} 项")
    print(f"  已售:     {r.sales_count or '-'}")
    print(f"  好评率:   {r.rating or '-'}")
    print(f"  标签:     {', '.join(r.tags) if r.tags else '-'}")

    if r.attributes:
        print()
        print("  ── 参数 ──")
        for k, v in list(r.attributes.items())[:15]:
            print(f"    {k}: {v}")
        if len(r.attributes) > 15:
            print(f"    ... 还有 {len(r.attributes) - 15} 项")

    print()
    print("═" * 55)


if __name__ == "__main__":
    main()

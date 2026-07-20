"""
急云/1688 解析器 → UnifiedDetail 适配层

将 急云/1688 开源库的解析器输出映射到 PageHarvest 的统一数据模型。
同时兼容 Ctrl+S（_files/）和 SingleFile（data-sf-original-src）两种保存格式。
"""
import logging
import re
from bs4 import BeautifulSoup
from typing import Optional
from core.schema import UnifiedDetail
from platforms.jiyun.factory import ParserFactory

logger = logging.getLogger(__name__)


def parse_jiyun(html: str) -> Optional[UnifiedDetail]:
    """使用急云/1688 解析器解析 HTML，返回 UnifiedDetail"""
    parser = ParserFactory.create_parser(html)
    if parser is None:
        return None

    info = parser.get_all_info()
    platform = info.get("platform", "unknown")
    platform_map = {"jd": "京东", "alibaba": "1688"}
    unified_platform = platform_map.get(platform, platform)

    # ── 主图 ──
    main_images = []
    # 先尝试急云原生解析
    for url in info.get("main_images", []):
        cleaned = _clean_jd_url(url) if platform == "jd" else url
        if cleaned:
            main_images.append(cleaned)

    # 急云没找到图 → 用 BS4 精确定位 SingleFile 结构
    if not main_images and platform == "jd":
        main_images = _extract_jd_main_images_from_soup(html)

    # ── 详情图（仅展示前 5 张，完整列表用于图包下载） ──
    detail_images_all = []
    for url in info.get("detail_images", []):
        cleaned = _clean_jd_url(url) if platform == "jd" else url
        if cleaned:
            detail_images_all.append(cleaned)

    if not detail_images_all and platform == "jd":
        detail_images_all = _extract_jd_detail_images_from_soup(html)

    # 详情图展示仅限前 5 张
    detail_images = detail_images_all[:5]

    # ── 属性 ──
    attrs = {}
    for name, val in info.get("attributes", []):
        if name and val:
            attrs[name] = val

    # ── 价格 ──
    price_info = info.get("price", {}) or {}
    price_min = 0.0
    price_max = 0.0
    if isinstance(price_info, dict):
        # 急云价格格式: {main_price: {price: 21.9, min_amount: 1}, ...}
        main_price = price_info.get("main_price", {}) or {}
        if isinstance(main_price, dict):
            price_min = float(main_price.get("price", 0) or 0)
        if not price_min:
            price_min = float(price_info.get("price", 0) or 0)
        price_max = float(price_info.get("original_price", 0) or 0)

    # ── 标题/品牌 ──
    title = info.get("title", "") or _extract_title(html)
    brand = ""
    for name, val in attrs.items():
        if "品牌" in name:
            brand = val
            break

    # 构建 UnifiedDetail
    all_images_combined = list(dict.fromkeys(main_images + detail_images_all))
    return UnifiedDetail(
        platform=unified_platform,
        product_id=info.get("product_code", "") or "",
        product_url=info.get("product_url", "") or "",
        title=title,
        brand=brand,
        spec=attrs.get("型号", ""),
        product_code=info.get("product_code", "") or "",
        price_min=price_min,
        price_max=price_max if price_max > price_min else price_min,
        min_order=info.get("min_order", 1),
        ship_from=info.get("ship_from", "") or "",
        sales_count=info.get("sales_count", 0) or 0,
        main_images=main_images,
        detail_images=detail_images,
        all_images=all_images_combined,
        videos=info.get("videos", []),
        sku_count=len(info.get("color_options", [])),
        attributes=attrs,
    )


# ── JD SingleFile 专有提取 ──


def _extract_jd_main_images_from_soup(html: str) -> list[str]:
    """从 SingleFile JD 页面提取主图

    Track 0: .image-carousel-track > .item > img.image → 主图缩略图
    spec-n1:  主展示图
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    images: list[str] = []

    # 策略 1: image-carousel-track 的 Track 0 — 主图轮播缩略图
    tracks = soup.select(".image-carousel-track")
    for track in tracks:
        items = track.select(".item")
        for item in items:
            imgs = item.select("img.image[data-sf-original-src]")
            for img in imgs:
                url = img.get("data-sf-original-src", "")
                if url and "/imagetool" not in url:
                    clean = _clean_jd_url(url)
                    if clean and clean not in seen:
                        seen.add(clean)
                        images.append(clean)
        # 只取第一个 track（主图轮播）
        if images:
            break

    # 策略 2: spec-n1 中的主展示图（补充，去重）
    spec_n1 = soup.select_one("#spec-n1")
    if spec_n1:
        for el in spec_n1.select("[data-sf-original-src]"):
            url = el.get("data-sf-original-src", "")
            if url and "/imagetool" not in url:
                clean = _clean_jd_url(url)
                if clean and clean not in seen:
                    seen.add(clean)
                    images.append(clean)

    return images


def _extract_jd_detail_images_from_soup(html: str) -> list[str]:
    """从 SingleFile JD 页面提取详情描述图

    Track 1-2: .image-carousel-track > .item > img.pc-component-__image_main__
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    images: list[str] = []

    tracks = soup.select(".image-carousel-track")
    for ti, track in enumerate(tracks):
        if ti == 0:
            continue  # Track 0 是主图，已处理
        items = track.select(".item")
        for item in items:
            imgs = item.select("img.pc-component-__image-main__[data-sf-original-src], "
                               "img.img[data-sf-original-src]")
            for img in imgs:
                url = img.get("data-sf-original-src", "")
                if url and "/imagetool" not in url:
                    clean = _clean_jd_url(url)
                    if clean and clean not in seen:
                        seen.add(clean)
                        images.append(clean)

    return images


def _clean_jd_url(url: str) -> str:
    """清理京东图片 URL"""
    if not url:
        return url
    url = url.rstrip(".avif")
    url = re.sub(r"/s\d+x\d+_jfs/", "/jfs/", url)
    return url


def _extract_title(html: str) -> str:
    """从 HTML 中提取标题"""
    m = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    if m:
        title = m.group(1).strip()
        title = re.sub(r"【.*?】.*", "", title).strip()
        title = re.sub(r"\s*-\s*京东.*", "", title).strip()
        return title
    return ""


def detect_singlefile(html: str) -> bool:
    """检测是否为 SingleFile 保存格式"""
    return "SingleFile" in html or "data-sf-original-src" in html

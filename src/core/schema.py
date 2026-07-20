"""
统一数据模型（Unified Schema）
所有平台的数据最终归一化到这里，支持搜索页和详情页两个层次。
"""

from dataclasses import dataclass, field
from typing import Optional


# ── 搜索层：商品列表 ──

@dataclass
class UnifiedProduct:
    """搜索页商品（所有平台统一）"""
    # ── 身份字段 ──
    platform: str                  # "1688" / "京东"
    product_id: str                # 平台原生ID (offerId / sku)
    product_url: str               # 详情页链接

    # ── 核心字段 ──
    title: str
    price_min: float = 0.0         # 最低价（到手价）
    price_max: float = 0.0         # 最高价（划线价/原价）
    currency: str = "CNY"
    shop_name: str = ""
    shop_type: str = ""            # "自营" / "旗舰店" / "普通店铺"
    brand: str = ""

    # ── 销售指标 ──
    sales_text: str = ""           # 原始销量文本（"已售5万+" / "年销量1234"）
    review_count: int = 0
    rating: float = 0.0            # 好评率 / 评分

    # ── 标记 ──
    is_ad: bool = False
    is_self_operated: bool = False
    tags: list = field(default_factory=list)

    # ── 媒体 ──
    image_url: str = ""

    # ── 平台原始数据（兜底） ──
    raw_data: dict = field(default_factory=dict)


# ── 详情层：商品详情 ──

@dataclass
class UnifiedDetail:
    """详情页商品（所有平台统一）"""
    platform: str
    product_id: str
    product_url: str

    # ── 基础 ──
    title: str = ""
    brand: str = ""
    spec: str = ""               # 型号
    product_code: str = ""       # 货号

    # ── 交易信息 ──
    price_min: float = 0.0
    price_max: float = 0.0
    min_order: int = 1           # 起批量
    ship_from: str = ""          # 发货地

    # ── 销售数据 ──
    sales_count: int = 0
    yearly_sales: str = ""
    repurchase_rate: str = ""
    listing_date: str = ""

    # ── 媒体 ──
    main_images: list = field(default_factory=list)
    detail_images: list = field(default_factory=list)
    videos: list = field(default_factory=list)

    # ── SKU ──
    sku_count: int = 0
    attributes: dict = field(default_factory=dict)
    sku_matrix: list = field(default_factory=list)
    color_options: list = field(default_factory=list)

    # ── 平台原始数据 ──
    raw_data: dict = field(default_factory=dict)


# ── 分析报告 ──

@dataclass
class AnalysisReport:
    """分析报告"""
    platform: str
    keyword: str
    total_products: int
    suppliers: int
    price_min: float
    price_max: float
    price_median: float
    price_avg: float
    distribution: dict = field(default_factory=dict)   # 价格区间分布
    top_suppliers: list = field(default_factory=list)  # 头部供应商
    top_categories: list = field(default_factory=list) # 品类分布
    brands_found: int = 0
    report_text: str = ""

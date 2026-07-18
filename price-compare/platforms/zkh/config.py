"""震坤行平台配置"""

PLATFORM_NAME = "震坤行"

# 搜索 URL 模板
SEARCH_URL = "https://www.zkh.com/search.html?keywords={keyword}"

# 搜索结果在 SSR 数据中的 key（按优先级尝试）
INITIAL_DATA_KEYS = ["productList", "list", "data.list"]

# Playwright 等待选择器（等待 SSR 数据渲染完成）
WAIT_SELECTOR = "#__NEXT_DATA__,#__NUXT__,script"

# 是否使用 Playwright（True=Playwright, False=requests）
USE_PLAYWRIGHT = True

# 价格 DOM 选择器
PRICE_SELECTOR = ".sku-price-wrap-new"
PRICE_INTEGER_SELECTOR = ".sku-price-wrap-new .integer"
PRICE_DECIMAL_SELECTOR = ".sku-price-wrap-new .decimal"
PRICE_UNIT_SELECTOR = ".sku-price-wrap-new .unit"

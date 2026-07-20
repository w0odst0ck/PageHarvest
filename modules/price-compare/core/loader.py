"""加载输入文件，统一为标准商品列表"""

import pandas as pd
from .logger import get_logger

log = get_logger()

# 列名映射（导出文件 → 内部统一字段）
COLUMN_MAP = {
    '任务Id': 'task_id',
    '申请单Id': 'apply_id',
    '信息提交时间': 'submit_time',
    '询价商品管理状态': 'status',
    '平台商品名称': 'name',
    '原商品名称': 'origin_name',
    '数量': 'qty',
    '品牌名称': 'brand',
    '型号': 'model',
    '配置参数': 'params',
    '用户组': 'user_group',
    '成本价': 'cost',
    '建议对外报价': 'our_price',
    '是否议价': 'is_negotiated',
    '首次报价': 'first_price',
    '平台SKU编码': 'sku',
    '公司名称': 'company',
    '询价商品类型': 'inquiry_type',
    '项目名称': 'project',
    '价格到期日': 'price_expire',
    '无法报价说明': 'cannot_reason',
    '是否指定品牌': 'is_brand_specified',
    '是否允许替换': 'is_replace_allowed',
    '任务派发时间标准格式': 'dispatch_time',
}


def load(filepath: str) -> list[dict]:
    """
    读取询价单 Excel，返回标准格式的商品列表

    返回:
        [
            {
                "sku": "1862184104972",
                "brand": "敏华",
                "model": "M-ZFZD-E5W3004",
                "name": "敏华 应急灯 ...",
                "params": "5W纳米板...",
                "cost": 30.8,
                "our_price": 33.5,
                "qty": 2,
                "company": "安徽科百隆...",
                "project": "安庆市经开区...",
                "origin_name": "应急灯",
            },
            ...
        ]
    """
    engine = 'xlrd' if str(filepath).endswith('.xls') else 'openpyxl'
    raw = pd.read_excel(filepath, sheet_name=0, engine=engine)

    # 重命名列
    df = raw.rename(columns=COLUMN_MAP)

    # 只保留目标列
    keep_cols = [c for c in COLUMN_MAP.values() if c in df.columns]
    df = df[keep_cols]

    # 数值处理
    for c in ['cost', 'our_price', 'first_price']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    # 转 dict
    products = df.to_dict(orient='records')

    log.info("LOADER", f"读取 {len(products)} 条商品")
    return products

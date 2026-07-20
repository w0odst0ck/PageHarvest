"""
品牌识别工具 — 从标题/店铺名提取品牌
仅由 api/ 层使用，不依赖任何原始代码。
"""
import re

# 已知品牌列表（按长度降序排列，优先匹配长名）
KNOWN_BRANDS = sorted([
    # 进口/合资
    "PHILIPS", "Philips", "飞利浦",
    "Panasonic", "松下",
    "欧司朗", "OSRAM",
    "GE",
    "西门子", "SIEMENS",
    "ABB",
    "施耐德", "Schneider",
    "三菱",
    # 国内一线
    "OPPLE", "欧普照明", "欧普",
    "NVC", "雷士照明", "雷士",
    "FSL", "佛山照明",
    "公牛", "BULL",
    "TCL照明", "TCL",
    "美的", "Midea",
    "小米", "米家", "MIJIA",
    "华为", "HUAWEI",
    "正泰", "CHNT",
    "德力西", "DELIXI",
    "三雄极光", "Pak",
    "阳光照明", "阳光",
    "华荣",
    "尚为",
    "海康威视", "HIKVISION",
    "大华",
    # 国际品牌
    "SATA", "世达",
    "SUPERFIRE", "神火",
    "MANVA", "敏华电工", "敏华",
    "惠普", "HP",
    "四季沐歌", "MICOE",
    # 京东常见补充
    "京东京造",
    "顾家家居", "顾家",
    "探路蜂",
    "万火", "ONEFIRE",
    "欧派", "OPPEIN",
    # 1688 常见
    "锦明",
    "家灯日记",
    "乐鹏",
], key=lambda x: -len(x))


def extract_brand(title: str, shop_name: str = "") -> str:
    """从标题或店铺名提取品牌"""
    if not title and not shop_name:
        return ""

    for b in KNOWN_BRANDS:
        if b in title:
            return b
        if b in shop_name:
            return b

    # Fallback: 从店铺名提取（去掉常见后缀）
    if shop_name:
        cleaned = shop_name
        for suffix in ["京东自营旗舰店", "官方旗舰店", "旗舰店", "京东自营", "自营旗舰店", "自营"]:
            cleaned = cleaned.replace(suffix, "")
        cleaned = cleaned.strip()
        if cleaned and len(cleaned) <= 10:
            return cleaned

    return ""

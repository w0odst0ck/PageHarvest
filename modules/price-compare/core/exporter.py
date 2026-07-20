"""合并各平台结果，输出比价表"""

import os
import pandas as pd
from .logger import get_logger

log = get_logger()


def export(products: list[dict], platform_results: dict, output_dir: str):
    """
    汇总并输出 price_compare.xlsx

    Args:
        products: loader 输出的标准商品列表
        platform_results: { "1688": {...}, "震坤行": {...} }
        output_dir: 输出目录
    """
    os.makedirs(output_dir, exist_ok=True)

    rows = []
    for prod in products:
        sku = prod.get('sku', '')

        row = {
            '河姆渡SKU': sku,
            '商品名称': prod.get('name', ''),
            '品牌': prod.get('brand', ''),
            '型号': prod.get('model', ''),
            '成本价': prod.get('cost', ''),
            '河姆渡报价': prod.get('our_price', ''),
            '数量': prod.get('qty', 0),
            '客户': prod.get('company', ''),
            '项目': prod.get('project', ''),
        }

        # 计算河姆渡毛利率
        cost = prod.get('cost') or 0
        price = prod.get('our_price') or 0
        if cost > 0:
            row['河姆渡毛利率'] = round((price - cost) / cost * 100, 1)
        else:
            row['河姆渡毛利率'] = ''

        # 遍历各平台匹配结果
        all_prices = []
        for pname, presult in platform_results.items():
            matched = None
            for r in presult.get('results', []):
                if r.get('sku') == sku:
                    matched = r
                    break
            if matched and matched.get('price') is not None:
                row[pname] = matched['price']
                row[f'{pname}_置信度'] = matched.get('confidence', '')
                row[f'{pname}_标题'] = matched.get('title', '')
                all_prices.append(matched['price'])
            else:
                row[pname] = ''
                row[f'{pname}_置信度'] = ''
                row[f'{pname}_标题'] = ''

        # 全平台最低价 + 价差
        if all_prices:
            min_price = min(all_prices)
            row['全平台最低价'] = min_price
            row['价差(河-最低)'] = round(price - min_price, 2) if price else ''
            if price > 0 and min_price > 0:
                ratio = round((price - min_price) / min_price * 100, 1)
                row['溢价(河比最低高%)'] = ratio
            else:
                row['溢价(河比最低高%)'] = ''
        else:
            row['全平台最低价'] = ''
            row['价差(河-最低)'] = ''
            row['溢价(河比最低高%)'] = ''

        rows.append(row)

    # 输出 Sheet 1: 比价总览
    df_main = pd.DataFrame(rows)
    path_main = os.path.join(output_dir, 'price_compare.xlsx')

    with pd.ExcelWriter(path_main, engine='openpyxl') as writer:
        df_main.to_excel(writer, sheet_name='比价总览', index=False)

    # 输出 Sheet 2: 未匹配清单
    unmatched_rows = []
    for pname, presult in platform_results.items():
        for u in presult.get('unmatched', []):
            unmatched_rows.append({
                '平台': pname,
                '河姆渡SKU': u.get('sku', ''),
                '商品名称': u.get('name', ''),
                '品牌': u.get('brand', ''),
                '型号': u.get('model', ''),
                '可能原因': u.get('reason', ''),
            })

    if unmatched_rows:
        df_unmatched = pd.DataFrame(unmatched_rows)
        with pd.ExcelWriter(path_main, engine='openpyxl', mode='a') as writer:
            df_unmatched.to_excel(writer, sheet_name='未匹配清单', index=False)

    log.info("EXPORTER", f"比价表已输出: {path_main}")

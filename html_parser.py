import os
import re
import csv
import sys
from bs4 import BeautifulSoup

def run_parser1(html_content, base_dir):
    """
    解析第一种 HTML 结构（参考 parser.py 逻辑）
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    item_wrappers = soup.find_all("div", class_="sku-item-wrapper")
    print(f"共找到 {len(item_wrappers)} 个 sku 项。")
    data_rows = []
    # 正则表达式：支持 " 或 &quot; 引号格式，提取背景图片 URL
    url_pattern = re.compile(r'url\(\s*(?:"|&quot;)(.*?)(?:"|&quot;)\s*\)')
    
    for wrapper in item_wrappers:
        img_div = wrapper.find("div", class_="sku-item-image")
        if img_div and 'style' in img_div.attrs:
            style = img_div['style']
            match = url_pattern.search(style)
            if match:
                img_url = match.group(1)
            else:
                print("无法解析图片URL:", style)
                continue
        else:
            print("未找到图片 div。")
            continue

        name_div = wrapper.find("div", class_="sku-item-name")
        if name_div:
            item_name = name_div.get_text(strip=True)
        else:
            print("未找到商品名称")
            continue

        price_div = wrapper.find("div", class_="discountPrice-price")
        if price_div:
            price_text = price_div.get_text(strip=True)
        else:
            print("未找到商品价格")
            price_text = ""

        data_rows.append({
            "商品名称": item_name,
            "图片地址": img_url,
            "价格": price_text,
        })
    
    # 确保目录存在
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    
    # 在指定目录下保存CSV文件
    csv_file = os.path.join(base_dir, "sku_data.csv")
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ["商品名称", "图片地址", "价格"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in data_rows:
            writer.writerow(row)
    
    print(f"数据已保存到: {os.path.abspath(csv_file)}")

def run_parser2(html_content, base_dir):
    """
    解析第二种 HTML 结构（参考 parser2.py 逻辑）
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. 提取颜色数据
    colors = []
    color_container = soup.find("div", class_="prop-item-wrapper")
    if color_container:
        prop_items = color_container.find_all("div", class_="prop-item")
        for item in prop_items:
            inner = item.find("div", class_="prop-item-inner-wrapper")
            if inner:
                img_div = inner.find("div", class_="prop-img")
                name_div = inner.find("div", class_="prop-name")
                if img_div and name_div and "style" in img_div.attrs:
                    color_name = name_div.get_text(strip=True)
                    pattern = re.compile(r'url\(\s*(?:"|&quot;)(.*?)(?:"|&quot;)\s*\)')
                    match = pattern.search(img_div['style'])
                    img_url = match.group(1) if match else ""
                    colors.append({
                        "颜色": color_name,
                        "颜色图片地址": img_url,
                    })
    else:
        print("未找到颜色选项容器。")
    
    # 2. 提取尺码 SKU 数据
    sizes = []
    sku_container = soup.find("div", id="sku-count-widget-wrapper")
    if sku_container:
        sku_items = sku_container.find_all("div", class_="sku-item-wrapper")
        for item in sku_items:
            left_div = item.find("div", class_="sku-item-left")
            if left_div:
                sku_name_div = left_div.find("div", class_="sku-item-name")
                price_div = left_div.find("div", class_="discountPrice-price")
                size_text = sku_name_div.get_text(strip=True) if sku_name_div else ""
                price_text = price_div.get_text(strip=True) if price_div else ""
                sizes.append({
                    "尺码": size_text,
                    "价格": price_text,
                })
    else:
        print("未找到尺码 SKU 容器。")
    
    if not colors:
        print("没有提取到颜色数据。")
    if not sizes:
        print("没有提取到尺码数据。")
    
    # 3. 组合数据：生成笛卡尔积
    combined_rows = []
    for color_item in colors:
        for size_item in sizes:
            row = {
                "颜色": color_item.get("颜色", ""),
                "图片地址": color_item.get("颜色图片地址", ""),
                "尺码": size_item.get("尺码", ""),
                "价格": size_item.get("价格", ""),
            }
            combined_rows.append(row)
    
    # 确保目录存在
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    
    # 在指定目录下保存CSV文件
    csv_file = os.path.join(base_dir, "sku_data.csv")
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ["颜色", "图片地址", "尺码", "价格"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in combined_rows:
            writer.writerow(row)
    
    print(f"共生成 {len(combined_rows)} 条数据，已保存到: {os.path.abspath(csv_file)}")

def run_parser3(html_content, base_dir):
    """
    解析第三种 HTML 结构（简单商品列表结构）
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    item_wrappers = soup.find_all("div", class_="sku-item-wrapper")
    print(f"共找到 {len(item_wrappers)} 个 sku 项。")
    data_rows = []
    
    for wrapper in item_wrappers:
        left_div = wrapper.find("div", class_="sku-item-left")
        if not left_div:
            print("未找到商品信息区域")
            continue
            
        name_div = left_div.find("div", class_="sku-item-name")
        if name_div:
            item_name = name_div.get_text(strip=True)
        else:
            print("未找到商品名称")
            continue

        price_div = left_div.find("div", class_="discountPrice-price")
        if price_div:
            price_text = price_div.get_text(strip=True)
        else:
            print("未找到商品价格")
            price_text = ""
            
        stock_div = left_div.find("div", class_="sku-item-sale-num")
        if stock_div:
            stock_text = stock_div.get_text(strip=True)
        else:
            print("未找到库存信息")
            stock_text = ""

        data_rows.append({
            "商品名称": item_name,
            "价格": price_text,
            "库存": stock_text
        })
    
    # 确保目录存在
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
    
    # 在指定目录下保存CSV文件
    csv_file = os.path.join(base_dir, "sku_data.csv")
    with open(csv_file, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = ["商品名称", "价格", "库存"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in data_rows:
            writer.writerow(row)
    
    print(f"数据已保存到: {os.path.abspath(csv_file)}")

def main():
    # 获取当前脚本的绝对路径
    script_path = os.path.abspath(__file__)
    # 获取当前脚本所在目录
    script_dir = os.path.dirname(script_path)
    
    # 如果脚本在项目根目录，直接使用项目根目录
    if os.path.basename(script_dir) == "1688" or os.path.exists(os.path.join(script_dir, "main.py")):
        base_dir = script_dir
    # 如果脚本在src/parser目录下
    elif os.path.basename(script_dir) == "parser" and os.path.basename(os.path.dirname(script_dir)) == "src":
        base_dir = os.path.dirname(os.path.dirname(script_dir))
    # 其他情况，假设脚本在项目根目录
    else:
        base_dir = script_dir
    
    # 打印路径信息以便调试
    print(f"脚本路径: {script_path}")
    print(f"项目根目录: {base_dir}")
    
    # 指定data目录作为输出目录
    data_dir = os.path.join(base_dir, "data")
    print(f"数据目录: {data_dir}")
    
    # 使用基准目录构建HTML文件的完整路径
    html_file = os.path.join(data_dir, "output.html")
    print(f"尝试读取HTML文件: {html_file}")
    
    if not os.path.exists(html_file):
        print(f"文件不存在: {html_file}")
        
        # 尝试在当前目录查找
        alt_html_file = os.path.join(os.getcwd(), "data", "output.html")
        print(f"尝试备选路径: {alt_html_file}")
        
        if os.path.exists(alt_html_file):
            print(f"找到HTML文件: {alt_html_file}")
            html_file = alt_html_file
        else:
            print("备选路径也不存在")
            sys.exit(1)
    else:
        print(f"找到HTML文件: {html_file}")
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 精确判断逻辑：按优先级检查三种结构
    is_parser2 = False
    is_parser1 = False
    is_parser3 = False
    
    # 1. 首先检查第二种结构（颜色+尺码）
    prop_container = soup.find("div", class_="prop-item-wrapper")
    sku_count_container = soup.find("div", id="sku-count-widget-wrapper")
    if prop_container and sku_count_container:
        print("检测到第二种 HTML 结构（颜色+尺码），调用 parser2.py 逻辑")
        run_parser2(html_content, data_dir)
        is_parser2 = True
    else:
        # 2. 检查第一种结构（带图片的商品项）
        sku_wrappers = soup.find_all("div", class_="sku-item-wrapper")
        for wrapper in sku_wrappers:
            if wrapper.find("div", class_="sku-item-image") and wrapper.find("div", class_="discountPrice-price"):
                is_parser1 = True
                break
                
        # 3. 检查第三种结构（简单商品列表）
        if not is_parser1:
            for wrapper in sku_wrappers:
                left_div = wrapper.find("div", class_="sku-item-left")
                if left_div and left_div.find("div", class_="sku-item-name") and left_div.find("div", class_="discountPrice-price"):
                    is_parser3 = True
                    break
        
        if is_parser1:
            print("检测到第一种 HTML 结构（带图片商品项），调用 parser.py 逻辑")
            run_parser1(html_content, data_dir)
        elif is_parser3:
            print("检测到第三种 HTML 结构（简单商品列表），调用 parser3 逻辑")
            run_parser3(html_content, data_dir)
        else:
            print("未能识别 HTML 结构，无法选择解析器")

if __name__ == "__main__":
    main()

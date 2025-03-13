import time
import os
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
import sys
import logging
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# 启用调试日志
#logging.basicConfig(level=logging.DEBUG)

def scrape_1688(url):
    print("正在初始化Chrome选项...")
    # 设置Chrome选项
    options = uc.ChromeOptions()
    
    # 获取当前脚本所在目录的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 指定用户数据目录
    chrome_profile = os.path.join(current_dir, "chrome_profile")
    
    # 确保目录存在
    if not os.path.exists(chrome_profile):
        print(f"创建用户数据目录: {chrome_profile}")
        os.makedirs(chrome_profile)
    else:
        print(f"使用已存在的用户数据目录: {chrome_profile}")
        
    options.add_argument(f'--user-data-dir={chrome_profile}')
    
    # 如需使用无头模式，可取消下面一行注释
    # options.headless = True
    # 添加更多反爬虫配置
    options.add_argument('--disable-blink-features=AutomationControlled')  # 关闭自动化标记
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36 ')
   
    try:
        print("正在启动Chrome浏览器（首次启动可能需要一些时间）...")
        driver_executable_path = r".\chromedriver-win32\chromedriver.exe"
        driver = uc.Chrome(options=options, driver_executable_path=driver_executable_path)
        # driver = uc.Chrome(options=options)
        print("浏览器启动成功，正在访问目标页面...")
        driver.get(url)
      
        # 等待页面加载，确保动态内容加载完成
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "sku-item-wrapper"))
        )
        
        html_content = driver.page_source
        with open(r".\data\output.html", "w", encoding="utf-8") as f:
            f.write(html_content)
            
        print("页面内容已保存")
        # 解析页面内容
        soup = BeautifulSoup(html_content, "html.parser")
        # 根据需要进一步解析soup内容
    except Exception as e:
        print("发生错误:", str(e))
    finally:
        if 'driver' in locals():
            driver.quit()

if __name__ == "__main__":
    # url = "https://detail.1688.com/offer/645192958830.html?spm=a261y.25179003.137725730154361.4.52b63773CCXUTY&sk=consign" #单个商品信息案例
    url = "https://detail.1688.com/offer/863498322785.html?offerId=863498322785&spm=a260k.home2024.recommendpart.22" #双重商品信息案例
    # url = "https://detail.1688.com/offer/850519838351.html?sk=consign&__tdScene__=jxhy-od&&spm=a21vf6.result.0.i3" #简单商品信息案例
    # url = "https://detail.1688.com/offer/739997259706.html?offerId=739997259706&spm=a260k.home2024.recommendpart.26"
    
    scrape_1688(url)

    # 使用 sys.executable 确保调用的是当前环境中的 Python 解释器
    script2_path = r".\html_parser.py"  # 请将此路径替换为实际的脚本2路径
    os.system(f'"{sys.executable}" {script2_path}')
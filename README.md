# 1688商品数据爬取工具

这是一个用于爬取1688.com商品详情页数据的Python工具。该工具使用无头浏览器技术，能够绕过反爬虫机制，实现稳定的数据采集。

## 功能特点

- 支持1688商品详情页数据爬取
- 使用undetected-chromedriver绕过反爬虫检测
- 支持动态页面内容加载
- 自动保存页面内容并解析商品数据
- 提供API接口支持

## 系统要求

- Python 3.6+
- Chrome浏览器
- Windows操作系统（其他系统需要相应修改ChromeDriver路径）

## 安装说明

1. 克隆项目到本地：
```bash
git clone [项目地址]
cd 1688-scraper
```

2. 创建并激活虚拟环境（推荐）：
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
```

3. 安装依赖包：
```bash
pip install -r requirements.txt
```

4. 确保Chrome浏览器已安装，并下载对应版本的ChromeDriver（项目中已包含）

## 目录结构

```
├── main.py              # 主程序入口
├── api.py              # API接口实现
├── html_parser.py      # HTML解析模块
├── requirements.txt    # 项目依赖
├── chrome_profile/    # Chrome用户配置目录
├── chromedriver-win32/ # ChromeDriver文件
└── data/              # 数据存储目录
```

## 使用方法

1. 直接运行爬虫：
```bash
python main.py
```

2. 通过API使用：
```bash
python api.py
```
API服务将在 http://localhost:5000 启动

### API端点

- POST `/api/scrape`
  - 参数：`{"url": "商品详情页URL"}`
  - 返回：商品详细信息（JSON格式）

## 注意事项

1. 首次运行时会自动创建Chrome用户配置文件
2. 如遇到反爬虫检测，可能需要手动完成验证
3. 建议使用稳定的网络连接
4. 遵守1688平台的使用条款和爬虫规范

## 许可证

[添加许可证信息]

## 贡献指南

欢迎提交Issue和Pull Request来帮助改进项目。

## 联系方式

[添加联系方式] 
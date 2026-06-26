# 1688 智能照明商品数据采集 & 分析工具

> 从 1688 搜索结果页到商品详情页的完整数据链路：搜索页采集 → 清洗分析 → 精选 → 详情页深度采集。

---

## 项目概述

两个阶段的数据管线：

**第一阶段（搜索层）** — 油猴脚本自动翻页采集 1688 搜索列表页，Python 管线解析、清洗、分析，输出品类全貌报告。

**第二阶段（详情层）** — 精选 Top 供应商的商品，用 Selenium 下载详情页 HTML，再用 [急云/1688](https://github.com/jiyun/1688) 开源库提取品牌、SKU、主图、详情图、视频、属性等深度数据。

---

## 📂 项目结构

```
1688-scrapy/
│
├── pipeline/                        # 核心管线
│   ├── 01_fetch.user.js             # 油猴脚本 — 翻页 + 滚动 + 下载 HTML
│   ├── 02_parse.py                  # HTML → CSV 解析（17 字段）
│   ├── 03_clean.py                  # 数据清洗（去重 + 价格 + 品牌）
│   ├── 04_analyze.py                # 数据分析 + 图表生成
│   ├── 05_manual_urls.py            # 手动录入精选商品详情页 URL
│   ├── 06_detail_collector.py       # Selenium 下载详情页 + 1688库解析
│   ├── 07_process_with_1688lib.py   # 调用 1688 库全流程处理（下载资源）
│   ├── run1.py                      # 一键运行：搜索页管线（解析→清洗→分析）
│   ├── run2.py                      # 一键运行：详情页管线（录入→解析→资源）
│
├── 1688/                            # 1688 详情页资源采集工具（第三方开源库）
│   └── 1688/
│       ├── main.py                  # 主程序入口
│       ├── start1688.bat            # 拖放 HTML 启动处理
│       ├── config.py                # 配置文件
│       └── utils/parsers/
│           └── alibaba_parser.py    # ★ 核心解析器（品牌、SKU、图片等）
│
├── data/                            # 数据目录
│   ├── 户外灯具/                     # 品类文件夹
│   │   ├── (*.html)                 # 搜索页原始 HTML（油猴采集）
│   │   ├── all_products.csv         # 解析后的原始数据
│   │   ├── cleaned_products.csv     # 清洗去重后的数据
│   │   ├── analysis_report.txt      # 分析报告
│   │   ├── analysis_chart.png       # 可视化图表
│   │   ├── top_products_urls.csv    # 精选商品详情页 URL
│   │   ├── top_products_details.csv # 精选商品详情数据汇总
│   │   └── products_detail/         # 详情页 HTML + 解析结果
│   │       └── {offer_id}/
│   │           ├── {offer_id}.html
│   │           ├── _resources.txt
│   │           └── _1688_parsed.txt
│   └── 投光灯/                       # 同上
│
├── chromedriver-win32/              # ChromeDriver（Selenium 用）
├── chrome_profile/                  # Chrome 用户数据（保持登录态）
├── requirements.txt                 # Python 依赖
└── README.md
```

---

## 🔧 使用流程

```
第一阶段：搜索页采集
═══════════════════════════════════════════
 ① 安装油猴脚本 (01_fetch.user.js)
 ② 打开 1688 搜索关键词 → 自动翻页 34 页
 ③ 将 HTML 移到 data/品类名/
 ④ run1.py --cat 品类名 (解析+清洗+分析)

                      ↓
第二阶段：精选详情采集
═══════════════════════════════════════════
 ⑤ 看分析报告 → 圈定目标商品
 ⑥ 05_manual_urls.py → 手动录入详情页 URL
 ⑦ 06_detail_collector.py → 下载+解析详情页
 ⑧ run2.py --cat 品类名 (全流程自动化)
```

### 第一阶段：搜索页分析

```powershell
# 一键跑完搜索页（解析 → 清洗 → 分析）
.venv\Scripts\python.exe pipeline\run1.py --cat 投光灯

# 或分步执行
.venv\Scripts\python.exe pipeline\02_parse.py --cat 投光灯
.venv\Scripts\python.exe pipeline\03_clean.py --cat 投光灯
.venv\Scripts\python.exe pipeline\04_analyze.py --cat 投光灯
```

### 第二阶段：详情页深度采集

```powershell
# 一键跑完详情页（手动录入 → 下载 → 解析 → 资源下载）
.venv\Scripts\python.exe pipeline\run2.py --cat 投光灯

# 或分步执行
.venv\Scripts\python.exe pipeline\05_manual_urls.py --cat 投光灯
.venv\Scripts\python.exe pipeline\06_detail_collector.py --cat 投光灯
.venv\Scripts\python.exe pipeline\07_process_with_1688lib.py --cat 投光灯
```

---

## 📋 数据字段

### 搜索层（17 列）

| 字段 | 说明 | 来源 |
|------|------|------|
| `title` | 商品标题 | 搜索页 |
| `price` | 价格 | 搜索页 |
| `shop_name` | 供应商名称 | 搜索页 |
| `yearly_sales` | 年销量 | 搜索页插件 |
| `return_rate` | 回头率 | 搜索页插件 |
| `shop_age` | 经营时长 | 搜索页插件 |
| `category` | 品类 | 搜索页插件 |

### 详情层（补充字段）

| 字段 | 说明 | 来源（AlibabaParser） |
|------|------|---|
| `brand` | 品牌 | `get_attributes()` |
| `spec / product_code` | 型号 / 货号 | `get_attributes() / get_product_code()` |
| `ship_from` | 发货地 | `get_ship_from()` |
| `min_order` | 起批量 | `get_min_order()` |
| `sales_count` | 销量 | `get_sales_count()` |
| `main_images` | 主图 URL 列表 | `get_main_images()` |
| `detail_images` | 详情图 URL 列表 | `get_detail_images()` |
| `videos` | 视频 URL | `get_videos()` |
| `attributes` | 属性列表（品牌/型号/材质等） | `get_attributes()` |
| `sku_matrix` | SKU 矩阵（规格/价格/库存） | `get_sku_matrix()` |
| `color_options` | 色卡选项 | `get_color_options()` |
| `listing_date` | 上架时间 | `get_plugin_data()` |
| `yearly_sales_pieces` | 年成交件数 | `get_plugin_data()` |
| `repurchase_rate` | 复购率 | `get_trend_data()` |

---

## ✅ 当前状态

| 品类 | 搜索页 | 详情页 |
|------|--------|--------|
| 户外灯具 | ✅ 已完成 | ⏳ |
| 投光灯 | ✅ 已完成 | ✅ Top 10 |
| 照明配套 | ⏳ | ⏳ |
| 面板灯 | ⏳ | ⏳ |
| 吸顶灯 | ⏳ | ⏳ |
| 射灯 | ⏳ | ⏳ |
| 筒灯 | ⏳ | ⏳ |
| 灯带 | ⏳ | ⏳ |
| 灯泡 | ⏳ | ⏳ |
| 灯管 | ⏳ | ⏳ |
| 灯头 | ⏳ | ⏳ |
| 泛光灯 | ⏳ | ⏳ |
| 照明辅件 | ⏳ | ⏳ |
| 开关电源 照明 | ⏳ | ⏳ |

---

## 🛠 技术栈

| 工具 | 用途 |
|------|------|
| **油猴脚本 (Tampermonkey)** | 搜索页自动翻页 + 滚动加载 |
| **Python 3 + BeautifulSoup4** | HTML 解析、清洗、分析 |
| **matplotlib** | 可视化图表 |
| **Selenium + ChromeDriver** | 详情页动态内容采集 |
| **[急云/1688](https://github.com/jiyun/1688)** | 1688 详情页深度解析（MIT 协议） |

### 1688 开源库（第三方）

详情页深度解析能力基于 [急云/1688](https://github.com/jiyun/1688) 开源项目，提供：

- `AlibabaParser` — 1688 详情页解析器，提取主图、详情图、色卡图、视频、属性、SKU 价格等
- `auto_collector.py` — Selenium 在线采集模块，支持浏览器扩展加载
- `main.py` — 资源下载（aria2c）+ 文件整理 + GUI 管理界面
- `database.py` — DuckDB 数据存储

---

## ⚠️ 注意事项

1. 油猴一次只跑一个关键词，跑完再搜下一个
2. 1688 使用 GBK 编码，油猴脚本已内置处理
3. Selenium 需要 Chrome 浏览器 + 已登录 1688 账号
4. 详情页采集最好在网络稳定的环境下运行
5. 遵守 1688 平台规则，合理控制采集频率
6. 1688 开源库的解析器依赖 SingleFile 扩展保存的 HTML 结构，Selenium 直存页面部分功能受限

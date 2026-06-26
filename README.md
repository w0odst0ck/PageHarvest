# 1688 智能照明商品数据采集 → 分析 Pipeline

## 项目目录

```
D:\projects\1688-scrapy\
├── pipeline/                          ← 全流程管道
│   ├── 01_fetch.user.js               # 🔵 数据采集 (油猴脚本)
│   ├── 02_parse.py                    # 🟢 HTML→CSV (17字段解析)
│   ├── 03_clean.py                    # 🟡 数据清洗 (去重+价格修正)
│   ├── 04_analyze.py                  # 🟠 数据分析+图表
│   └── run.py                         # 🏃 一键运行
│
├── data/                              # 📁 数据文件
│   ├── 户外灯具/                       # 原始HTML (34页)
│   ├── all_products.csv               # 原始解析数据
│   ├── cleaned_products.csv           # 清洗后数据
│   ├── analysis_report.txt            # 分析报告
│   └── analysis_chart.png             # 图表
│
├── download_all_pages.user.js         # 油猴脚本副本
├── requirements.txt                   # Python依赖
└── *.md                               # 文档
```

## 使用流程

```
01_fetch        02_parse        03_clean        04_analyze
 油猴下载  →  HTML→CSV    →  去重清洗    →  分析出图
    ↓              ↓              ↓              ↓
 34页HTML     1,550条原始    342条有效     报告+图表
```

**一键运行:**
```powershell
cd D:\projects\1688-scrapy
.venv\Scripts\activate
python pipeline\run.py
```

## 各步骤说明

### 01_fetch — 数据采集
- 油猴脚本，在1688搜索页自动翻34页
- 每页滚动加载全部商品，保存HTML到下载目录
- 手动把HTML移到 `data/关键词/` 文件夹

### 02_parse — HTML解析
- 解析 `search-offer-item` 商品卡片
- 提取 `plugin-offer-search-card` 插件数据
- 输出17个字段到 CSV

### 03_clean — 数据清洗
- 价格格式标准化
- 标题去冗余后缀
- 基于关键词的品牌识别
- 重复商品去重 (标题+供应商)

### 04_analyze — 数据分析
- 价格分布分析 (区间+统计)
- 供应商排名
- 品类分布
- 店铺经营时长
- 回头率分析
- 生成 `analysis_report.txt` 和 `analysis_chart.png`

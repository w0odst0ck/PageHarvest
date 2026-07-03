# 商品数据采集 & 分析工具

> 多平台电商数据采集框架，从搜索页到商品详情页的完整数据链路。  
> 当前支持 **1688** + **京东** + **震坤行**，可扩展至任意电商平台。

---

## 项目概述

两阶段数据管线，适配多平台：

**第一阶段（搜索层）** — 采集搜索列表页，解析、清洗、分析，输出品类全貌报告。

**第二阶段（详情层）** — 精选 Top 供应商的商品，采集详情页，提取品牌、SKU、主图、详情图、属性等深度数据。

> 1688 详情页解析基于 [急云/1688](https://github.com/jiyun/1688) 开源库。

---

## 📂 项目结构

```
1688Collector/
│
├── core/                            # 核心模块
│   ├── schema.py                    # 统一数据模型 (UnifiedProduct, UnifiedDetail, AnalysisReport)
│   ├── registry.py                  # 平台注册表 (@register 装饰器)
│   ├── pipeline.py                  # 管线编排器 (搜索页/详情页/跨平台)
│   ├── storage.py                   # 数据存储 (CSV/报告, 按平台目录)
│   └── merge.py                     # 跨平台数据合并对比
│
├── platforms/                       # ★ 平台适配器 (可扩展)
│   ├── base.py                      # 抽象基类 PlatformAdapter
│   ├── alibaba/                     # 1688 平台
│   │   ├── adapter.py               # 适配器 (采集+解析)
│   │   └── search_parser.py         # 搜索页解析器
│   ├── jingdong/                    # 京东平台
│   │   ├── adapter.py               # 适配器
│   │   └── search_parser.py         # 搜索页解析器
│   └── zkh/                         # 震坤行平台
│       ├── adapter.py               # 适配器
│       └── search_parser.py         # 搜索页解析器
│
├── userscripts/                     # ★ 油猴脚本 (纯HTML下载, 不解析)
│   ├── platform-1688.user.js        # 1688 自动翻页+保存
│   ├── platform-jd.user.js          # 京东 HTML 下载器 (SPA模式)
│   └── platform-zkh.user.js         # 震坤行 HTML 下载器
│
├── data/                            # ★ 数据目录 (按平台归档)
│   ├── 1688/                        # 1688 采集数据
│   ├── JD/                          # 京东采集数据
│   └── ZKH/                         # 震坤行采集数据
│
├── pipeline/                        # 旧管道脚本 (兼容)
│   ├── run.py                       # 统一命令行入口 (v2)
│   ├── run1.py                      # 原 1688 搜索页管线
│   └── run2.py                      # 原 1688 详情页管线
│
└── requirements.txt                 # Python 依赖
```

---

## 🚀 快速开始

### 1. 采集数据 (油猴脚本)

各平台的油猴脚本只做一件事：**模拟人类浏览 → 保存完整 HTML**。
解析工作由后端 Python 适配器完成。

| 平台 | 脚本 | 说明 |
|------|------|------|
| 1688 | `platform-1688.user.js` | 自动翻页+保存 HTML |
| 京东 | `platform-jd.user.js` | SPA 模式，单页内连续翻页保存 |
| 震坤行 | `platform-zkh.user.js` | 手动设起始页，自动翻页 20 页 |

### 2. 解析与分析

```python
from platforms.zkh import ZhenKunHangAdapter
from core.pipeline import SearchPipeline

# 方式一：直接解析 HTML
adapter = ZhenKunHangAdapter()
with open('data/ZKH/xxx.html') as f:
    products = adapter.parse_search(f.read(), "投光灯")

# 方式二：通过管线
pipeline = SearchPipeline("震坤行", "data")
products = pipeline.run("投光灯", html_dir="data/ZKH")
```

---

## 🏗️ 扩展新平台

1. 在 `platforms/` 下创建目录，如 `platforms/pinduoduo/`
2. 实现 `PlatformAdapter` 抽象基类
3. 用 `@register("平台名")` 装饰
4. 创建油猴脚本保存 HTML

```python
from platforms.base import PlatformAdapter
from core.registry import register

@register("新平台")
class NewPlatformAdapter(PlatformAdapter):
    @property
    def platform_name(self): return "新平台"
    # 实现所有抽象方法...
```

---

## 📊 数据存储路径

管线输出路径已改为**按平台目录**存储：

| 文件类型 | 路径格式 |
|---------|---------|
| 搜索页 CSV | `data/{平台}/all_{品类}.csv` |
| 详情页 CSV | `data/{平台}/top_{品类}_details.csv` |
| 分析报告 | `data/{平台}/analysis_{品类}.txt` |

---

## ⚙️ 油猴脚本使用说明

### 通用流程

1. 安装 [Tampermonkey](https://www.tampermonkey.net/)
2. 将 `userscripts/` 下的 `.user.js` 文件拖入浏览器安装
3. 打开目标平台的搜索页
4. 脚本会自动弹窗确认 → 模拟滚动 → 保存 HTML → 翻页

### 震坤行 (ZKH)

- 首次运行：等 20 秒让你手动跳到起始页 → 弹窗输入页码
- 自动翻页直到结束或触发风控
- 被风控后刷新页面，脚本从断点继续
- 可在脚本顶部修改 `TOTAL`（总页数）和 `START_PAGE`（起始页）

### 京东 (JD)

- SPA 单页连续模式，不依赖 URL 翻页
- 自适应滚动到底 → 保存 → 点击下一页 → 循环
- 京东反爬严格，建议单次不超过 10 页，页间延迟 5~10 秒

### 1688

- 传统页面模式，自动翻页
- 已有成熟采集逻辑，不动

---

## 🔑 平台对比

| 特性 | 1688 | 京东 | 震坤行 |
|------|------|------|--------|
| 渲染方式 | 传统 | SPA (Vue) | 传统 |
| 反爬强度 | 中等 | 严格 | 中等 (WAF) |
| 每页商品数 | ~30 | ~30 | 60 |
| 搜索页销量 | ✅ 有 | ✅ 有 | ❌ 无 |
| 品牌标签 | 有 | 有 | 行家精选 |
| 在线采集 | ✅ | ❌ 需浏览器 | ⚠️ WAF 拦截 |

---

## 📝 日志

- **2026-07-02**: 新增震坤行平台适配器；重写京东下载器为 SPA 模式；数据目录按平台归档；管线路径改为平台优先

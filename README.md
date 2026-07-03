# PageHarvest

> 多平台电商数据采集与解析框架。  
> 用 Tampermonkey 油猴脚本绕过反爬，后端 Python 统一解析，从搜索页到详情页一键闭环。

---

## 概述

两阶段数据管线，适配多平台：

**第一阶段（搜索层）** — 采集搜索列表页，解析、清洗、分析，输出品类全貌报告。

**第二阶段（详情层）** — 精选 Top 供应商的商品，采集详情页，提取品牌、SKU、主图、详情图、属性等深度数据。

> 1688 详情页解析基于 [急云/1688](https://github.com/jiyun/1688) 开源库。

---

## 项目结构

```
PageHarvest/
│
├── core/                          # 核心模块
│   ├── schema.py                  # 统一数据模型 (UnifiedProduct, UnifiedDetail, AnalysisReport)
│   ├── registry.py                # 平台注册表 (@register 装饰器)
│   ├── pipeline.py                # 管线编排器 (搜索页/详情页/跨平台)
│   ├── storage.py                 # 数据存储 (CSV/报告, 按平台目录)
│   └── merge.py                   # 跨平台数据合并对比
│
├── platforms/                     # 平台适配器 (可扩展)
│   ├── base.py                    # 抽象基类 PlatformAdapter
│   ├── alibaba/                   # 1688 平台
│   │   ├── adapter.py             # 适配器 (采集+解析)
│   │   └── search_parser.py       # 搜索页解析器
│   └── zkh/                       # 震坤行平台
│       ├── adapter.py             # 适配器
│       └── search_parser.py       # 搜索页解析器
│
├── selection/                     # 选品分析脚本 (配菜)
│   └── zkh-picker.py              # 震坤行选品分析器
│
├── userscripts/                   # 油猴脚本 (纯HTML下载, 不解析)
│   ├── platform-1688.user.js      # 1688 自动翻页+保存
│   ├── platform-jd.user.js        # 京东 HTML 下载器
│   └── platform-zkh.user.js       # 震坤行 HTML 下载器
│
├── data/                          # 数据目录 (按平台归档)
│   ├── 1688/
│   ├── JD/
│   └── ZKH/
│
├── pipeline/                      # 管线入口
│   ├── run.py                     # 统一命令行入口 (v2)
│   ├── run1.py                    # 原 1688 搜索页管线
│   └── run2.py                    # 原 1688 详情页管线
│
├── memory/                        # 项目日志
│
└── requirements.txt
```

---

## 快速开始

### 1. 采集数据 (油猴脚本)

各平台的油猴脚本只做一件事：**模拟人类浏览 → 保存完整 HTML**。解析工作由后端 Python 适配器完成。

| 平台 | 脚本 | 说明 |
|------|------|------|
| 1688 | `platform-1688.user.js` | 自动翻页+保存 HTML |
| 京东 | `platform-jd.user.js` | SPA 模式，单页内连续翻页保存 |
| 震坤行 | `platform-zkh.user.js` | 手动设起始页，自动翻页 20 页 |

### 2. 解析与分析

```python
# 搜索页解析
from platforms.zkh import ZhenKunHangAdapter

adapter = ZhenKunHangAdapter()
with open('data/ZKH/xxx.html') as f:
    products = adapter.parse_search(f.read(), "关键词")

# 详情页解析 (1688)
from platforms.alibaba import AlibabaAdapter
adapter = AlibabaAdapter()
detail = adapter.collect_detail("732462521472")
```

或通过统一命令行：

```bash
# 搜索页
python3 pipeline/run.py search --platform 1688 --keyword 投光灯 --html-dir data/1688/

# 详情页
python3 pipeline/run.py detail --platform 1688 --keyword 投光灯 --product-ids 732462521472

# 跨平台对比
python3 pipeline/run.py compare --keyword 投光灯 --platforms 1688,震坤行
```

### 3. 油猴脚本使用

1. 安装 [Tampermonkey](https://www.tampermonkey.net/)
2. 将 `userscripts/` 下的 `.user.js` 文件拖入浏览器安装
3. 打开目标平台的搜索页
4. 脚本会自动翻页、保存 HTML

---

## 扩展新平台

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

## 平台对比

| 特性 | 1688 | 京东 | 震坤行 |
|------|------|------|--------|
| 渲染方式 | 传统 | SPA (Vue) | 传统 |
| 反爬强度 | 中等 | 严格 | 中等 (WAF) |
| 每页商品数 | ~30 | ~30 | 60 |
| 搜索页销量 | ✅ 有 | ✅ 有 | ❌ 无 |
| 优选标签 | 实力商家/工业品牌 | — | 行家精选 |
| 在线采集 | ✅ | ❌ 需浏览器 | ⚠️ WAF 拦截 |

---

## 选品分析 (配菜)

基于已采集的销量降序数据，快速输出上架推荐清单：

```bash
python3 selection/zkh-picker.py --all
```

按品类/策略分文件夹输出，每份 30-50 条。

---

## 许可证

MIT

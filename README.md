# PageHarvest

> 多平台商品数据采集 & 选品分析框架。  
> 从搜索列表到详情数据，从采集解析到上架推荐，一站式完成。

---

## 概述

PageHarvest 是一个两阶段数据管线，适配多平台：

**第一阶段（搜索层）** — 采集搜索列表页，解析、清洗、分析，输出品类全貌报告。

**第二阶段（详情层）** — 精选 Top 供应商的商品，采集详情页，提取品牌、SKU、主图、详情图、属性等深度数据。

**第三阶段（选品层）** — 基于销量排序、平台标签、品牌格局，输出可执行的上架推荐。

当前支持平台：**1688** · **震坤行 (ZKH)**

> 1688 详情页解析基于 [急云/1688](https://github.com/jiyun/1688) 开源库。

## 核心能力

| 阶段 | 覆盖平台 | 产出 |
|------|---------|------|
| 搜索页采集 | 1688、震坤行 | 搜索列表 HTML |
| 搜索页解析 | 1688、震坤行 | 结构化商品数据（CSV） |
| 详情页采集 | 1688 | 商品详情 HTML |
| 详情页解析 | 1688（基于急云/1688） | 品牌、SKU、主图、详情图、属性 |
| 选品分析 | 震坤行 | 分级上架推荐清单 |

---

## 快速开始

### 安装

```bash
pip install -r requirements.txt
```

### 采集数据（浏览器 + 油猴脚本）

各平台的油猴脚本只做一件事：保存渲染后的完整 HTML。解析工作由后端 Python 完成。

| 平台 | 脚本 | 说明 |
|------|------|------|
| 1688 | `userscripts/platform-1688.user.js` | 自动翻页+保存 HTML |
| 震坤行 | `userscripts/platform-zkh.user.js` | 手动设起始页，自动翻页 20 页 |

**通用流程：**
1. 安装 [Tampermonkey](https://www.tampermonkey.net/)
2. 拖入对应的 `.user.js` 文件安装
3. 打开目标平台搜索页（按销量或综合排序）
4. 脚本自动保存每页 HTML 到本地

### 解析与分析

```python
# 搜索页解析
from platforms.zkh import ZhenKunHangAdapter

adapter = ZhenKunHangAdapter()
with open('data/ZKH/xxx.html') as f:
    products = adapter.parse_search(f.read(), "关键词")

# 或通过统一管线
python3 pipeline/run.py search --platform 震坤行 --keyword 关键词 --html-dir data/ZKH/

# 详情页解析（1688）
from platforms.alibaba import AlibabaAdapter
adapter = AlibabaAdapter()
detail = adapter.collect_detail("732462521472")  # offerId
```

### 详情页深度采集

精选 Top 供应商后，一键采集详情页，提取深度数据：

```bash
python3 pipeline/run.py detail --platform 1688 --keyword 品类 --product-ids id1,id2,id3
```

### 选品分析

```bash
# 一键分析所有品类，输出上架推荐清单
python3 selection/zkh-picker.py --all

# 单品类分析
python3 selection/zkh-picker.py data/ZKH/分析-某品类 --name 某品类
```

输出按品类/策略分文件夹，每份聚焦 30-50 条高价值商品。

---

## 项目结构

```
PageHarvest/
│
├── core/                          # 核心框架
│   ├── schema.py                  # 统一数据模型
│   ├── registry.py                # 平台注册表 (@register)
│   ├── pipeline.py                # 管线编排器
│   ├── storage.py                 # 数据存储
│   └── merge.py                   # 跨平台数据对比
│
├── platforms/                     # 平台适配器（可扩展）
│   ├── base.py                    # 抽象基类 PlatformAdapter
│   ├── alibaba/                   # 1688 适配器
│   │   ├── adapter.py
│   │   └── search_parser.py
│   └── zkh/                       # 震坤行适配器
│       ├── adapter.py
│       └── search_parser.py
│
├── selection/                     # 选品分析脚本
│   └── zkh-picker.py              # 震坤行选品分析（可作模板）
│
├── userscripts/                   # 油猴脚本
│   ├── platform-1688.user.js
│   └── platform-zkh.user.js
│
├── pipeline/                      # 管线入口
│   └── run.py                     # 统一命令行入口
│
├── data/                          # 采集数据归档
│   ├── 1688/
│   └── ZKH/
│
├── memory/                        # 项目日志
│   └── YYYY-MM-DD.md
│
└── requirements.txt
```

---

## 扩展新平台

1. 在 `platforms/` 下新建目录，如 `platforms/pinduoduo/`
2. 实现 `PlatformAdapter` 抽象基类
3. 用 `@register("平台名")` 装饰器注册
4. 创建对应油猴脚本保存 HTML

```python
from platforms.base import PlatformAdapter
from core.registry import register

@register("新平台")
class NewPlatformAdapter(PlatformAdapter):
    @property
    def platform_name(self): return "新平台"
    # 实现所有抽象方法……
```

5. （可选）在 `selection/` 下创建该平台的选品分析脚本

---

## 选品分析框架

分析维度对所有平台通用：

| 策略 | 条件 | 说明 |
|------|------|------|
| 🔥 必上 | 平台优选标签 + 高销量 | 最安全的首选 |
| 👍 推荐 | 平台优选标签 + 中上销量 | 补充候选 |
| 💡 暗马 | 无标签但销量极高 | 市场验证过的潜力品 |
| 📌 关注 | 无标签但销量靠前 | 可观察备选 |

各平台有各自的"优选标签"概念，映射关系：

| 平台 | 优选标签 |
|------|---------|
| 震坤行 | 行家精选 |
| 1688 | 实力商家 / 工业品牌 |
| 待扩展 | … |

---

## 平台对比

| 特性 | 1688 | 震坤行 (ZKH) |
|------|------|-------------|
| 渲染方式 | 传统 SSR | 传统 SSR |
| 反爬强度 | 中等 | 中等（WAF） |
| 每页商品数 | ~30 | 60 |
| 优选标签 | 实力商家/工业品牌 | 行家精选 |
| 销量数据 | 页面可见 | JSON 中为 null |
| 在线采集 | ✅ | ⚠️ WAF 拦截 |

---

## 许可证

MIT

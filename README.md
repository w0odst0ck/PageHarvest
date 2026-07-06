# PageHarvest — 多平台商品数据采集 & 选品分析框架

跨平台电商数据采集、选品推荐、详情提取、缺口比对的自动化框架。

```
search HTML → 选品推荐 → download list → detail HTML → 结构化数据 → 缺口分析
  (任何平台)   (策略分级)   (批次管理)     (离线保存)    (统一schema)  (交叉比对)
```

---

## 设计思想

**离线优先。** 不上线采集器。浏览器保存 HTML → 本地解析，零反爬风险、零维护成本。

**适配器模式。** 每个平台是一个 `PlatformAdapter` 插件，搜索页解析、详情页解析、URL 模板各自独立实现。

**管道化。** 数据从原始 HTML 到结构化结果，经过选品→下载→解析→比对等阶段，各阶段可插拔、可独立使用。

---

## 核心能力

### 搜索页 → 选品推荐
解析任何平台的搜索列表页 HTML，提取商品信息，按可配置策略分级，输出上架推荐清单。

### 下载清单管理
从选品结果生成 Excel 下载清单（可点击链接、策略颜色标注、自动筛选），支持断点续下。

### 详情页解析（跨平台）
浏览器渲染后的商品详情页 → 自动检测平台 → 路由到正确解析器 → 统一数据结构。

解析器注册表 `core/detail_parser.py` 可扩展：
```python
@register_parser("平台名")
def my_parser(html: str) -> dict:
    ...
```

### 商品缺口分析
跨平台比对：选品清单 vs 在售商品库 → 左反连接找出缺失品 → 模糊匹配二次校验 → 结构化 Excel 报告。

6 步流水线：读取 → 标准化 → 差集 → 模糊匹配 → 导出。

---

## 用你手上的数据跑一遍

项目根目录下 `data/` 中的内容仅作测试样例。你可以用你自己的 HTML 数据。

```bash
# 1. 选品分析：从搜索页 HTML 提取上架推荐
python3 selection/zkh-picker.py path/to/search/html/ --name 品类名

# 2. 生成下载清单
python -m selection.download_list --platform zkh --all --top 10

# 3. 保存详情页 HTML（浏览器打开链接 → Ctrl+S）
#    放入 details/ 目录

# 4. 批量解析详情页
python -m core.detail_parser path/to/details/ --batch --output result.csv

# 5. 缺口分析：选品 vs 在售
python -m gap.runner --listing path/to/selection/ --inventory path/to/inventory.xlsx --fuzzy
```

---

## 📂 项目结构

```
core/                    # 框架核心
├── schema.py            # 统一数据模型 (UnifiedProduct / UnifiedDetail)
├── registry.py          # @register 平台注册表
├── detail_parser.py     # ★ 跨平台详情页解析器注册表
├── pipeline.py          # 管线编排
├── storage.py           # 存储
└── merge.py             # 跨平台数据合并

platforms/              # ★ 各平台适配器（插件式）
├── base.py             # PlatformAdapter 抽象基类
├── alibaba/            # 1688 适配器
├── jingdong/           # 京东适配器
└── zkh/                # 震坤行适配器

selection/              # ★ 选品分析
├── zkh-picker.py       # 搜索页→选品推荐
├── auto_pick.py        # 选品赛后汇总
├── download_list.py    # ★ 跨平台下载清单生成
└── run_all.py          # 选品→缺口全流程桥接

gap/                    # ★ 商品缺口分析
├── config.py           # 配置
├── analyzer.py         # 6步流水线
└── runner.py           # CLI

pipeline/               # 管道脚本（兼容）
data/                   # 测试样例数据
memory/                 # 项目日志
```

---

## 扩展一个平台

```python
# 1. platforms/{新平台}/adapter.py
from platforms.base import PlatformAdapter
from core.registry import register

@register("平台名")
class MyAdapter(PlatformAdapter):
    def search_url(self, keyword, page): ...
    def product_url(self, product_id): ...
    def parse_search(self, html, keyword): ...
    def parse_detail(self, html): ...

# 2. platforms/{新平台}/search_parser.py — 搜索页解析逻辑

# 3. platforms/{新平台}/detail_parser.py — 详情页解析逻辑

# 4. 注册到 core.detail_parser
@register_parser("平台名")
def parse(html):
    ...

# 5. 配置到 download_list 的 PLATFORMS 字典
```

---

## 平台适配现状

| 平台 | 搜索页 | 选品 | 详情页解析 | 备注 |
|------|-------|------|-----------|------|
| 震坤行 (ZKH) | ✅ | ✅ | ✅ | 主力测试平台 |
| 1688 | ✅ | — | 待接入 | 遗留数据 |
| 京东 | ❌ | — | — | 反爬太强已放弃 |

---

## 依赖

```bash
pip install beautifulsoup4 openpyxl
# 可选: pip install rapidfuzz        # 模糊匹配（缺口分析用）
# 可选: pip install playwright        # 实验性浏览器自动化
```

---

## 许可

MIT

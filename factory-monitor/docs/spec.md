# 1688 优质工厂持续监控系统 — 设计文档

> 版本：v1.2 | 日期：2026-07-18 | 状态：定稿

---

## 一、定位

自动追踪 1688 小夜灯品类优质工厂，持续输出排名和变化预警。

**核心原则：** 零成本（Playwright + SQLite），不依赖任何付费 API。

---

## 二、筛选三维度

| 维度 | 量化指标 | 数据来源 |
|------|----------|----------|
| 产品线宽 | 全店商品总数 | 产品目录页 sectionCount |
| 销量好 | Top10 商品平均销量（代码内排序，非页面排序） | 产品目录页各商品销量字段 |
| 履约信誉 | 响应率 / 回头率 / 履约率 | 搜索页工厂卡片 |

> **说明：** 1688 工厂相关页面（搜索页、名片页、产品目录页）均**不提供** DSR / 好评率字段。信誉维度仅依赖搜索页工厂卡片的响应率、回头率、履约率这三个指标。产品目录页不按销量排序，需爬取全部可见商品后在代码层按销量排序取 Top10。

---

## 三、已定决策

| 决策项 | 结论 |
|--------|------|
| 品类 | 小夜灯 |
| 种子库 | 脚本拉取搜索页前 5 页 → 写入 factories（基础信息）→ 首次全量采集后再筛选 |
| 种子库规模 | 约 120 家（24 家/页 × 5 页） |
| 缺失指标 | 先收进来，对应维度降权 |
| 销量口径 | 店铺 Top10 商品平均销量（代码内排序） |
| 监控频率 | 每周 |
| 输出形式 | 按需查询（CLI） |
| 技术路线 | Playwright 本地运行，全部零成本 |
| Cookie 管理 | 手动登录一次 → 保存 → 复用；过期重新登录，历史数据不受影响 |
| 运行窗口 | 工作日 07:30-19:30 |

> **种子阶段说明：** 搜索页工厂卡片仅有店铺名、认证等级、响应率/回头率/履约率、位置、人员规模等基础信息，**缺少商品总数、销量数据**。这意味着半自动过滤阶段无法据此做出有效决策。因此改为：搜索页全量写入 → 首次全量采集获得完整指标后 → 根据实际数据排名筛选。

---

## 四、页面结构与数据源

系统涉及三个独立的 1688 页面类型。**已验证的 DOM 选择器标注为 ✅，可直接用于 Playwright 采集。**

### 4.1 工厂搜索页（factory_search）

**URL：** `s.1688.com/company/pc/factory_search.htm?keywords=...`

**工厂卡片容器：** `.space-factory-card`（24 个/页 × 50 页）

| 字段 | 示例 | 选择器 ✅ |
|------|------|-----------|
| 店铺名 | 中山市艾尔之光照明科技有限公司 | `.title` 文本 |
| 店铺 URL | sale.1688.com/factory/card.html?memberId=... | 卡片链接 href |
| 位置 | 中山 | `.city` 文本 |
| 认证等级 | 超级工厂 / 实力商家 / 诚信通 | `.super-text` 文本 |
| 开店年限 | 12 年 | `.year-text` 文本 |
| 主营品类 | LED支架灯 LED日光灯 工矿灯 | `.desc` 文本 |
| 厂房面积 | 9768㎡ | `.desc` 文本 |
| 人员规模 | 101-500人 | `.desc` 文本 |
| 响应率 | 97% | `.rate` 第 1 个 |
| 履约率 | 100% | `.rate` 第 2 个 |
| 回头率 | 52% | `.rate` 第 3 个 |
| 工厂等级 | 三钻工厂 | `.rank-txt` 文本 |
| 标签 | ["高新技术企业","CE认证"] | `.label-span` 文本数组 |
| 分页总数 | 50 页 | `.fui-paging-num` 文本 |

**版本差异：** 页面底部另有 `.cardWrap` 卡片区域（推荐工厂），结构不同，暂不采集。

### 4.2 工厂名片页（card）

**URL：** `sale.1688.com/factory/card.html?memberId=...`

从搜索页工厂卡片链接跳转（弹窗/新页面）。此页面仅用于获取店铺主页 URL 和补充基础信息。

| 字段 | 示例 | 选择器 ✅ |
|------|------|-----------|
| 成立时间 | 2026.04.13 | `.ability_info` 内 `ability_key` 匹配"成立时间"的兄弟元素 |
| 年交易额 | 101~500万 | 同上 |
| 厂房面积 | 10000m² | 同上 |
| 员工总数 | 20人 | 同上 |
| 商标/品牌 | 夏居乐 | 同上 |
| 专利数 | 2 | `.data-board-container` 内 `data-btrack-clkpos="专利数"` |
| 定制起订量 | 100个 | `.ability_info` |
| 加工方式 | 清加工 来样加工 来图加工 | `.ability_info` |
| **店铺主页 URL** | shop591c67h195891.1688.com | `<a href>` 含 `shop` 且含 `1688.com` |
| 商品详情页 | detail.1688.com/offer/xxx.html | `<a href>` 含 `detail.1688.com/offer/` |

**为什么需要这个页面：** 搜索页的工厂卡片链接指向的不是店铺主页，而是这个名片页。名片页中包含 `shopXXX.1688.com/` 的店铺主页链接。采集流程为：搜索页 → 名片页（提取 shop_url） → 店铺产品目录页（提取商品列表）。

### 4.3 产品目录页（product gallery）

**URL：** `sale.1688.com/factory/{shopCode}.html?memberId=...`

此页面是商品列表核心页面，**不按销量排序**（默认排序），但每个商品卡片直接显示销量数字，可在代码层排序。

| 字段 | 示例 | 选择器 ✅ |
|------|------|-----------|
| **商品总数** | 82 | `.sectionCount` 文本（位于"全部"标题旁） |
| **商品卡片** | — | `.galleyItemLink`（约 60 条/页） |
| 商品 ID | 1037898475960 | 从卡片链接 `href` 提取：`/offer/{id}.html` |
| 商品标题 | 智能折叠台灯学习专用... | `.galleyName` 文本 |
| 价格 | 16.63 | `.price` 文本 |
| 销量 | 42 | `.priceRight` 文本中的 `销\d+` 匹配 |
| 销量排名标签 | 阅读台灯...销量TOP10% | `.marketTag` 文本 |
| 品类标签 | ["拍拍灯","学习灯","夜灯"] | `.sampleTag` 文本数组 |

**分页：** 该工厂商品总数 82 件，一页约显示 60 件，尚未触发分页。数据分布待更多工厂验证。

**Top10 实现方式：** 爬取当前可见的全部商品卡片 → 提取每个商品的销量数字 → 在代码中 `sorted(products, key=lambda p: p.sales_30d, reverse=True)[:10]`。

---

## 五、数据流

```
[种子库构建 — 搜索页 + 名片页]
1688 搜索"小夜灯"前 5 页（~120 家）
    → 提取工厂卡片基础字段
    → 打开每家名片页 → 获取 shop_url
    → 写入 factories 表
                               ↓
[首次全量采集 — 产品目录页]
遍历 factories（全部 active）
    → 打开 `sale.1688.com/factory/{shopCode}.html`
    → 提取商品总数（`.sectionCount`）
    → 爬取全部 `.galleyItemLink` 卡片
    → 代码内按销量排序取 Top10
    → 写入 factory_snapshots + product_snapshots
                               ↓
[种子筛选 — 数据驱动]
查 SQLite → 基于完整指标排名 → 你决定保留/移除/暂缓哪些工厂
    → factories.status 更新为 active / paused / removed
                               ↓
[每周监控]
加载 Cookie → 遍历 active 工厂
    → 产品目录页：商品总数 + Top10 商品
    → 写入快照表（保留历史）
                               ↓
[变化检测]
对比本次快照与上次 → 匹配预警规则 → 写入 alerts
                               ↓
[查询]
CLI 提问 → 读 SQLite → 输出排名/趋势/预警
```

---

## 六、数据表设计

### factories — 工厂主表

| 字段 | 类型 | 说明 | 数据来源 |
|------|------|------|----------|
| id | INTEGER PK | | |
| shop_name | TEXT | 店铺名称 | 搜索页 |
| shop_url | TEXT | **UNIQUE** 店铺主页 URL，写入时用 card_url 做占位符避免冲突 | 搜索页 |
| card_url | TEXT | 名片页 URL | 搜索页 |
| catalog_url | TEXT | 产品目录页 URL（实际采集入口），搜索页写入时留空，名片页后回填 | 名片页 data-btrack |
| cert_level | TEXT | 超级工厂 / 实力商家 / 诚信通 | 搜索页 |
| has_yellow_tag | INTEGER | 小黄标 (0/1) | 搜索页 |
| location | TEXT | 产地城市，如"中山" | 搜索页 |
| years_on_1688 | INTEGER | 开店年限 | 搜索页 |
| gold_medal_rank | TEXT | 工厂钻级，如"三钻工厂" | 搜索页 |
| labels_json | TEXT | 标签数组 JSON | 搜索页 |
| area_sqm | INTEGER | 厂房面积 | 搜索页 |
| employees | TEXT | 人员规模，如"101-500人" | 搜索页 |
| product_tags | TEXT | 主营品类描述 | 搜索页 |
| status | TEXT | active / paused / removed | |
| first_seen | TEXT | 首次收录时间 | |

### factory_snapshots — 工厂快照（每次采集写一条）

| 字段 | 类型 | 说明 | 数据来源 |
|------|------|------|----------|
| id | INTEGER PK | | |
| factory_id | INTEGER FK | 关联 factories | |
| total_products | INTEGER | 全店商品总数 | 产品目录页 `.sectionCount` |
| response_rate | REAL | 响应率，搜索页无变化时复用上次值 | 搜索页 |
| fulfillment_rate | REAL | 履约率 | 搜索页 |
| repurchase_rate | REAL | 回头率 | 搜索页 |
| top10_avg_sales | REAL | 店铺 Top10 商品平均销量 | 产品目录页（代码排序） |
| snapshot_time | TEXT | 快照时间戳 | |

### product_snapshots — 商品快照（Top10 商品逐条记录）

| 字段 | 类型 | 说明 | 数据来源 |
|------|------|------|----------|
| id | INTEGER PK | | |
| factory_id | INTEGER FK | 关联 factories | |
| product_id | TEXT | 1688 商品 ID，如 1037898475960 | 产品目录页卡片链接 |
| title | TEXT | 商品标题 | `.galleyName` |
| price | REAL | 最低价（起订量对应的单价） | `.price` |
| sales_30d | INTEGER | 销量，如 42（表示"销42个"） | `.priceRight` 文本解析 |
| sales_tag | TEXT | 销量排名标签，如"阅读台灯...销量TOP10%" | `.marketTag` |
| category_tags | TEXT | 品类标签 JSON，如["拍拍灯","学习灯","夜灯"] | `.sampleTag` 文本数组 |
| snapshot_time | TEXT | 本次快照时间戳 | |

> **注意：** 产品目录页的商品不显示"上架时间"（created_time）和"品类"（category）字段，已从表精简为 JSON 标签存储。上架时间可通过商品详情页另行获取，当前阶段暂不采集。

### alerts — 预警事件

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | |
| factory_id | INTEGER FK | |
| alert_level | TEXT | red / yellow / blue |
| alert_type | TEXT | 见预警规则 |
| message | TEXT | 预警描述 |
| triggered_at | TEXT | 触发时间 |
| resolved | INTEGER | 是否已处理 (0/1) |

---

## 七、预警规则（4 类）

| 等级 | 规则 | 说明 | 依赖数据 |
|------|------|------|----------|
| 🔴 数据异常 | 商品数减少 ≥30%（相对上次快照） | 可能下架/关店/换品类 | total_products |
| 🟡 评分波动 | 响应率/回头率/履约率降幅 ≥5%（相对上次） | 服务或品控可能出问题 | response_rate / repurchase_rate / fulfillment_rate |
| 🔵 黑马发现 | 新入库工厂综合评分进入候选前 20% | 种子库扩展入口 | 综合得分（各维度加权） |
| 🔵 增长信号 | Top10 商品总销量增幅 ≥50%（相对上次） | 整体销量趋势上扬 | product_snapshots 各次快照对比 |

> **规则调整：** 原"近 7 天上新 ≥5 款"因产品目录页不显示上架时间而无法检测，改为 Top10 总销量增幅。阈值均为可配置参数，数据积累后调整。

---

## 八、技术栈

| 组件 | 选型 | 成本 |
|------|------|------|
| 浏览器自动化 | Playwright | 免费 |
| 数据存储 | SQLite | 免费 |
| 定时调度 | Windows 任务计划程序 | 免费 |
| 开发语言 | Python 3 | 免费 |

---

## 九、实施路线图

| 阶段 | 内容 | 预估 |
|------|------|------|
| 一 | 环境搭建 ✅ | — |
| 二 | 搜索页 + 名片页采集（提取 factories 表） | 1 天 |
| 三 | 产品目录页采集 + Top10 排序 + 入库 + 种子筛选 | 2-3 天 |
| 四 | 预警逻辑 + 查询 CLI | 1-2 天 |
| 五 | 定时任务 + 试运行 | 1 天 |
| **合计** | | **约 1 周** |

---

## 十、更新记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-18 | 合并 proposal + architecture 为 spec，统一 schema，移除 API 网关路线 |
| v1.1 | 2026-07-18 | 基于工厂搜索页 DOM 分析修正：三维度指标替换、种子流程优化 |
| v1.2 | 2026-07-18 | 基于工厂名片页 + 产品目录页 DOM 验证：补全所有选择器、去除好评率/DSR、Top10 改为代码排序、card_url 加入 factories 表、product_snapshots 字段精简、扩展规调整 |

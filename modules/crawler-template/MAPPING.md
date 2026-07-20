# factory-monitor → 模板映射

> 从具体项目到通用模板的溯源。当你写新项目时遇到疑问，查这里看 factory-monitor 当时怎么处理的。

---

## 映射表

| factory-monitor 文件 | 模板文件 | 说明 |
|----------------------|---------|------|
| `core/browser.py` | `core/browser.py` | 几乎直接复用，增加 `restart()` / `delete_cookies()` 方法 |
| `core/db.py` | `core/db.py` | 抽象为通用 ProjectDB，去掉工厂专有字段，保留 upsert/快照/预警三件套 |
| — | `core/utils.py` | 新增：safe_float / extract_number / random_delay / random_ua |
| `collector/search.py` | `collector/list_page.py` | 模式完全保留：搜索页提取 → 补全详情 URL → 两阶段 |
| `collector/offers.py` | `collector/detail_page.py` | 模式保留：读待处理条目 → 打开详情 → 提取 → 入库 |
| `engine/filter.py` | `engine/filter.py` | 抽象为通用关键词+阈值过滤 |
| `engine/alerter.py` | `engine/alerter.py` | 抽象为通用快照对比预警 |
| `cli/run.py` | `cli/run.py` | 保留四阶段编排 + flags |
| `cli/query.py` | `cli/query.py` | 保留 list / item 两个子命令 |

## 模板比原版多了什么

- `BrowserManager.restart()` — 运行时切换 headless 模式（用于 Cookie 过期后重新登录）
- `BrowserManager.delete_cookies()` — 删除 Cookie 文件重新登录
- `core/utils.py` — 常用工具函数集中管理
- `.gitignore` + `data/.gitkeep` — 开箱即用的数据目录隔离
- `scaffold.sh` — 一键创建新项目

## 模板从原版去掉的（不通用）

- **factory-monitor 特有的表结构**（factories / factory_snapshots / product_snapshots）→ 替换为泛化 items / snapshots / alerts
- **小夜灯灯具关键词** → KEYWORDS 放 filter.py 中留空作为修改点
- **1688 特定的编码/URL/选择器** → 改为 PLATFORM / _ENCODING / SEARCH_URL_TEMPLATE 常量
- **verify.py** → 这是工厂监控项目搭建时的验证工具，非通用模式，不留模板

## 预期修改量（新项目）

| 文件 | 修改量 | 难度 |
|------|--------|------|
| `core/db.py` SCHEMA_SQL | 3-5 行 | 低 |
| `core/db.py` CRUD 方法 | 5-10 行 | 低 |
| `collector/list_page.py` | 20-40 行（选择器+URL） | 中 |
| `collector/detail_page.py` | 15-30 行（选择器） | 中 |
| `engine/filter.py` | 3-5 行（关键词） | 低 |
| `engine/alerter.py` | 3-5 行（阈值+规则） | 低 |
| `cli/run.py` | ~0 行（通常不改） | 无 |
| `cli/query.py` | ~0 行（通常不改） | 无 |
| `requirements.txt` | 加其他依赖 | 低 |

总计新项目 **30-60 分钟** 完成适配。

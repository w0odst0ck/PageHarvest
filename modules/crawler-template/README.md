# 🕷️ Crawler Template — Playwright 爬虫项目模板

从 [PageHarvest/factory-monitor](https://github.com/your/factory-monitor) 实战中沉淀出的标准化爬虫脚手架。

## 一句话

```bash
cp -r crawler-template/_project/ my-new-crawler
# 改 config, 写 selector, 跑起来
```

## 核心模式

| 层级 | 模块 | 职责 |
|------|------|------|
| `core/` | `browser.py` | Playwright 管理器：生命周期、Cookie 持久化、反爬注入 |
| `core/` | `db.py` | SQLite 存储层：建表、CRUD、upsert |
| `collector/` | `list_page.py` | **列表页采集**：搜索/分页 → 提取条目列表 → 入库 |
| `collector/` | `detail_page.py` | **详情页采集**：读条目 → 打开详情 → 提取详情 → 入库 |
| `engine/` | `filter.py` | **过滤引擎**：按规则筛选/分类入库数据 |
| `engine/` | `alerter.py` | **预警引擎**：对比快照差异 → 触发告警 |
| `cli/` | `run.py` | **编排器**：命令行一键跑完多阶段流水线 |
| `cli/` | `query.py` | **查询器**：查看数据库内容 |

## 快速开始

```bash
# 1. 从模板创建新项目
cp -r _project/ my-new-crawler
cd my-new-crawler

# 2. 装依赖
pip install -r requirements.txt
playwright install chromium

# 3. 首次运行（弹浏览器，手动登录）
python -m cli.run

# 4. 以后静默跑
python -m cli.run --headless
```

## 设计原则

详见 [ARCHITECTURE.md](ARCHITECTURE.md) 和 [PATTERNS.md](PATTERNS.md)——它们解释为什么这样写，以及实战中踩过的坑。

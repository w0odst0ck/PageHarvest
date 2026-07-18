# 1688 优质工厂持续监控系统

自动化追踪 1688 小夜灯品类优质工厂，持续输出排名与变化预警。

**核心原则：** 零成本（Playwright + SQLite），不依赖任何付费 API。

---

## 快速开始

```bash
# 首次运行
cd 1688-factory-monitor
.venv/bin/pip install -r requirements.txt
playwright install chromium

# 全流程跑一次
.venv/bin/python3 -m cli.run
```

首次运行会弹出浏览器，请在浏览器中扫码登录 1688，登录后按回车继续。Cookie 自动保存，后续运行静默化。

## CLI

```bash
# 全流程：搜索 → 采集 → 预警
.venv/bin/python3 -m cli.run

# 仅搜索工厂（写入 factories 表）
.venv/bin/python3 -m collector.search --keyword 小夜灯 --pages 5

# 仅采集产品目录（读取 factories → 写快照表）
.venv/bin/python3 -m collector.offers

# 仅运行预警引擎
.venv/bin/python3 -m engine.alerter

# 查数据库
.venv/bin/python3 -m cli.query list
sqlite3 data/monitor.db "SELECT * FROM factory_snapshots LIMIT 10;"
```

## 项目结构

```
├── core/              # 核心模块
│   ├── db.py          — SQLite 存储层（建表 + CRUD）
│   └── browser.py     — Playwright 浏览器管理器（Cookie 持久化 + 共享上下文）
├── collector/         # 采集模块
│   ├── search.py      — 搜索页采集 → factories 表
│   └── offers.py      — 产品目录页采集 → 快照表
├── engine/
│   └── alerter.py     — 预警引擎（数据异常 + 增长信号）
├── cli/
│   ├── query.py       — 查询 CLI（list / factory）
│   └── run.py         — 一键编排入口
├── docs/
│   └── spec.md        — 完整技术设计文档
├── data/              — SQLite 数据库 + Cookie
├── requirements.txt
└── .gitignore
```

## 设计文档

详见 [`docs/spec.md`](docs/spec.md)。

# 架构文档

> 为什么这样设计？每一层的职责边界在哪？

---

## 整体架构

```
main.py → cli/run.py (编排器)
              │
              ├─ 阶段一: collector/list_page.py  (列表页采集)
              ├─ 阶段二: collector/detail_page.py (详情页采集)
              ├─ 阶段三: engine/filter.py         (数据过滤)
              └─ 阶段四: engine/alerter.py         (变化预警)
              │
              ▼
        core/browser.py    (浏览器管理 + 反爬)
        core/db.py          (存储层)
        data/               (SQLite DB + Cookie)
```

每阶段都是独立模块，可通过 CLI flags 单独跑：

```bash
python -m cli.run              # 全流程
python -m cli.run --list-only  # 仅阶段一
python -m cli.run --detail-only # 仅阶段二
python -m cli.run --filter-only # 仅阶段三
python -m cli.run --alert-only  # 仅阶段四
```

---

## 核心设计决策

### 1. Playwright 全套，不用 requests

**原因**：主流电商/B2B 平台几乎全面 SPA 化（React/Vue SSR），DOM 选择器 + Cookie 持久化的 Playwright 路线：
- 绕过前端反爬检测（比 requests + header 伪造可靠）
- 拿到真实渲染后的 HTML（不是 API 返回的结构化数据，但 DOM 反而更稳定）
- Cookie 持久化后 headless 运行，零人工干涉

### 2. Cookie JSON 持久化，不依赖 session

登录一次 → `save_cookies()` → 后续 `headless=True` 自动加载。偶有过期 → `--login` 重新登录。

### 3. 单页复用，不重复开浏览器

`BrowserManager` 单例模式，所有页面共用一个 `BrowserContext`：
- 共享 Cookie（不用每次都重新挂）
- 共享资源（开一次 Chrome 跑完全部）
- 每页面用 `page.goto()` 导航，不重复 `launch()`

### 4. 按阶段隔离，单步可重跑

每阶段只操作自己的表，错误不影响已完成数据。`--xxx-only` 支持失败后只重跑某一段。

### 5. 错误隔离在条目级

```
for item in items:       ← 外层循环是"页面/条目"
    try:
        process(item)     ← 内层 try/except 隔离单条失败
    except:
        log.warning(...)  ← 不影响其他条目
```

整页或整个阶段的异常会让页面级别失败，但是单个条目不会拖垮全部。

---

## 项目结构

```
my-project/
│
├── core/
│   ├── __init__.py        # (空)
│   ├── browser.py         # BrowserManager — 单例浏览器管理器
│   └── db.py              # ProjectDB — SQLite 存储层
│
├── collector/
│   ├── __init__.py         # (空)
│   ├── list_page.py        # 列表页/搜索页采集
│   └── detail_page.py      # 详情页/子页面采集
│
├── engine/
│   ├── __init__.py          # (空)
│   ├── filter.py            # 数据过滤/分类
│   └── alerter.py           # 预警/变化检测
│
├── cli/
│   ├── __init__.py          # (空)
│   ├── run.py               # 一键编排
│   └── query.py             # 查询 CLI
│
├── data/                    # 运行时数据（.gitignore）
│   ├── monitor.db           # SQLite 数据库
│   └── cookies.json         # Cookie 持久化
│
├── requirements.txt
├── .gitignore
└── README.md
```

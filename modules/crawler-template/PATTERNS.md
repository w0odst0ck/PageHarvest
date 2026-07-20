# 实战模式手册

> 从 factory-monitor 实战中踩过的坑和沉淀的解法。新项目开始前，先读这篇。

---

## 一、BrowserManager 模式

### 生命周期

```python
# 推荐用法：context manager
with BrowserManager(headless=True, cookie_path="data/cookies.json") as bm:
    page = bm.new_page("https://example.com")
    # ... 干活 ...

# 等价手动管理
bm = BrowserManager()
bm.start()
try:
    page = bm.new_page("https://example.com")
finally:
    bm.close()
```

### 🚨 关键踩坑

| 问题 | 解法 |
|------|------|
| **`chromium.launch()` 不自建上下文** | 必须显式 `new_context()`，否则 Cookie 不能持久化 |
| **`networkidle` 超时** | 1688 等平台页面有长连接，用 `"load"` 或 `"domcontentloaded"` |
| **headless 被检测** | `args=["--disable-blink-features=AutomationControlled"]` + `add_init_script()` 抹掉 webdriver |
| **Cookie 跨 session 失效** | `save_cookies()` 存 JSON → `_load_cookies()` 自动加载 |

### Cookie 策略

```
首次运行:  headed=True → 弹出浏览器 → 人工登录 → save_cookies()
以后运行:  headless=True → Cookie 自动加载 → 静默采集
Cookie 过期: 登录页跳转 → 自动 fallback 到 headed + 人工登录
```

---

## 二、DB 模式

### Schema 管理

```python
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id    INTEGER PRIMARY KEY,
    name  TEXT NOT NULL UNIQUE,
    ...
);
-- 索引在同语句块内创建
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
"""

class ProjectDB:
    def ensure_schema(self):
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()
```

### 🚨 关键踩坑

| 问题 | 解法 |
|------|------|
| **UNIQUE 约束 + 空字符串冲突** | 多个空 `shop_url` 会互相覆盖。方案：用唯一真实字段做 UNIQUE，或 COALESCE 回退 |
| **WAL 并发** | `PRAGMA journal_mode=WAL` — 允许读写并发，防止多步骤间锁等待 |
| **外键约束默认关闭** | 必须显式 `PRAGMA foreign_keys=ON` |
| **row_factory 默认 tuple** | 设 `conn.row_factory = sqlite3.Row` 才能按列名取值 |

### Upsert 模式

```python
INSERT INTO table (...) VALUES (...)
ON CONFLICT(unique_col) DO UPDATE SET
    field1 = COALESCE(NULLIF(?,''), field1),  -- 非空才更新
    field2 = COALESCE(?, field2)               -- 原样更新
```

---

## 三、列表页采集模式

### 流程

```
1. 构造 URL（注意编码）
2. goto() → 等待渲染
3. query_selector_all() 取卡片列表
4. 遍历卡片 → 逐行提取字段
5. 写入数据库
```

### 🚨 关键踩坑

| 问题 | 解法 |
|------|------|
| **中文 URL 编码** | 1688 工厂搜索用 GBK：`quote(keyword, encoding="gbk")`。其他平台通常 UTF-8 |
| **元素未渲染** | 加 `time.sleep(2-3)` 等待 JS 渲染后再查。不用 `wait_for_selector` 是因为某些元素存在但未渲染完整 |
| **CSS 类名依赖** | 优先用 `data-*` 属性选择器（`[data-btrack="..."]`），比 CSS class 稳定 |
| **翻页** | 循环构造 URL page 参数，每页单独 `goto()` + sleep，不点"下一页"按钮（按钮可能在 DOM 中定位困难） |
| **空页判断** | 检查卡片列表长度 == 0 → 跳出翻页循环 |

### 数据提取模板

```python
for card in cards:
    el = card.query_selector(".selector")
    value = el.inner_text().strip() if el else ""

    # 从 data-* 属性取结构化数据
    attr_val = card.get_attribute("data-xxx") or ""
    m = re.search(r"pattern", attr_val)
    extracted = m.group(1) if m else ""
```

---

## 四、详情页/子页面采集模式

### 流程

```
1. 从 DB 读待处理条目列表
2. 打开一个新 page（或复用现有 page.goto()）
3. 等待渲染 → 提取字段
4. 写库 → 下一个
```

### 🚨 关键踩坑

| 问题 | 解法 |
|------|------|
| **页面复用** | 复用同一个 page 对象，用 `page.goto(new_url)` 导航，不要重复 `new_page()` |
| **跳转失败** | 每个条目 try/except 隔离，失败只跳过一个不影响后续 |
| **懒加载** | 滚动到底部：`page.evaluate("window.scrollTo(0, document.body.scrollHeight)")` → sleep(1.5) → 检查元素数变化 |
| **跳转超时** | `page.goto(url, timeout=15000)` 显式设超时，长超时不卡死 |

---

## 五、编排器模式

```python
# cli/run.py 核心结构
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-only", action="store_true")
    parser.add_argument("--detail-only", action="store_true")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    db = ProjectDB()
    db.ensure_schema()

    if not args.detail_only:
        run_list_page(db, args)     # 阶段一
    if not args.list_only:
        run_detail_page(db, args)   # 阶段二
    # ... 后续阶段

    db.close()
```

**关键原则**：
- 每阶段独立函数，互不依赖执行结果
- 支持跳过任意阶段（`--xxx-only`）
- 全局 `logging` 统一格式
- 标准 argparse 接口，不要硬编码参数

---

## 六、反爬总览

| 防护类型 | 表现 | 解法 |
|---------|------|------|
| **滑块验证码** | 页面出现滑块框 | 免：Cookie 持久化。兜底：`headless=False` 手动滑 |
| **Cloudflare** | 5 秒盾 / 人机验证 | 第一次 headed 通过后存 Cookie（CF Token 在 Cookie 里） |
| **WAF** | 遮罩层 / 拦截 / 弹窗 | MutationObserver 预移除、DOM 操作绕过 |
| **IP 封禁** | 所有请求返回 403 / 空白 | 等 24h 冷却 / 换 IP（代理池） |
| **频率限制** | 正常返回后弹验证码 | `time.sleep(3-5)` 保守间隔，不并发 |
| **headless 检测** | 检测到 Playwright | `add_init_script()` 抹掉 webdriver + chrome 特征 |

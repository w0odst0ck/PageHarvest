# 新增平台操作手册

## 流程（约 10 分钟）

### Step 1：拷贝模板

```
cp -r platforms/_template platforms/新平台名
```

### Step 2：修改配置

编辑 `platforms/新平台名/config.py`：

- `PLATFORM_NAME` → 平台中文名
- `SEARCH_URL` → 搜索 URL 模板，用 `{keyword}` 占位
- `DELAY_RANGE` → 请求间隔
- `COOKIE_FILE` → Cookie 路径
- `HEADERS` → 自定义请求头

### Step 3：实现爬虫（只改这个文件）

编辑 `platforms/新平台名/crawler.py`

- 根据平台反爬级别选方案：
  - 无反爬：requests.get()
  - 有反爬：带 Cookie + UA + 延时
  - 强反爬：selenium

### Step 4：实现解析

编辑 `platforms/新平台名/parser.py`

- 分析搜索页 HTML 结构
- 提取：标题、价格、链接、店铺名

### Step 5：匹配逻辑

编辑 `platforms/新平台名/matcher.py`

- 可复用 `_template/matcher.py` 的通用逻辑
- 也可按平台定制（如 1688 标题杂，可能需要定制）

### Step 6：注册

在 `platforms/__init__.py` 添加一行：

```python
{
    'name': '新平台名',
    'module_path': 'platforms.新平台名',
    'enabled': True,       # 先开 True 测试
    'tier': 3,
    'status': 'active',
},
```

### Step 7：测试

```bash
python main.py
```

## 注意事项

- 不要修改其他平台的代码
- 不要修改 main.py
- 不要修改 core/ 的公共模块

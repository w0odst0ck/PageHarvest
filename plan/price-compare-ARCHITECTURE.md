# 架构说明

## 整体架构

```
main.py  →  platforms/__init__.py (注册表)
              │
              ├─ alibaba_1688/     → crawler + parser + matcher
              ├─ zkh/              → crawler + parser + matcher
              ├─ jd_industrial/    → (已规划)
              ├─ gongpinhui/       → (已规划)
              └─ ehsy/             → (已规划)
              │
              ▼
        core/loader.py     (输入读取)
        core/exporter.py   (结果合并输出)
        core/logger.py     (日志)
        core/utils.py      (工具函数)
```

## 模块职责

| 层级 | 职责 |
|------|------|
| main.py | 调度器，遍历注册表调用各平台 run() |
| platforms/__init__.py | 平台注册表，控制启用/禁用 |
| platforms/xxx/ | 单个平台实现：搜索、解析、匹配 |
| core/ | 公共基础设施 |
| config.py | 全局配置 |
| cookies/ | Cookie 文件（手工放入） |

## 平台接口规范

每个平台模块必须暴露一个 run() 函数：

```python
def run(products: list[dict]) -> dict:
    """输入标准商品列表，返回匹配结果"""
```

## 数据流

```
输入文件  →  loader   →  标准商品列表  →  各平台 run()
                                               │
                                               ▼
                                         匹配结果
                                               │
                                               ▼
                                exporter → price_compare.xlsx
```

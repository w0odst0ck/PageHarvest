"""
价格监控 — 选品结果入库引擎

从 selection 输出的 CSV 目录读取选品结果，写入 SQLite。

用法（代码内）：
    from monitor.ingester import ingest_selection
    ingest_selection("output/ZKH/灯具", platform="zkh", db_path="data/monitor.db")

输出：
    - 商品去重写入 products 表
    - 每次调用产生一条 ingestion_runs 记录
    - 每条商品写入一条 snapshots 快照
"""

import csv
import logging
import re
from pathlib import Path
from typing import Optional

from monitor.db import MonitorDB

logger = logging.getLogger(__name__)

# ── CSV 列映射（字段名 → 统一处理函数） ──
# 按 selection_schema.py 定义映射

PLATFORM_FIELD_MAP = {
    "zkh": {
        "header": ["策略", "排名", "品牌", "标题", "价格", "型号", "行家精选", "链接"],
        "extra_keys": ["型号", "行家精选"],
    },
    "jd": {
        "header": ["策略", "排名", "品牌", "标题", "价格", "销量", "好评率", "自营", "链接"],
        "extra_keys": ["销量", "好评率", "自营"],
    },
    "1688": {
        "header": ["策略", "排名", "品牌", "标题", "价格", "年销", "复购率", "店铺", "链接"],
        "extra_keys": ["年销", "复购率", "店铺"],
    },
}


def _find_collection_csv(category_dir: Path) -> Optional[Path]:
    """在品类目录下找 00-选品推荐合集.csv"""
    for f in category_dir.iterdir():
        if f.name == "00-选品推荐合集.csv":
            return f
    return None


def _parse_sales(raw: str) -> Optional[int]:
    """年销/销量 字符串转整数。'167636'→167636  '已售60万+'→600000"""
    if not raw or raw == "-":
        return None
    raw = raw.strip()
    # 万/万+ 单位
    m = re.search(r'([\d.]+)\s*万', raw)
    if m:
        return int(float(m.group(1)) * 10000)
    # 纯数字
    m = re.search(r'\d+', raw.replace(",", ""))
    return int(m.group()) if m else None


def _parse_price(raw: str) -> Optional[float]:
    """价格转浮点数。'5.5'→5.5  '~69.9'→69.9  '¥21.90~¥90.00'→21.9"""
    if not raw or raw == "-":
        return None
    raw = raw.strip().lstrip("¥").lstrip("￥")
    # 价格区间：取最小值
    parts = re.split(r'[~～]', raw)
    try:
        return float(parts[0].strip())
    except ValueError:
        return None


def _parse_rank(raw: str) -> Optional[int]:
    """排名转整数"""
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def ingest_selection(
    platform: str,
    selection_dir: str | Path,
    category: str = "",
    db_path: str | Path = "data/monitor.db",
) -> dict:
    """
    从选品输出目录导入数据到 SQLite。

    Args:
        platform: "zkh" | "jd" | "1688"
        selection_dir: selection 输出目录（如 "output/ZKH/灯具"）
        category: 品类名（自动从目录名推测时留空）
        db_path: SQLite 文件路径

    Returns:
        {"run_id": int, "products": int, "snapshots": int, "categories": [str]}
    """
    selection_dir = Path(selection_dir)
    if not selection_dir.is_dir():
        raise FileNotFoundError(f"选品目录不存在: {selection_dir}")

    platform = platform.lower()
    if platform not in PLATFORM_FIELD_MAP:
        raise ValueError(f"不支持的平台: {platform}，支持: {list(PLATFORM_FIELD_MAP)}")

    field_def = PLATFORM_FIELD_MAP[platform]
    header = field_def["header"]
    # 找到策略列索引和价格列索引
    strategy_idx = header.index("策略")
    rank_idx = header.index("排名")
    brand_idx = header.index("品牌")
    title_idx = header.index("标题")
    price_idx = header.index("价格")
    link_idx = header.index("链接")

    db = MonitorDB(db_path)
    db.ensure_schema()

    # 发现品类目录
    # categories 的取值：[(品类名, CSV所在目录), ...]
    categories: list[tuple[str, Path]] = []

    if category:
        categories = [(category, selection_dir)]
    elif selection_dir.name == "搜索页":
        # 直接是品类下的搜索页目录
        categories = [(selection_dir.parent.name, selection_dir)]
    else:
        # 检查是否有 "搜索页" 子目录
        search_page = selection_dir / "搜索页"
        if search_page.is_dir():
            categories = [(selection_dir.name, search_page)]
        else:
            # 扫描子目录（每个子目录即一个品类）
            for child in sorted(selection_dir.iterdir()):
                if child.is_dir():
                    # 子目录下可能有 "搜索页" 或直接含 CSV
                    sp = child / "搜索页"
                    if sp.is_dir():
                        categories.append((child.name, sp))
                    elif _find_collection_csv(child):
                        categories.append((child.name, child))
            if not categories:
                # 单品类目录，CSV 就在本目录
                categories = [(selection_dir.name, selection_dir)]
                selection_dir = selection_dir.parent

    total_products = 0
    total_snapshots = 0
    run_ids = []

    for cat, cat_dir in categories:
        csv_path = _find_collection_csv(cat_dir)
        if not csv_path:
            logger.warning("品类 %s 下无 00-选品推荐合集.csv，跳过", cat)
            continue

        # 创建入库记录
        run_id = db.create_run(platform, category=cat, source_dir=str(cat_dir))
        run_ids.append(run_id)

        with open(csv_path, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows = list(reader)

        if not rows:
            logger.warning("CSV 为空: %s", csv_path)
            continue

        # 校验表头（含 BOM）
        actual_header = rows[0]
        if actual_header[0].lstrip("\ufeff") != "策略":
            logger.warning("CSV 表头不匹配: %s，跳过", csv_path)
            continue

        data_rows = rows[1:]
        product_count = 0

        for row in data_rows:
            if len(row) < len(header):
                continue

            url = row[link_idx].strip()
            if not url:
                continue

            product_id = ""
            title = row[title_idx].strip()
            brand = row[brand_idx].strip()
            strategy = row[strategy_idx].strip()
            price = _parse_price(row[price_idx])
            rank = _parse_rank(row[rank_idx])
            sales = None

            # 收集扩展字段
            extra = {}
            for k in field_def["extra_keys"]:
                ek_idx = header.index(k)
                extra[k] = row[ek_idx].strip() if ek_idx < len(row) else ""

            # 销量从 extra 提取
            sales_raw = extra.get("年销") or extra.get("销量") or ""
            sales = _parse_sales(sales_raw)

            # 写入商品
            pid = db.upsert_product(
                platform=platform, url=url, title=title,
                brand=brand, product_id=product_id,
            )

            # 写入快照
            db.add_snapshot(
                run_id=run_id, product_db_id=pid,
                price=price, sales=sales, rank=rank,
                strategy=strategy, extra=extra,
            )
            product_count += 1

        db.update_run_count(run_id, product_count)
        total_products += product_count
        total_snapshots += product_count
        logger.info("品类 %s: %d 商品入库 (run_id=%d)", cat, product_count, run_id)

    cat_names = [c[0] if isinstance(c, tuple) else c for c in categories]
    # 更新 categories 字段
    if run_ids:
        db.conn.executemany(
            "UPDATE ingestion_runs SET category = ? WHERE id = ?",
            [(cn, rid) for cn, rid in zip(cat_names, run_ids)]
        )
        db.conn.commit()

    db.close()
    return {
        "run_id": run_ids[0] if len(run_ids) == 1 else run_ids,
        "products": total_products,
        "snapshots": total_snapshots,
        "categories": cat_names,
    }

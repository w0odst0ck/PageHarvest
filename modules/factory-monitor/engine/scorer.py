"""
工厂评分引擎 — 搜索页数据维度评分 → 筛选 Top N

在搜索完成之后、产品目录采集之前执行。
只用搜索页已有的数据（不需要打开详情页），打一轮分，只采高分工厂。

评分维度：
  - 认证等级: 超级工厂=30, 实力商家=20, 普通=5
  - 开店年限: min(years/10, 1) * 15
  - 响应率 ×15
  - 履约率 ×15
  - 回头率 ×10
  - 行家精选标签: +10
  - 金牌货盘: +5
  合计 = 100

用法：
    python -m engine.scorer --category-keyword 小夜灯 --top 10
    python -m engine.scorer --category-keyword 吸顶灯 --top 20
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DB_PATH
from core.db import MonitorDB

logger = logging.getLogger(__name__)

# 认证等级权重
CERT_WEIGHTS = {
    "超级工厂": 30,
    "实力商家": 20,
    "普通": 5,
}
DEFAULT_CERT_WEIGHT = 5
YELLOW_TAG_BONUS = 10
GOLD_MEDAL_BONUS = 5
YEAR_MAX = 10


def _safe_rate(val):
    """安全取信誉率，None/0 返回 0"""
    return val if val is not None and val > 0 else 0.0


def _score_factory(f) -> int:
    """计算单家工厂的评分（0-100）

    维度：cert 30 + years 15 + 响应率 15 + 履约率 15 + 回头率 10
         + 标签 10 + 货盘 5 = 100
    """
    score = 0

    # 1. 认证等级（0-30）
    cert = (f["cert_level"] or "").strip()
    score += CERT_WEIGHTS.get(cert, DEFAULT_CERT_WEIGHT)

    # 2. 开店年限（0-15）
    years = f["years_on_1688"] or 0
    score += int(min(years / YEAR_MAX, 1.0) * 15)

    # 3. 响应率（0-15）
    score += int(_safe_rate(f["response_rate"]) * 15)

    # 4. 履约率（0-15）
    score += int(_safe_rate(f["fulfillment_rate"]) * 15)

    # 5. 回头率（0-10）
    score += int(_safe_rate(f["repurchase_rate"]) * 10)

    # 6. 行家精选标签（0-10）
    if f["has_yellow_tag"]:
        score += YELLOW_TAG_BONUS

    # 7. 金牌货盘（0-5）
    if f["gold_medal_rank"]:
        score += GOLD_MEDAL_BONUS

    return min(score, 100)


def score_factories(db: MonitorDB, category_id: int, top_n: int = 10) -> list[dict]:
    """
    对品类下所有 active 工厂评分，写入 scored_rank，返回排名列表。

    Returns:
        [{"rank", "factory_id", "shop_name", "score"}, ...]
    """
    factories = db.get_active_factories(category_id=category_id)
    scored = []

    for f in factories:
        s = _score_factory(f)
        scored.append({
            "factory_id": f["id"],
            "shop_name": f["shop_name"],
            "score": s,
            "cert_level": f["cert_level"],
            "years": f["years_on_1688"],
        })

    # 按评分降序排名
    scored.sort(key=lambda x: x["score"], reverse=True)

    # 写入 scored_rank
    for rank, item in enumerate(scored, start=1):
        db.conn.execute(
            "UPDATE factories SET scored_rank = ? WHERE id = ?",
            (rank if rank <= top_n else None, item["factory_id"])
        )
    db.conn.commit()

    logger.info("评分完成: %d 家工厂, Top %d:", len(scored), top_n)
    for item in scored[:top_n]:
        logger.info("  #%d  %s  (%d分  %s  %d年)",
                    scored.index(item) + 1,
                    item["shop_name"][:25],
                    item["score"], item["cert_level"], item["years"])

    return scored


def main():
    parser = argparse.ArgumentParser(description="工厂评分引擎")
    parser.add_argument("--category", type=int, default=None)
    parser.add_argument("--category-keyword", default=None)
    parser.add_argument("--top", type=int, default=10,
                        help="保留 Top N 家")
    args = parser.parse_args()

    db = MonitorDB(DB_PATH)
    db.ensure_schema()

    # 解析品类
    cid = None
    if args.category_keyword:
        c = db.get_category_by_keyword(args.category_keyword)
        if not c:
            print(f"  未找到品类: {args.category_keyword}")
            db.close()
            return
        cid = c["id"]
        print(f"  品类: {c['keyword']} id={cid}")
    elif args.category:
        cid = args.category

    if cid is None:
        print("  请指定品类: --category 或 --category-keyword")
        db.close()
        return

    scored = score_factories(db, cid, top_n=args.top)
    print(f"\n  评分完成: {len(scored)} 家工厂, 保留 Top {args.top}")
    print(f"\n  Top {args.top}:")
    for i, item in enumerate(scored[:args.top], 1):
        print(f"  #{i:<3} {item['shop_name'][:30]:<30} {item['score']:>2}分  "
              f"{item['cert_level']}")

    db.close()


if __name__ == "__main__":
    main()

"""
价格监控 — 预警引擎（移动平均版）

核心逻辑：入库时自动比对当前价格与历史移动平均。
仅在价格显著偏离均线时才输出预警，自然波动不触发。

触发方式：被动附着于 ingest 流程末尾。
输出形式：CSV/TXT 文件写入选品输出目录，无预警则无文件。
"""

import csv
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from monitor.db import MonitorDB

logger = logging.getLogger(__name__)

# ── 默认参数 ──
DEFAULT_THRESHOLD_BELOW_MA = 10.0   # 当前价低于移动平均 X% 时触发
DEFAULT_MA_WINDOW = 5               # 移动平均窗口（最近 N 次快照）
DEFAULT_MIN_SAMPLES = 3             # 最少快照数，低于此不触发

ALERT_TYPE_BELOW_MA = "below_ma"    # 低于均线
ALERT_TYPE_NEW = "new_product"      # 新商品
ALERT_TYPE_ABOVE_MA = "above_ma"    # 高于均线（选配，默认关闭，仅供预留）

ALERT_LABELS = {
    "below_ma":    "📉 低于均线",
    "new_product": "🆕 新商品",
    "above_ma":    "📈 高于均线",
}


# ═══════════════════════════════════════════════════════════════
#  修复器接口（预留，后续版本实现）
# ═══════════════════════════════════════════════════════════════

class AlertAdjuster(ABC):
    """
    价格修复器基类。对极端波动的商品调整告警参数。

    应用场景：
    - 半导体等商品随行情暴涨暴跌 → 移动平均被快速拉偏
    - 需要自动跳过或放宽阈值，避免频繁误报

    当前状态：接口已定义，实现待后续版本推进。
    """

    @abstractmethod
    def should_skip(self, product_db_id: int,
                    prices: list[Optional[float]]) -> bool:
        """是否跳过该商品的告警"""
        ...

    @abstractmethod
    def adjust_threshold(self, product_db_id: int,
                         prices: list[Optional[float]],
                         base_threshold: float) -> float:
        """调整告警阈值。返回值：调整后的阈值（百分比）。"""
        ...


# ═══════════════════════════════════════════════════════════════
#  预警记录
# ═══════════════════════════════════════════════════════════════

class Alert:
    __slots__ = (
        "alert_type", "platform", "category",
        "product_db_id", "title", "brand", "url",
        "current_price", "ma_price", "deviation_pct",
        "latest_sales", "n_snapshots", "detected_at",
    )

    def __init__(self, alert_type: str, platform: str, category: str,
                 product_db_id: int, title: str, brand: str, url: str):
        self.alert_type = alert_type
        self.platform = platform
        self.category = category
        self.product_db_id = product_db_id
        self.title = title
        self.brand = brand
        self.url = url
        self.current_price: Optional[float] = None
        self.ma_price: Optional[float] = None          # 移动平均值
        self.deviation_pct: Optional[float] = None     # 偏离度
        self.latest_sales: Optional[int] = None
        self.n_snapshots: int = 0
        self.detected_at = datetime.now(timezone.utc).isoformat()

    @property
    def label(self) -> str:
        return ALERT_LABELS.get(self.alert_type, self.alert_type)

    def to_row(self) -> list:
        return [
            self.label,
            self.platform,
            self.category,
            self.brand or "-",
            self.title,
            self._fmt_price(self.current_price),
            self._fmt_price(self.ma_price),
            self._fmt_pct(self.deviation_pct),
            self._fmt_sales(self.latest_sales),
            f"{self.n_snapshots}次",
            self.detected_at[:10],
            self.url,
        ]

    @staticmethod
    def _fmt_price(v: Optional[float]) -> str:
        return f"¥{v:.2f}" if v is not None else "-"

    @staticmethod
    def _fmt_pct(v: Optional[float]) -> str:
        if v is None:
            return "-"
        sign = "+" if v > 0 else ""
        return f"{sign}{v:.1f}%"

    @staticmethod
    def _fmt_sales(v: Optional[int]) -> str:
        if v is None:
            return "-"
        if v >= 10000:
            return f"{v / 10000:.1f}万"
        return str(v)

    @staticmethod
    def csv_header() -> list[str]:
        return ["信号", "平台", "品类", "品牌", "标题",
                "当前价格", "移动均价", "偏离度",
                "销量", "快照数", "日期", "链接"]


# ═══════════════════════════════════════════════════════════════
#  核心：移动平均比对
# ═══════════════════════════════════════════════════════════════

def _moving_average(prices: list[Optional[float]],
                    window: int) -> Optional[float]:
    """计算最近 window 次快照的移动平均"""
    valid = [p for p in prices[-window:] if p is not None]
    if not valid:
        return None
    return sum(valid) / len(valid)


def run_alert(platform: str, category: str, current_run_id: int,
              db: MonitorDB,
              threshold_below_ma: float = DEFAULT_THRESHOLD_BELOW_MA,
              ma_window: int = DEFAULT_MA_WINDOW,
              min_samples: int = DEFAULT_MIN_SAMPLES,
              adjuster: Optional[AlertAdjuster] = None,
              ) -> list[Alert]:
    """
    比对最新入库商品的当前价格与移动平均，生成预警。

    首次/头几次入库（快照数 < min_samples）保持沉默。
    只在价格显著低于移动平均值时才触发。

    Args:
        platform: 平台名
        category: 品类名
        current_run_id: 本次入库 run_id
        db: MonitorDB 实例
        threshold_below_ma: 当前价低于移动平均 X% 时触发，默认 10%
        ma_window: 移动平均窗口，默认 5 次
        min_samples: 最少快照数，低于此不触发冷启动
        adjuster: 价格修复器实例（预留，当前不实现）

    Returns:
        Alert 列表（空列表 = 无预警）
    """
    alerts: list[Alert] = []

    # 获取本次入库所有快照
    rows = db.conn.execute("""
        SELECT p.url, p.id as product_db_id, p.title, p.brand,
               s.price, s.sales
        FROM snapshots s
        JOIN products p ON p.id = s.product_id
        WHERE s.run_id = ?
    """, (current_run_id,)).fetchall()

    for row in rows:
        url = row["url"]
        product_db_id = row["product_db_id"]
        current_price = row["price"]
        sales = row["sales"]

        if current_price is None:
            continue

        # 获取该商品所有历史快照价格（按时间升序）
        price_rows = db.conn.execute("""
            SELECT s.price
            FROM snapshots s
            WHERE s.product_id = ?
            ORDER BY s.id
        """, (product_db_id,)).fetchall()

        prices = [r["price"] for r in price_rows if r["price"] is not None]
        n = len(prices)

        if n < min_samples:
            # 冷启动：快照不足，不触发
            continue

        # 计算移动平均
        ma = _moving_average(prices, ma_window)
        if ma is None or ma == 0:
            continue

        deviation = (current_price - ma) / ma * 100

        # ---- 修复器预留逻辑 ----
        if adjuster:
            if adjuster.should_skip(product_db_id, prices):
                continue
            threshold_below_ma = adjuster.adjust_threshold(
                product_db_id, prices, threshold_below_ma
            )

        # ---- 判断 ---- 
        if deviation <= -threshold_below_ma:
            # 价格显著低于均线 → 预警
            alert = Alert("below_ma", platform, category,
                          product_db_id, "", "", url)
            alert.current_price = current_price
            alert.ma_price = ma
            alert.deviation_pct = deviation
            alert.latest_sales = sales
            alert.n_snapshots = n
            _fill_product_info(db, alert)
            alerts.append(alert)

    return alerts


def _fill_product_info(db: MonitorDB, alert: Alert):
    rows = db.conn.execute(
        "SELECT title, brand FROM products WHERE id = ?",
        (alert.product_db_id,)
    ).fetchall()
    if rows:
        alert.title = rows[0]["title"] or ""
        alert.brand = rows[0]["brand"] or ""


# ═══════════════════════════════════════════════════════════════
#  输出
# ═══════════════════════════════════════════════════════════════

def format_alert_text(alerts: list[Alert], platform: str = "",
                      category: str = "") -> str:
    if not alerts:
        return ""

    header = f"🔔 价格预警 · 低于移动平均"
    if platform:
        header += f" {platform}"
    if category:
        header += f"/{category}"

    lines = [f"{'═' * 55}", f"  {header}", f"{'═' * 55}"]
    for a in alerts:
        parts = [f"  {a.label}"]
        if a.brand:
            parts.append(f"  品牌: {a.brand}")
        parts.append(f"  商品: {a.title[:55]}")
        parts.append(
            f"  价格: {Alert._fmt_price(a.current_price)}  |  "
            f"均线: {Alert._fmt_price(a.ma_price)}  |  "
            f"偏离: {Alert._fmt_pct(a.deviation_pct)}"
        )
        if a.latest_sales:
            parts.append(f"  销量: {Alert._fmt_sales(a.latest_sales)}")
        parts.append(f"  快照: {a.n_snapshots}次 | {a.url}")
        parts.append("")
        lines.extend(parts)
    return "\n".join(lines)


def write_alert_csv(alerts: list[Alert], output_path: str | Path):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(Alert.csv_header())
        for a in alerts:
            writer.writerow(a.to_row())
    logger.info("预警 CSV: %s (%d 条)", output_path, len(alerts))


def write_alert_txt(alerts: list[Alert], output_path: str | Path,
                    platform: str = "", category: str = ""):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = format_alert_text(alerts, platform, category)
    output_path.write_text(text, encoding="utf-8")
    logger.info("预警 TXT: %s", output_path)

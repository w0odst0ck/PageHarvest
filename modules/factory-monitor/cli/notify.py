"""
告警通知 — 检查未处理预警并输出摘要

在 cli/run.py 全流程结束后自动调用。
也支持独立运行：python -m cli.notify

只输出当天新增的未处理预警，避免重复推送。
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import MonitorDB
from config import DB_PATH

logger = logging.getLogger(__name__)


def notify_pending_alerts() -> int:
    """检查未处理预警并输出摘要，返回预警数"""
    db = MonitorDB(DB_PATH)
    db.ensure_schema()

    alerts = db.get_unresolved_alerts()
    if not alerts:
        db.close()
        return 0

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_alerts = [a for a in alerts if a["triggered_at"].startswith(today)]
    total_msg = ""

    if today_alerts:
        print(f"\n{'=' * 45}")
        print(f"  ⚠️  今天新增 {len(today_alerts)} 条预警")
        print(f"{'=' * 45}")
        for a in today_alerts:
            name = a.get("shop_name") or a.get("item_name", "")
            level_icon = {"red": "🔴", "yellow": "🟡", "blue": "🔵"}.get(
                a.get("alert_level", ""), "⚪")
            ts = a["triggered_at"][:19]
            print(f"  {level_icon} [{ts}] {name}")
            print(f"      {a['message']}")
            total_msg += f"\n    {level_icon} {a['message']}"

    if len(alerts) > len(today_alerts):
        print(f"\n  📋 还有 {len(alerts) - len(today_alerts)} 条历史未处理预警")
        print(f"     查看全部: python -m cli.query alerts")

    db.close()
    return len(today_alerts)


def main():
    n = notify_pending_alerts()
    if n == 0:
        print("  ✅ 无新增预警")


if __name__ == "__main__":
    main()

"""
工厂监控报告生成器 — 读取数据库 → 输出 HTML 报告（含 Chart.js 图表）

用法：
  python -m cli.report                          # 仅读库生成报告
  python -m cli.report --run                    # 先跑 pipeline，再生成报告
  python -m cli.report --out ./monitor_report   # 指定输出目录
  python -m cli.report --open                   # 生成后自动打开浏览器
"""

import argparse
import json
import logging
import sys
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.db import MonitorDB
from config import DB_PATH

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Chart.js CDN（轻量 3.x）
CHART_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js"

# ── 模板 ──

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>工厂监控报告 — PageHarvest</title>
  <script src="{CHART_CDN}"></script>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: #f5f7fb; color: #1a1a2e; line-height: 1.6;
    }}
    .container {{ max-width: 1200px; margin: 0 auto; padding: 24px 16px; }}

    /* Header */
    .report-header {{
      background: linear-gradient(135deg, #1a56db, #0f3b8c);
      color: #fff; border-radius: 12px; padding: 32px; margin-bottom: 24px;
    }}
    .report-header h1 {{ font-size: 24px; margin-bottom: 4px; }}
    .report-header p {{ opacity: .85; font-size: 14px; }}

    /* Stats cards */
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
              gap: 12px; margin-bottom: 24px; }}
    .stat-card {{
      background: #fff; border-radius: 10px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,.08);
      text-align: center;
    }}
    .stat-card .num {{ font-size: 32px; font-weight: 700; line-height: 1.2; }}
    .stat-card .label {{ font-size: 13px; color: #666; margin-top: 4px; }}
    .stat-card.green .num {{ color: #16a34a; }}
    .stat-card.amber .num {{ color: #d97706; }}
    .stat-card.red .num {{ color: #dc2626; }}
    .stat-card.blue .num {{ color: #2563eb; }}

    /* Section */
    .section {{ background: #fff; border-radius: 10px; padding: 24px;
                box-shadow: 0 1px 3px rgba(0,0,0,.08); margin-bottom: 16px; }}
    .section h2 {{ font-size: 18px; margin-bottom: 16px; padding-bottom: 8px;
                   border-bottom: 1px solid #eee; }}

    /* Alert list */
    .alert-item {{
      padding: 10px 14px; border-radius: 6px; margin-bottom: 8px;
      font-size: 14px; border-left: 4px solid;
    }}
    .alert-red {{ background: #fef2f2; border-color: #dc2626; }}
    .alert-blue {{ background: #eff6ff; border-color: #2563eb; }}
    .alert-level {{ display: inline-block; padding: 1px 8px; border-radius: 4px;
                    font-size: 12px; font-weight: 600; margin-right: 8px; }}
    .alert-level.lv-red {{ background: #fecaca; color: #991b1b; }}
    .alert-level.lv-blue {{ background: #bfdbfe; color: #1e40af; }}

    /* Table */
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #f0f0f0; white-space: nowrap; }}
    th {{ background: #f8f9fc; font-weight: 600; color: #555; font-size: 12px; text-transform: uppercase;
          letter-spacing: .3px; position: sticky; top: 0; }}
    tr:hover td {{ background: #fafbfe; }}

    .tag {{
      display: inline-block; padding: 1px 6px; border-radius: 4px; font-size: 12px; font-weight: 500;
    }}
    .tag-active {{ background: #dcfce7; color: #166534; }}
    .tag-paused {{ background: #fef9c3; color: #854d0e; }}

    /* Chart area */
    .charts {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }}
    .chart-box {{ background: #fff; border-radius: 10px; padding: 16px;
                  box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    .chart-box h3 {{ font-size: 14px; color: #555; margin-bottom: 8px; text-align: center; }}
    .chart-box canvas {{ max-height: 280px; }}

    /* Footer */
    .report-footer {{ text-align: center; font-size: 12px; color: #999; margin-top: 32px;
                      padding-top: 16px; border-top: 1px solid #e0e0e0; }}

    @media (max-width: 640px) {{
      .charts {{ grid-template-columns: 1fr; }}
      .stats {{ grid-template-columns: repeat(2, 1fr); }}
    }}
  </style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="report-header">
    <h1>📊 工厂监控报告</h1>
    <p>生成时间: {GENERATED_AT} │ 数据来源: monitor.db</p>
  </div>

  <!-- Stats -->
  <div class="stats">
    <div class="stat-card green"><div class="num">{ACTIVE_COUNT}</div><div class="label">Active 工厂</div></div>
    <div class="stat-card amber"><div class="num">{PAUSED_COUNT}</div><div class="label">Paused 工厂</div></div>
    <div class="stat-card red"><div class="num">{ALERT_COUNT}</div><div class="label">未处理预警</div></div>
    <div class="stat-card blue"><div class="num">{SNAPSHOT_COUNT}</div><div class="label">快照总数</div></div>
  </div>

  <!-- Alerts -->
  {ALERTS_SECTION}

  <!-- Charts -->
  <div class="charts">
    <div class="chart-box">
      <h3>📈 工厂商品数分布</h3>
      <canvas id="chartProducts"></canvas>
    </div>
    <div class="chart-box">
      <h3>🧩 认证等级分布</h3>
      <canvas id="chartCert"></canvas>
    </div>
  </div>

  <!-- Factory Table -->
  <div class="section">
    <h2>🏭 工厂清单（{FACTORY_TOTAL} 家）</h2>
    <div class="table-wrap">
      <table>
        <thead><tr>
          <th>#</th><th>店铺名称</th><th>认证等级</th><th>所在地</th>
          <th>开店年数</th><th>商品数</th><th>Top10 均销</th><th>状态</th>
        </tr></thead>
        <tbody>
          {FACTORY_ROWS}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Footer -->
  <div class="report-footer">
    PageHarvest Factory Monitor — {GENERATED_AT_SHORT}
  </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', function() {{
  // 商品数分布
  new Chart(document.getElementById('chartProducts'), {{
    type: 'bar',
    data: {{
      labels: {PRODUCT_BIN_LABELS},
      datasets: [{{
        label: '工厂数',
        data: {PRODUCT_BIN_DATA},
        backgroundColor: 'rgba(37, 99, 235, .6)',
        borderColor: 'rgba(37, 99, 235, 1)',
        borderWidth: 1,
        borderRadius: 4,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: true,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }},
      }}
    }}
  }});

  // 认证等级分布
  new Chart(document.getElementById('chartCert'), {{
    type: 'doughnut',
    data: {{
      labels: {CERT_LABELS},
      datasets: [{{
        data: {CERT_DATA},
        backgroundColor: ['#2563eb', '#16a34a', '#d97706', '#6b7280'],
        borderWidth: 2,
      }}]
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: true,
      plugins: {{
        legend: {{ position: 'bottom', labels: {{ font: {{ size: 12 }}, padding: 12 }} }}
      }}
    }}
  }});
}});
</script>
</body>
</html>
"""


def _get_cert_bucket(cert_level: str) -> str:
    cert = (cert_level or "").strip()
    if not cert:
        return "未标注"
    if "超级" in cert:
        return "超级工厂"
    if "实力" in cert:
        return "实力商家"
    return "普通"


def generate_report(db: MonitorDB, output_dir: str | Path, open_browser: bool = False) -> str:
    """生成 HTML 报告，返回文件路径"""

    # ── 数据查询 ──
    factories = db.conn.execute("""
        SELECT f.*, fs.total_products, fs.top10_avg_sales, fs.snapshot_time
        FROM factories f
        LEFT JOIN (
            SELECT factory_id, total_products, top10_avg_sales, snapshot_time,
                   ROW_NUMBER() OVER (PARTITION BY factory_id ORDER BY snapshot_time DESC) AS rn
            FROM factory_snapshots
        ) fs ON f.id = fs.factory_id AND fs.rn = 1
        ORDER BY f.id
    """).fetchall()

    alerts = db.get_unresolved_alerts()
    total_snapshots = db.conn.execute(
        "SELECT COUNT(*) as c FROM factory_snapshots"
    ).fetchone()["c"]

    active_count = f"{sum(1 for f in factories if f['status'] == 'active')}"
    paused_count = f"{sum(1 for f in factories if f['status'] == 'paused')}"
    alert_count = f"{len(alerts)}"
    snapshot_count = f"{total_snapshots}"

    # ── 工厂表格行 ──
    factory_rows = []
    cert_buckets = {"超级工厂": 0, "实力商家": 0, "普通": 0, "未标注": 0}
    product_bins = {"0": 0, "1-10": 0, "11-50": 0, "51-100": 0, "100+": 0}

    for f in factories:
        cert = _get_cert_bucket(f["cert_level"])
        cert_buckets[cert] = cert_buckets.get(cert, 0) + 1

        tp = f["total_products"]
        if tp is None:
            product_bins["0"] += 1
        elif tp == 0:
            product_bins["0"] += 1
        elif tp <= 10:
            product_bins["1-10"] += 1
        elif tp <= 50:
            product_bins["11-50"] += 1
        elif tp <= 100:
            product_bins["51-100"] += 1
        else:
            product_bins["100+"] += 1

        status_tag = f'<span class="tag tag-active">active</span>' if f["status"] == "active" else f'<span class="tag tag-paused">paused</span>'
        top10 = f"{f['top10_avg_sales']:.0f}" if f["top10_avg_sales"] else "-"
        products = f"{f['total_products']}" if f["total_products"] else "-"
        years = f"{f['years_on_1688']}" if f["years_on_1688"] else "-"

        factory_rows.append(
            f"<tr>"
            f"<td>{f['id']}</td>"
            f"<td><a href='{f['shop_url']}' target='_blank' style='color:#2563eb;text-decoration:none'>{f['shop_name']}</a></td>"
            f"<td>{cert}</td>"
            f"<td>{f['location'] or '-'}</td>"
            f"<td>{years}</td>"
            f"<td>{products}</td>"
            f"<td>{top10}</td>"
            f"<td>{status_tag}</td>"
            f"</tr>"
        )

    # ── 预警部分 ──
    alerts_html = ""
    if alerts:
        alert_items = []
        for a in alerts:
            lv_class = "lv-red" if a["alert_level"] == "red" else "lv-blue"
            alert_class = "alert-red" if a["alert_level"] == "red" else "alert-blue"
            alert_items.append(
                f'<div class="alert-item {alert_class}">'
                f'<span class="alert-level {lv_class}">{a["alert_level"]}</span>'
                f'<strong>{a["shop_name"]}</strong> — {a["message"]}'
                f'</div>'
            )
        alerts_html = f"""
<div class="section">
  <h2>🔔 未处理预警（{len(alerts)} 条）</h2>
  {''.join(alert_items)}
</div>"""

    # ── 图表数据 ──
    bin_order = ["0", "1-10", "11-50", "51-100", "100+"]
    bin_labels = json.dumps(bin_order, ensure_ascii=False)
    bin_data = json.dumps([product_bins[k] for k in bin_order], ensure_ascii=False)

    cert_order = ["超级工厂", "实力商家", "普通", "未标注"]
    cert_labels = json.dumps(cert_order, ensure_ascii=False)
    cert_data = json.dumps([cert_buckets[k] for k in cert_order], ensure_ascii=False)

    # ── 时间 ──
    now = datetime.now(timezone.utc).astimezone()
    generated_at = now.strftime("%Y-%m-%d %H:%M")
    generated_at_short = now.strftime("%Y-%m-%d")

    # ── 渲染 ──
    html = HTML_TEMPLATE.format(
        CHART_CDN=CHART_CDN,
        GENERATED_AT=generated_at,
        GENERATED_AT_SHORT=generated_at_short,
        ACTIVE_COUNT=active_count,
        PAUSED_COUNT=paused_count,
        ALERT_COUNT=alert_count,
        SNAPSHOT_COUNT=snapshot_count,
        ALERTS_SECTION=alerts_html,
        ACTIVE_JSON=json.dumps([int(active_count), int(paused_count)]),
        FACTORY_TOTAL=len(factories),
        FACTORY_ROWS="\n          ".join(factory_rows),
        PRODUCT_BIN_LABELS=bin_labels,
        PRODUCT_BIN_DATA=bin_data,
        CERT_LABELS=cert_labels,
        CERT_DATA=cert_data,
    )

    # ── 写文件 ──
    output_path = Path(output_dir) / f"monitor_report_{now.strftime('%Y%m%d_%H%M')}.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")

    logger.info("报告已生成: %s", output_path)

    if open_browser:
        webbrowser.open(output_path.as_uri())

    return str(output_path)


def main():
    parser = argparse.ArgumentParser(description="工厂监控报告生成器")
    parser.add_argument("--run", action="store_true", help="先运行 pipeline 再生成报告")
    parser.add_argument("--out", default="./reports", help="输出目录 (default: ./reports)")
    parser.add_argument("--open", action="store_true", help="生成后自动打开浏览器")
    parser.add_argument("--keyword", default="小夜灯", help="pipeline 关键词")
    parser.add_argument("--pages", type=int, default=5, help="pipeline 搜索页数")
    args = parser.parse_args()

    db = MonitorDB(DB_PATH)
    db.ensure_schema()

    if args.run:
        logger.info("运行 pipeline（keyword=%s, pages=%d）", args.keyword, args.pages)
        from collector.search import search_factories
        from collector.offers import collect_offers
        from engine.filter import run_filter
        from engine.alerter import run_alerts

        search_factories(args.keyword, args.pages)
        collect_offers()
        run_filter(db)
        run_alerts(db)

    generate_report(db, args.out, open_browser=args.open)
    db.close()


if __name__ == "__main__":
    main()

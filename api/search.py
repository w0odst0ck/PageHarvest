"""
PageHarvest 搜索页选品 — 稳定封存模块

搜索页处理逻辑，冻结后不可修改。
仅通过 api.engine.process_upload() 调用。
"""

import os
import sys
import csv
import io
import subprocess
import logging
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── 路径 ──
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


# ═══════════════════════════════════════════════════════════════
#  API：搜索页选品分析
# ═══════════════════════════════════════════════════════════════

@dataclass
class SearchResult:
    csv_content: str = ""
    txt_content: str = ""
    platform: str = ""
    product_count: int = 0
    error: str = ""


def detect_platform_from_name(filename: str) -> str:
    """从文件名猜测平台（XLSX 等非 HTML 文件备用）"""
    low = filename.lower()
    if "1688" in low or "alibaba" in low:
        return "1688"
    if "zkh" in low or "震坤行" in low:
        return "震坤行"
    if "jd" in low or "jingdong" in low or "京东" in low:
        return "京东"
    return "未知"


def _detect_category(job) -> str:
    """从文件名推断品类"""
    files = job.html_files() or job.xlsx_files()
    if not files:
        return "品类"
    name = files[0].stem  # 去掉扩展名
    import re
    # 常见模式: "灯具_商品搜索_..." "灯具 - 商品搜索 - ..." "灯具1-商品列表-..."
    # 先尝试常见分隔符前的第一个片段
    candidates = []
    for sep in ["_", " - ", "-", " "]:
        parts = name.split(sep)
        if len(parts) > 1:
            first = parts[0].strip()
            if re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9]{1,10}$', first):
                candidates.append(first)
    if candidates:
        raw = candidates[0]
        # 去掉尾随数字（如 "灯具1" → "灯具"），但保留纯英文品牌
        cleaned = re.sub(r'\d+$', '', raw)
        if cleaned:
            return cleaned
        return raw
    return "品类"


def run_search_pipeline(job) -> SearchResult:
    """搜索页选品分析 → 子进程调原始 picker
    job: Job 实例（defines html_files(), xlsx_files(), extract_dir, output_dir）"""
    result = SearchResult()

    # 检测平台
    if job.html_files():
        with open(job.html_files()[0], "r", encoding="utf-8", errors="replace") as f:
            sample = f.read()
        platform = job.detect_platform(sample)
    elif job.xlsx_files():
        platform = detect_platform_from_name(job.xlsx_files()[0].name)
        if platform == "未知":
            result.error = "无法从文件名识别平台"
            return result
    else:
        result.error = "未找到 HTML 或 XLSX 文件"
        return result
    result.platform = platform

    # 平台短名映射（用于输出目录）
    _PLATFORM_DIR = {"震坤行": "ZKH", "京东": "JD", "1688": "1688"}
    platform_dir = _PLATFORM_DIR.get(platform, platform)

    # 品类自动检测
    category = _detect_category(job)

    # 输出目录: output/{platform_short}/{category}/搜索页/
    # 输出目录基准（picker 会追加 {name}/搜索页/）
    out_dir = ROOT / "output" / platform_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        if platform == "1688":
            # 自动判断：有 XLSX 就走 XLSX，否则用 HTML
            has_xlsx = bool(job.xlsx_files())
            cmd = [sys.executable, "-m", "selection.1688-picker",
                   str(job.extract_dir), "--name", category, "--output", str(out_dir)]
            if not has_xlsx:
                cmd.append("--from-html")
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=180, cwd=str(ROOT),
            )

        elif platform == "震坤行":
            proc = subprocess.run(
                [sys.executable, "-m", "selection.zkh-picker",
                 str(job.extract_dir), "--name", category, "--output", str(out_dir)],
                capture_output=True, text=True, timeout=180, cwd=str(ROOT),
            )

        elif platform == "京东":
            # JD picker 需要 CSV，先子进程解析 HTML 转 CSV
            tmp_csv = out_dir / "_input.csv"
            convert_proc = subprocess.run(
                [sys.executable, str(HERE / "jd_html2csv.py"),
                 str(job.extract_dir), "-o", str(tmp_csv)],
                capture_output=True, text=True, timeout=120, cwd=str(ROOT),
            )
            if convert_proc.returncode != 0:
                result.error = f"HTML 转 CSV 失败: {convert_proc.stderr or convert_proc.stdout}"
                return result

            proc = subprocess.run(
                [sys.executable, "-m", "selection.jd-picker",
                 str(tmp_csv), "--name", category, "--output", str(out_dir)],
                capture_output=True, text=True, timeout=180, cwd=str(ROOT),
            )

        else:
            result.error = f"暂不支持平台: {platform}"
            return result

        if proc.returncode != 0:
            result.error = proc.stderr or proc.stdout or "选品分析失败"
            return result

        # 读取结果
        cat_dir = out_dir / category / "搜索页"
        if not cat_dir.is_dir():
            result.error = "未生成结果文件"
            return result

        summary_file = cat_dir / "00-选品推荐合集.csv"
        if summary_file.exists():
            result.csv_content = summary_file.read_text(encoding="utf-8-sig")
            import pandas as pd
            df = pd.read_csv(io.StringIO(result.csv_content))
        else:
            import pandas as pd
            parts = []
            for tag in ["🔥 必上", "👍 推荐", "💡 暗马", "📌 关注"]:
                fp = cat_dir / f"{tag}.csv"
                if fp.exists():
                    parts.append(pd.read_csv(fp, encoding="utf-8-sig"))
            if parts:
                df = pd.concat(parts, ignore_index=True)
                buf = io.StringIO()
                df.to_csv(buf, index=False, encoding="utf-8-sig")
                result.csv_content = buf.getvalue()
            else:
                result.error = "未找到选品结果"
                return result

        result.product_count = len(df)

        # TXT 报告
        lines = [f"PageHarvest 选品分析报告 — {platform}", ""]
        if "策略" in df.columns:
            for tag in ["🔥 必上", "👍 推荐", "💡 暗马", "📌 关注"]:
                subset = df[df["策略"] == tag]
                if not subset.empty:
                    lines.append(f"【{tag}】{len(subset)} 件")
                    lines.append("-" * 36)
                    for _, r in subset.iterrows():
                        b = r.get("品牌", "")
                        p = r.get("价格", 0)
                        t = str(r.get("标题", ""))[:40]
                        lines.append(f"  {str(b or '-'):8} ¥{float(p):<8.2f} {t}")
                    lines.append("")

        result.txt_content = "\n".join(lines)
        return result

    except subprocess.TimeoutExpired:
        result.error = "选品分析超时（>180 秒）"
        return result
    except Exception as e:
        result.error = f"搜索分析异常: {e}"
        return result

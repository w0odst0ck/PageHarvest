"""
PageHarvest 搜索页选品 — 稳定封存模块

搜索页处理逻辑，冻结后不可修改。
仅通过 api.engine.process_upload() 调用。
"""

import os
import sys
import csv
import io
import importlib
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
    name = files[0].stem
    import re
    candidates = []
    for sep in ["_", " - ", "-", " "]:
        parts = name.split(sep)
        if len(parts) > 1:
            first = parts[0].strip()
            if re.match(r'^[\u4e00-\u9fa5a-zA-Z0-9]{1,10}$', first):
                candidates.append(first)
    if candidates:
        raw = candidates[0]
        cleaned = re.sub(r'\d+$', '', raw)
        if cleaned:
            return cleaned
        return raw
    return "品类"


def _load_picker(name: str):
    """用 importlib 加载含连字符的 picker 模块"""
    return importlib.import_module(f"selection.{name}")


def run_search_pipeline(job) -> SearchResult:
    """搜索页选品分析 → 直接调 picker 函数（不经过 subprocess）"""
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

    _PLATFORM_DIR = {"震坤行": "ZKH", "京东": "JD", "1688": "1688"}
    platform_dir = _PLATFORM_DIR.get(platform, platform)
    category = _detect_category(job)
    out_dir = ROOT / "output" / platform_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        if platform == "1688":
            picker = _load_picker("1688-picker")
            has_xlsx = bool(job.xlsx_files())

            if has_xlsx:
                import glob
                products = []
                for f in job.xlsx_files():
                    p = picker.parse_xlsx(str(f))
                    logger.info(f"  {f.name}: {len(p)} 条")
                    products.extend(p)
            else:
                products = picker.parse_html_dir(str(job.extract_dir))

            if not products:
                result.error = "1688 无数据"
                return result
            # 去重
            seen = set()
            unique = []
            for p in products:
                pid = p.get("product_id") or p.get("title", "")
                if pid not in seen:
                    seen.add(pid)
                    unique.append(p)

            picker.analyze(category, unique, str(out_dir))

        elif platform == "震坤行":
            picker = _load_picker("zkh-picker")
            picker.analyze_category(category, str(job.extract_dir), str(out_dir))

        elif platform == "京东":
            # JD: HTML → CSV → picker
            from api.jd_html2csv import convert as jd_convert
            tmp_csv = out_dir / "_input.csv"
            count = jd_convert(str(job.extract_dir), str(tmp_csv))

            if count == 0:
                result.error = "JD HTML 转 CSV 失败"
                return result

            picker = _load_picker("jd-picker")
            picker.analyze(category, str(tmp_csv), str(out_dir))

        else:
            result.error = f"暂不支持平台: {platform}"
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

    except Exception as e:
        result.error = f"搜索分析异常: {e}"
        import traceback
        logger.error(traceback.format_exc())
        return result

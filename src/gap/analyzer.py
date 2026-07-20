"""
gap/analyzer.py — 商品缺口分析核心逻辑

跨平台比对：将 PageHarvest 选品清单（CSV/JSON）与目标平台在售商品库
（XLSX/CSV）进行多步匹配，找出缺失商品，输出结构化缺品报告。

适配工作流：
  1. read_listing()       → 读取选品清单（支持 CSV子文件夹+门类识别）
  2. read_inventory()     → 读取在售商品库（XLSX/CSV 自动识别）
  3. standardize_keys()   → 统一生成标准化 match_key
  4. find_gaps()          → 左反连接计算缺失商品
  5. fuzzy_verify()       → 可选：模糊匹配二次校验
  6. export_report()      → 导出 Excel 报告（缺品明细 + 统计 + 潜匹配表）

整合自 product-gap-analyzer，适配 PageHarvest 架构。
"""

import os
import re
import glob
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# ── 默认列名常量 ────────────────────────────────────────────────

# 震坤行选品清单（由 zkh-picker.py 输出）
LISTING_COLUMNS_ZKH = ["策略", "排名", "品牌", "标题", "价格", "型号", "行家精选", "链接"]

# 河姆渡在售商品
INVENTORY_COLUMNS_HMD = [
    "SKU编号", "SPU编号", "U8/WMS编码", "实际商品编号",
    "商品名称", "副标题", "一级分类", "二级分类", "三级分类",
    "市场价", "品牌", "规格型号",
]

# ── 第一步：读取选品清单 ────────────────────────────────────────


def read_listing(
    folder_path: str,
    file_pattern: str = "00-选品推荐合集.csv",
) -> Dict[str, Any]:
    """读取选品清单 CSV（按子文件夹=门类），自动合并。

    目录结构预期：
        {folder_path}/{门类}/00-选品推荐合集.csv  ← 主力数据源

    Args:
        folder_path: 选品清单根目录
        file_pattern: 目标文件名（默认取合集文件）

    Returns:
        { row_count, columns, sample, categories, data }
    """
    if not os.path.isdir(folder_path):
        raise FileNotFoundError(f"目录不存在: {folder_path}")

    all_dfs: List[pd.DataFrame] = []

    # 扫描子文件夹（每个 = 一个门类）
    subdirs = sorted([
        d for d in os.listdir(folder_path)
        if os.path.isdir(os.path.join(folder_path, d)) and not d.startswith("_")
    ])

    if not subdirs:
        # 无子文件夹，直接从根目录读
        csv_files = glob.glob(os.path.join(folder_path, file_pattern))
        for cf in csv_files:
            df = _read_csv_safe(cf)
            df["来源门类"] = os.path.basename(folder_path)
            all_dfs.append(df)
            logger.info("  已读取 %s (%d 行)", os.path.basename(cf), len(df))
    else:
        for sub in subdirs:
            search_dir = os.path.join(folder_path, sub)
            # 主数据源：选品推荐合集
            collection_file = os.path.join(search_dir, file_pattern)
            if os.path.exists(collection_file):
                df = _read_csv_safe(collection_file)
                df["来源门类"] = sub
                all_dfs.append(df)
                logger.info("  %s → %s (%d 行)", sub, file_pattern, len(df))
            else:
                # 兜底：读该目录下所有 CSV
                csv_files = glob.glob(os.path.join(search_dir, "*.csv"))
                for cf in csv_files:
                    base = os.path.basename(cf)
                    df = _read_csv_safe(cf)
                    df["来源门类"] = sub
                    if "策略" not in df.columns:
                        df["策略"] = os.path.splitext(base)[0]
                    all_dfs.append(df)
                    logger.info("  %s → %s (%d 行)", sub, base, len(df))

    if not all_dfs:
        raise FileNotFoundError(f"在 {folder_path} 中未找到 CSV 文件（模式: {file_pattern}）")

    merged = pd.concat(all_dfs, ignore_index=True)
    logger.info("合并后共 %d 行，%d 个门类", len(merged), merged["来源门类"].nunique())

    return _df_to_result(merged)


def read_csv_wizard(filepath: str, encoding_hints: list = None) -> pd.DataFrame:
    """万能 CSV 读取器（自动探测编码 + 分隔符），也兼容 gap 模块独立使用。"""
    return _read_csv_safe(filepath, encodings=encoding_hints)


def _read_csv_safe(path: str, encodings: list = None) -> pd.DataFrame:
    """安全读取 CSV（自动检测编码）"""
    if encodings is None:
        encodings = ("utf-8-sig", "utf-8", "gbk", "gb2312", "gb18030")
    for enc in encodings:
        try:
            df = pd.read_csv(path, dtype=str, encoding=enc)
            if df.shape[1] >= 2:  # 至少 2 列才视为有效
                return df
        except (UnicodeDecodeError, Exception):
            continue
    # 最后尝试一次
    return pd.read_csv(path, dtype=str, encoding="utf-8", errors="replace")


# ── 第二步：读取在售商品 ────────────────────────────────────────


def read_inventory(file_path: str = "") -> Dict[str, Any]:
    """读取在售商品库（XLSX 优先，兜底 CSV）。

    支持自动发现：如果 file_path 为空，尝试搜当前目录/Downloads。

    Args:
        file_path: XLSX 或 CSV 文件路径

    Returns:
        { row_count, columns, sample, sheet_name, data }
    """
    path = file_path
    if not path:
        # 自动发现
        candidates = glob.glob(os.path.join(os.path.expanduser("~"), "Downloads", "河姆渡-all-*.xlsx"))
        if not candidates:
            candidates = glob.glob("河姆渡-all-*.xlsx")
        if candidates:
            path = sorted(candidates)[-1]

    if not path or not os.path.exists(path):
        raise FileNotFoundError(
            f"在售商品数据文件不存在: {path}\n"
            f"请通过 --inventory 参数或环境变量 GAP_INVENTORY_FILE 指定"
        )

    ext = os.path.splitext(path)[1].lower()
    logger.info("读取在售商品: %s", path)

    if ext in (".xlsx", ".xls"):
        xls = pd.ExcelFile(path)
        # 找最合适的 sheet
        sheet_name = None
        for pref in ["基础信息", "商品信息", "商品列表", "Sheet1"]:
            if pref in xls.sheet_names:
                sheet_name = pref
                break
        if not sheet_name:
            sheet_name = xls.sheet_names[0]
            logger.info("未匹配到标准 Sheet 名，使用 '%s'", sheet_name)
        df = pd.read_excel(path, sheet_name=sheet_name, dtype=str)
        logger.info("  Sheet '%s' → %d 行, %d 列", sheet_name, len(df), len(df.columns))
    elif ext == ".csv":
        sheet_name = "CSV"
        df = _read_csv_safe(path)
        logger.info("  CSV → %d 行, %d 列", len(df), len(df.columns))
    else:
        raise ValueError(f"不支持的文件格式: {ext}")

    return {
        "row_count": len(df),
        "columns": list(df.columns),
        "sample": df.head(3).to_dict(orient="records"),
        "sheet_name": sheet_name,
        "data": df.to_dict(orient="records"),
    }


# ── 第三步：标准化匹配键 ────────────────────────────────────────


def standardize_keys(
    data: List[Dict[str, Any]],
    key_hint: Optional[str] = None,
    source_label: str = "unknown",
) -> Dict[str, Any]:
    """统一生成标准化 match_key，自动识别数据源类型。

    识别逻辑：
      - 列含"标题" → ZKH 选品清单
      - 列含"商品名称" → 河姆渡在售
      - 用户指定 key_hint → 优先使用

    Args:
        data: 数据行列表
        key_hint: 手动指定作为匹配键的列名
        source_label: 数据来源标识（仅日志用）

    Returns:
        { detected_key, cleaned_data, row_count }
    """
    df = pd.DataFrame(data)
    if df.empty:
        return {"detected_key": "", "cleaned_data": [], "row_count": 0}

    df.columns = df.columns.str.strip()

    if key_hint and key_hint in df.columns:
        df["match_key"] = df[key_hint].astype(str).apply(_clean_key)
        detected = key_hint
    elif "标题" in df.columns and "商品名称" not in df.columns:
        df["match_key"] = df["标题"].astype(str).apply(_clean_key)
        detected = "标题"
    elif "商品名称" in df.columns:
        df["match_key"] = df["商品名称"].astype(str).apply(_clean_key)
        detected = "商品名称"
    else:
        # 兜底：用最佳文本列
        text_cols = [c for c in df.columns if "名" in c or "标题" in c or "品名" in c or "title" in c.lower()]
        if text_cols:
            col = text_cols[0]
        else:
            col = df.columns[0]
        logger.warning("无法自动识别键列，使用 '%s'", col)
        df["match_key"] = df[col].astype(str).apply(_clean_key)
        detected = col

    # 辅助：从链接提取 item_id（选品侧）
    if "链接" in df.columns:
        df["item_id"] = df["链接"].apply(_extract_item_id)

    null_count = df["match_key"].isna().sum()
    logger.info("[%s] 匹配键: %s → %d 行 (空值 %d)", source_label, detected, len(df), null_count)

    return {
        "detected_key": detected,
        "cleaned_data": df.to_dict(orient="records"),
        "row_count": len(df),
    }


def _clean_key(value: Any) -> str:
    """标准化清洗：跨平台商品标题匹配用。"""
    if not isinstance(value, str):
        value = str(value) if pd.notna(value) else ""
    if not value:
        return ""

    # 全角 → 半角
    full_to_half = {
        "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
        "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
        "Ａ": "A", "Ｂ": "B", "Ｃ": "C", "Ｄ": "D", "Ｅ": "E",
        "Ｆ": "F", "Ｇ": "G", "Ｈ": "H", "Ｉ": "I", "Ｊ": "J",
        "Ｋ": "K", "Ｌ": "L", "Ｍ": "M", "Ｎ": "N", "Ｏ": "O",
        "Ｐ": "P", "Ｑ": "Q", "Ｒ": "R", "Ｓ": "S", "Ｔ": "T",
        "Ｕ": "U", "Ｖ": "V", "Ｗ": "W", "Ｘ": "X", "Ｙ": "Y",
        "Ｚ": "Z",
        "ａ": "a", "ｂ": "b", "ｃ": "c", "ｄ": "d", "ｅ": "e",
        "ｆ": "f", "ｇ": "g", "ｈ": "h", "ｉ": "i", "ｊ": "j",
        "ｋ": "k", "ｌ": "l", "ｍ": "m", "ｎ": "n", "ｏ": "o",
        "ｐ": "p", "ｑ": "q", "ｒ": "r", "ｓ": "s", "ｔ": "t",
        "ｕ": "u", "ｖ": "v", "ｗ": "w", "ｘ": "x", "ｙ": "y",
        "ｚ": "z",
        "（": "(", "）": ")", "，": ",", "；": ";",
        "：": ":", "！": "!", "？": "?", "＂": '"', "＇": "'",
    }
    for full, half in full_to_half.items():
        value = value.replace(full, half)

    value = re.sub(r"\s+", "", value)            # 去空白
    value = value.upper()                         # 统一大写
    value = re.sub(r"[-_./・·#&@~]", "", value)   # 去分隔符
    value = re.sub(r"^[A-Z]+/", "", value)        # 去品牌前缀 FSL/ BULL/

    return value


def _extract_item_id(url: str) -> str:
    """从 URL 提取商品 ID（适配多平台）"""
    if not isinstance(url, str):
        return ""
    # 震坤行: /item/AA9430979.html
    m = re.search(r"/item/([A-Za-z0-9]+)\.html", url)
    if m:
        return m.group(1)
    # 1688: /offer/1234567890.html
    m = re.search(r"/offer/(\d+)\.html", url)
    if m:
        return m.group(1)
    return ""


# ── 第四步：差集计算 ─────────────────────────────────────────────


def find_gaps(
    source_data: List[Dict[str, Any]],
    target_data: List[Dict[str, Any]],
    match_key: str = "match_key",
    id_key: str = "item_id",
    target_has_id: bool = False,
    id_col_target: str = "SKU编号",
) -> Dict[str, Any]:
    """左反连接：选品清单中有、在售商品中没有的商品。

    匹配优先级：
      1. match_key 精确匹配（主方案）
      2. 如果双方都有 item_id，辅助验证去重

    Args:
        source_data: 选品清单（已清洗，含 match_key）
        target_data: 在售清单（已清洗，含 match_key）
        match_key: 主匹配键列名
        id_key: 选品侧 ID 列名
        target_has_id: 在售侧是否有可匹配的 ID 列
        id_col_target: 在售侧 ID 列名

    Returns:
        { gap_count, total_source, total_target, gap_rate, gap_list, ... }
    """
    source_df = pd.DataFrame(source_data)
    target_df = pd.DataFrame(target_data)

    if source_df.empty:
        return {
            "gap_count": 0, "total_source": 0,
            "total_target": len(target_df), "gap_rate": 0.0,
            "gap_list": [],
        }

    # 去空
    source_valid = source_df[
        source_df[match_key].notna() & (source_df[match_key] != "")
    ].copy()
    target_keys = set(target_df[match_key].dropna().unique())

    missing_mask = ~source_valid[match_key].isin(target_keys)
    gap_df = source_valid[missing_mask].copy()

    # 如果选品侧有 item_id 且在售侧也有匹配列，辅助去重
    if id_key in gap_df.columns and target_has_id and id_col_target in target_df.columns:
        target_ids = set(target_df[id_col_target].dropna().unique())
        source_ids_valid = gap_df[id_key].notna() & (gap_df[id_key] != "")
        id_matched = gap_df[source_ids_valid][id_key].isin(target_ids)
        # 排除 ID 匹配上的
        id_matched_indices = gap_df[source_ids_valid][id_matched].index
        gap_df = gap_df.drop(index=id_matched_indices, errors="ignore")

    gap_count = len(gap_df)
    total_source = len(source_valid)
    total_target = len(target_df)
    gap_rate = gap_count / total_source if total_source > 0 else 0.0

    logger.info(
        "选品 %d → 在售 %d → 缺失 %d (%.1f%%)",
        total_source, total_target, gap_count, gap_rate * 100,
    )

    return {
        "gap_count": gap_count,
        "total_source": total_source,
        "total_target": total_target,
        "gap_rate": gap_rate,
        "gap_list": gap_df.to_dict(orient="records"),
        "sample": gap_df.head(5).to_dict(orient="records"),
    }


# ── 第五步：模糊匹配二次校验 ────────────────────────────────────


def fuzzy_verify(
    suspect_data: List[Dict[str, Any]],
    target_data: List[Dict[str, Any]],
    threshold: int = 55,
    title_col_l: str = "标题",
    title_col_r: str = "商品名称",
    brand_col_l: str = "品牌",
    brand_col_r: str = "品牌",
) -> Dict[str, Any]:
    """对精确匹配后仍缺失的商品，做标题+品牌模糊匹配。

    Args:
        suspect_data: 疑似缺失商品列表
        target_data: 在售商品全量
        threshold: 相似度阈值（0-100，跨平台推荐 50-60）
        title_col_l: 选品侧标题列名
        title_col_r: 在售侧商品名称列名
        brand_col_l: 选品侧品牌列名
        brand_col_r: 在售侧品牌列名

    Returns:
        { confirmed_gaps, potential_matches, confirmed_count, potential_count }
    """
    try:
        from rapidfuzz import fuzz
    except ImportError:
        logger.warning("rapidfuzz 未安装 (pip install rapidfuzz)，模糊匹配跳过")
        return {
            "confirmed_gaps": suspect_data,
            "potential_matches": [],
            "confirmed_count": len(suspect_data),
            "potential_count": 0,
        }

    source_df = pd.DataFrame(suspect_data)
    target_df = pd.DataFrame(target_data)

    # 动态解析列名
    src_title = _resolve_col(source_df, title_col_l, ["标题", "商品名称"])
    src_brand = _resolve_col(source_df, brand_col_l, ["品牌"])
    tgt_title = _resolve_col(target_df, title_col_r, ["商品名称", "标题"])
    tgt_brand = _resolve_col(target_df, brand_col_r, ["品牌"])

    confirmed = []
    potentials = []

    for _, src_row in source_df.iterrows():
        src_name = str(src_row.get(src_title, "")).strip()
        src_b = str(src_row.get(src_brand, "")).strip() if src_brand else ""

        best_score = 0
        best_target = None

        for _, tgt_row in target_df.iterrows():
            tgt_name = str(tgt_row.get(tgt_title, "")).strip()
            tgt_b = str(tgt_row.get(tgt_brand, "")).strip() if tgt_brand else ""

            title_score = fuzz.token_sort_ratio(src_name, tgt_name)

            if src_b and tgt_b:
                brand_score = 100 if src_b.lower() == tgt_b.lower() else 0
                score = int(title_score * 0.8 + brand_score * 0.2)
            else:
                score = title_score

            if score > best_score:
                best_score = score
                best_target = tgt_row.to_dict()

        if best_score >= threshold:
            potentials.append({
                "产品": src_row.to_dict(),
                "候选匹配": best_target,
                "相似度": best_score,
            })
        else:
            confirmed.append(src_row.to_dict())

    logger.info(
        "模糊匹配：确认缺失 %d，潜在匹配 %d（阈值 %d）",
        len(confirmed), len(potentials), threshold,
    )

    return {
        "confirmed_gaps": confirmed,
        "potential_matches": potentials,
        "confirmed_count": len(confirmed),
        "potential_count": len(potentials),
    }


def _resolve_col(df: pd.DataFrame, preferred: str, fallbacks: List[str]) -> str:
    """智能列名解析：优先 preferred，否则 fallbacks 中找第一个存在的"""
    if preferred in df.columns:
        return preferred
    for col in fallbacks:
        if col in df.columns:
            return col
    return df.columns[0]


# ── 第六步：导出报告 ─────────────────────────────────────────────


def export_report(
    gap_data: List[Dict[str, Any]],
    output_folder: str,
    file_prefix: str = "缺口分析报告",
    fuzzy_matches: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """导出缺品 Excel 报告。

    输出 Sheet:
      - 缺品明细     → 所有确认缺失的商品
      - 门类统计     → 按门类分组统计
      - 策略统计     → 按策略分组统计（如必上/推荐/暗马/关注）
      - 门类+策略    → 交叉统计
      - 潜匹配(需人工确认) → 模糊匹配候选表

    Args:
        gap_data: 缺失商品数据
        output_folder: 输出目录
        file_prefix: 文件名前缀
        fuzzy_matches: 模糊匹配结果（可选）

    Returns:
        { output_path, summary, total_gaps, categories }
    """
    df = pd.DataFrame(gap_data)

    if df.empty:
        return {
            "output_path": "",
            "summary": "✅ 无缺失商品——选品清单中的所有商品均已在在售商品库中找到。",
            "total_gaps": 0,
            "categories": [],
        }

    Path(output_folder).mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_folder, f"{file_prefix}_{date_str}.xlsx")

    # 去除内部辅助列
    export_df = df.copy()
    internal_cols = ["match_key", "item_id"]
    export_df.drop(columns=[c for c in internal_cols if c in export_df.columns], inplace=True, errors="ignore")

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        # Sheet 1: 缺品明细
        export_df.to_excel(writer, sheet_name="缺品明细", index=False)

        # Sheet 2+ 多维度统计
        stats = {}
        if "来源门类" in export_df.columns:
            stats["门类统计"] = (
                export_df.groupby("来源门类")
                .size().reset_index(name="缺失数量")
                .sort_values("缺失数量", ascending=False)
            )
        if "策略" in export_df.columns:
            stats["策略统计"] = (
                export_df.groupby("策略")
                .size().reset_index(name="缺失数量")
                .sort_values("缺失数量", ascending=False)
            )
        if "来源门类" in export_df.columns and "策略" in export_df.columns:
            stats["门类+策略"] = (
                export_df.groupby(["来源门类", "策略"])
                .size().reset_index(name="缺失数量")
                .sort_values(["来源门类", "缺失数量"], ascending=[True, False])
            )
        for name, sdf in stats.items():
            sdf.to_excel(writer, sheet_name=name, index=False)

        # 潜匹配人工审核表
        if fuzzy_matches and fuzzy_matches.get("potential_matches"):
            rows = []
            for m in fuzzy_matches["potential_matches"]:
                src = m.get("产品", {})
                tgt = m.get("候选匹配", {})
                rows.append({
                    "相似度(%)": m.get("相似度", 0),
                    "来源门类": src.get("来源门类", ""),
                    "策略": src.get("策略", ""),
                    "选品_品牌": src.get("品牌", ""),
                    "选品_标题": src.get("标题", ""),
                    "选品_型号": src.get("型号", ""),
                    "选品_价格": src.get("价格", ""),
                    "选品_链接": src.get("链接", ""),
                    "在售_品牌": tgt.get("品牌", ""),
                    "在售_名称": tgt.get("商品名称", ""),
                    "在售_规格": tgt.get("规格型号", ""),
                    "在售_SKU": tgt.get("SKU编号", ""),
                })
            pd.DataFrame(rows).sort_values("相似度(%)", ascending=False) \
                .to_excel(writer, sheet_name="潜匹配(需人工确认)", index=False)

    # 摘要
    total = len(df)
    category_list = stats.get("门类统计", pd.DataFrame()).to_dict(orient="records")
    lines = [
        f"📋 缺失商品总计: {total} 个",
        f"     来源: {df['来源门类'].nunique() if '来源门类' in df.columns else 'N/A'} 个门类",
    ]
    if category_list:
        lines.append("")
        lines.append("按门类:")
        for row in category_list:
            lines.append(f"  - {row['来源门类']}: {row['缺失数量']} 个")
    lines.append("")
    lines.append(f"📁 导出: {output_path}")

    return {
        "output_path": output_path,
        "summary": "\n".join(lines),
        "total_gaps": total,
        "categories": category_list,
    }


# ── 一站运行 ────────────────────────────────────────────────────


def run_pipeline(
    listing_folder: str,
    inventory_file: str,
    output_folder: str = "",
    listing_pattern: str = "00-选品推荐合集.csv",
    key_hint: Optional[str] = None,
    fuzzy: bool = False,
    fuzzy_threshold: int = 55,
    verbose: bool = False,
) -> Dict[str, Any]:
    """一站式缺口分析管道。

    Args:
        listing_folder: 选品清单根目录
        inventory_file: 在售商品文件路径
        output_folder: 输出目录（空=输出到 listing_folder）
        listing_pattern: 选品清单文件名模式
        key_hint: 指定匹配键列名
        fuzzy: 启用模糊匹配
        fuzzy_threshold: 模糊匹配阈值
        verbose: 详细日志

    Returns:
        包含所有步骤结果的字典
    """
    if verbose:
        logger.setLevel(logging.DEBUG)

    result = {"steps": {}, "status": "ok"}

    # Step 1
    logger.info("▶ Step 1/6: 读取选品清单...")
    listing = read_listing(listing_folder, listing_pattern)
    result["steps"]["read_listing"] = {
        "row_count": listing["row_count"],
        "categories": listing["categories"],
    }
    logger.info("  ✓ %d 行, %d 个门类", listing["row_count"], len(listing["categories"]))

    # Step 2
    logger.info("▶ Step 2/6: 读取在售商品...")
    inventory = read_inventory(inventory_file)
    result["steps"]["read_inventory"] = {"row_count": inventory["row_count"]}
    logger.info("  ✓ %d 行", inventory["row_count"])

    # Step 3
    logger.info("▶ Step 3/6: 标准化匹配键...")
    listing_std = standardize_keys(listing["data"], key_hint=key_hint, source_label="选品")
    inventory_std = standardize_keys(inventory["data"], key_hint=key_hint, source_label="在售")
    result["steps"]["standardize"] = {
        "listing_key": listing_std["detected_key"],
        "inventory_key": inventory_std["detected_key"],
    }

    # Step 4
    logger.info("▶ Step 4/6: 计算缺失商品...")
    target_has_id = "SKU编号" in (pd.DataFrame(inventory_std["cleaned_data"]).columns)
    gaps = find_gaps(
        listing_std["cleaned_data"],
        inventory_std["cleaned_data"],
        target_has_id=target_has_id,
    )
    result["steps"]["find_gaps"] = {
        "gap_count": gaps["gap_count"],
        "gap_rate": gaps["gap_rate"],
    }
    logger.info("  ✓ 缺失: %d/%d (%.1f%%)", gaps["gap_count"], gaps["total_source"], gaps["gap_rate"] * 100)

    if gaps["gap_rate"] > 0.8:
        logger.warning("⚠️ 缺品率 %.1f%% > 80%%，请确认数据源范围是否一致。", gaps["gap_rate"] * 100)

    # Step 5
    fuzzy_result = None
    confirmed_gaps = gaps["gap_list"]
    if fuzzy and gaps["gap_count"] > 0:
        logger.info("▶ Step 5/6: 模糊匹配二次校验...")
        fuzzy_result = fuzzy_verify(
            confirmed_gaps,
            inventory_std["cleaned_data"],
            threshold=fuzzy_threshold,
        )
        if fuzzy_result["potential_count"] > 0:
            logger.info("  ✓ 排除 %d 个潜匹配（≥%d%%）", fuzzy_result["potential_count"], fuzzy_threshold)
            confirmed_gaps = fuzzy_result["confirmed_gaps"]
        else:
            logger.info("  ✓ 无潜匹配，全部确认为缺失")
        result["steps"]["fuzzy_verify"] = {
            "confirmed": fuzzy_result["confirmed_count"],
            "potential": fuzzy_result["potential_count"],
        }
    else:
        status = "跳过" if not fuzzy else "无需模糊匹配（缺品为零）"
        logger.info("▶ Step 5/6: 模糊匹配（%s）", status)

    # Step 6
    logger.info("▶ Step 6/6: 导出缺口报告...")
    out_dir = output_folder or listing_folder
    report = export_report(
        confirmed_gaps,
        out_dir,
        fuzzy_matches=fuzzy_result,
    )
    result["steps"]["export"] = {
        "output_path": report["output_path"],
        "total_gaps": report["total_gaps"],
    }
    logger.info("  ✓ 报告已导出")

    result["report"] = report
    result["summary"] = report["summary"]
    return result


# ── 辅助 ─────────────────────────────────────────────────────────


def _df_to_result(df: pd.DataFrame) -> Dict[str, Any]:
    return {
        "row_count": len(df),
        "columns": list(df.columns),
        "sample": df.head(3).to_dict(orient="records"),
        "categories": sorted(df["来源门类"].unique()) if "来源门类" in df.columns else [],
        "data": df.to_dict(orient="records"),
    }


# ── 工具注册表（供 OpenClaw Agent / MCP 调用）────────────────────

TOOLS_SCHEMA = [
    {
        "name": "read_listing",
        "description": "读取选品清单 CSV（子文件夹=门类），自动合并去重",
        "parameters": {
            "folder_path": {"type": "string", "description": "选品清单根目录"},
            "file_pattern": {"type": "string", "default": "00-选品推荐合集.csv"},
        },
    },
    {
        "name": "read_inventory",
        "description": "读取在售商品库（XLSX/CSV 自动识别）",
        "parameters": {
            "file_path": {"type": "string", "description": "文件路径"},
        },
    },
    {
        "name": "standardize_keys",
        "description": "自动识别数据源并生成标准化 match_key",
        "parameters": {
            "data": {"type": "array", "items": {"type": "object"}},
            "key_hint": {"type": "string", "description": "手动指定键列名"},
            "source_label": {"type": "string", "default": "unknown"},
        },
    },
    {
        "name": "find_gaps",
        "description": "左反连接找出选品清单中有、在售清单中没有的商品",
        "parameters": {
            "source_data": {"type": "array", "items": {"type": "object"}},
            "target_data": {"type": "array", "items": {"type": "object"}},
            "match_key": {"type": "string", "default": "match_key"},
        },
    },
    {
        "name": "fuzzy_verify",
        "description": "基于标题+品牌的模糊匹配二次校验",
        "parameters": {
            "suspect_data": {"type": "array", "items": {"type": "object"}},
            "target_data": {"type": "array", "items": {"type": "object"}},
            "threshold": {"type": "integer", "default": 55},
        },
    },
    {
        "name": "export_report",
        "description": "导出缺品 Excel（明细+多维度统计+潜匹配表）",
        "parameters": {
            "gap_data": {"type": "array", "items": {"type": "object"}},
            "output_folder": {"type": "string"},
            "file_prefix": {"type": "string", "default": "缺口分析报告"},
        },
    },
    {
        "name": "run_pipeline",
        "description": "一站式运行缺口分析全流程（6步流水线）",
        "parameters": {
            "listing_folder": {"type": "string"},
            "inventory_file": {"type": "string"},
            "output_folder": {"type": "string", "default": ""},
            "fuzzy": {"type": "boolean", "default": False},
            "fuzzy_threshold": {"type": "integer", "default": 55},
        },
    },
]

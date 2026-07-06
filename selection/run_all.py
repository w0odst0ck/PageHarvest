#!/usr/bin/env python3
"""
选品 → 缺口 全流程自动化 (Picker → Gap Analyzer)
====================================================

一键完成从 HTML 选品分析到在售商品缺品比对的完整闭环。

用法:
  # 全品类选品 + 自动缺口比对
  python -m selection.run_all --all --compare

  # 全品类选品 + 带模糊匹配的缺口比对
  python -m selection.run_all --all --compare --fuzzy

  # 指定品类选品 + 缺口比对
  python -m selection.run_all --name 室内灯具 --html-dir data/ZKH/分析-室内灯具 --compare

  # 仅做缺口比对（跳过选品阶段）
  python -m selection.run_all --compare-only --inventory 河姆渡-all-20260704.xlsx

  # 详细日志
  python -m selection.run_all --all --compare --fuzzy --verbose

流程:
  Phase 1 [Picker] : 可选 — 解析 HTML → CSV 选品清单（复用 zkh-picker.py）
  Phase 2 [Gap]    : 全自动 — 选品清单 vs 在售商品 → 缺品 Excel 报告
"""

import argparse
import logging
import os
import sys
import subprocess
from pathlib import Path

# ── 项目根目录探测 ────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent  # selection/ → project root
sys.path.insert(0, str(PROJECT_ROOT))

from selection.auto_pick import summarize_selection, print_summary

logger = logging.getLogger("run_all")


# ═══════════════════════════════════════════════════════════════════
#  Phase 1: 选品分析 (复用 zkh-picker.py)
# ═══════════════════════════════════════════════════════════════════

def run_picker(
    all_categories: bool = False,
    name: str = "",
    html_dir: str = "",
    output_dir: str = "",
    verbose: bool = False,
) -> str:
    """调用 zkh-picker.py 执行选品分析，返回输出目录。

    通过 subprocess 调用，保证 CLI 行为一致、互不污染。
    """
    picker_script = str(_THIS_DIR / "zkh-picker.py")

    cmd = [sys.executable, picker_script]
    if all_categories:
        cmd.append("--all")
    elif name and html_dir:
        cmd.extend([html_dir, "--name", name])
    else:
        raise ValueError("必须指定 --all 或 --name + --html-dir")

    if output_dir:
        cmd.extend(["--output", output_dir])
    if verbose:
        cmd.append("--verbose")

    logger.info("─" * 55)
    logger.info("  Phase 1: 选品分析器 (Picker)")
    logger.info("─" * 55)

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")

    if result.returncode != 0:
        raise RuntimeError(f"选品分析失败 (exit={result.returncode})")

    # 从 zkh-picker.py 的默认输出逻辑推断 output_dir
    if output_dir:
        return output_dir

    # 默认路径: data/ZKH/震坤行/上架清单
    default = str(PROJECT_ROOT / "data" / "ZKH" / "震坤行" / "上架清单")
    if os.path.isdir(default):
        return default

    # 兜底：从项目根找
    data_dir = PROJECT_ROOT / "data"
    if data_dir.is_dir():
        for zkh_dir in data_dir.rglob("上架清单"):
            if zkh_dir.is_dir():
                return str(zkh_dir)

    return default


# ═══════════════════════════════════════════════════════════════════
#  Phase 2: 缺口比对 (gap/ analyzer)
# ═══════════════════════════════════════════════════════════════════

def run_gap(
    listing_folder: str,
    inventory_file: str = "",
    output_folder: str = "",
    fuzzy: bool = False,
    fuzzy_threshold: int = 55,
    verbose: bool = False,
) -> dict:
    """以模块化方式调用 gap/analyzer 执行缺口比对。

    直接 import gap.analyzer 而非 subprocess，获取结果对象方便 downstream。
    """
    from gap.analyzer import run_pipeline

    logger.info("─" * 55)
    logger.info("  Phase 2: 商品缺口分析 (Gap Analyzer)")
    logger.info("─" * 55)

    result = run_pipeline(
        listing_folder=listing_folder,
        inventory_file=inventory_file,
        output_folder=output_folder,
        fuzzy=fuzzy,
        fuzzy_threshold=fuzzy_threshold,
        verbose=verbose,
    )
    return result


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="选品 → 缺口 全流程自动化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m selection.run_all --all --compare
  python -m selection.run_all --all --compare --fuzzy
  python -m selection.run_all --name 室内灯具 --html-dir data/ZKH/分析-室内灯具 --compare
  python -m selection.run_all --compare-only --inventory 河姆渡-all-20260704.xlsx
        """,
    )

    # ── Phase 1 参数 ──
    p1 = parser.add_argument_group("Phase 1 — 选品分析 (Picker)")
    p1.add_argument("--all", "-a", action="store_true",
                    help="批量选品 data/ZKH/分析-* 所有品类")
    p1.add_argument("--name", "-n",
                    help="品类名称（配合 --html-dir）")
    p1.add_argument("--html-dir",
                    help="HTML 文件目录（配合 --name）")
    p1.add_argument("--picker-output",
                    help="选品输出目录（默认: data/ZKH/震坤行/上架清单）")

    # ── Phase 2 参数 ──
    p2 = parser.add_argument_group("Phase 2 — 缺口比对 (Gap)")
    p2.add_argument("--compare", action="store_true",
                    help="选品完成后自动执行缺口比对")
    p2.add_argument("--compare-only", action="store_true",
                    help="仅执行缺口比对（跳过选品）")
    p2.add_argument("--inventory", "-i",
                    default="",
                    help="在售商品文件路径（默认: 自动发现 河姆渡-all-*.xlsx）")
    p2.add_argument("--fuzzy", "-f", action="store_true",
                    help="启用模糊匹配（需 pip install rapidfuzz）")
    p2.add_argument("--fuzzy-threshold", type=int, default=55,
                    help="模糊匹配阈值 (0-100，默认 55)")
    p2.add_argument("--gap-output",
                    help="缺口报告输出目录（默认: 选品清单目录）")

    # ── 全局 ──
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="详细日志")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    # ── 日志 ──
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")
    logging.getLogger("gap.analyzer").setLevel(level)

    # ── 校验参数 ──
    has_p1 = args.all or (args.name and args.html_dir)
    has_p2 = args.compare or args.compare_only

    if not has_p1 and not has_p2:
        parser.print_help()
        print("\n❌ 请至少指定选品参数 (--all 或 --name) 或缺口比对参数 (--compare / --compare-only)")
        sys.exit(1)

    if args.compare_only and has_p1:
        print("⚠  --compare-only 与选品参数互斥，忽略选品参数")

    # ── 本期执行计划 ──
    if has_p1 and not args.compare_only:
        print("═" * 55)
        print("  PageHarvest — 选品 → 缺口 全流程")
        print("═" * 55)
        print()
        print(f"  Phase 1: 选品分析     {'✓' if has_p1 else '—'}")
        print(f"  Phase 2: 缺口比对     {'✓' if has_p2 else '—'}")
        print(f"  模糊匹配: {'✓ (阈值: ' + str(args.fuzzy_threshold) + ')' if args.fuzzy else '—'}")
        print()

    # ════════════════════════════════════════════════════════════
    #  Phase 1: 选品
    # ════════════════════════════════════════════════════════════
    listing_dir = ""
    picker_summary = None

    if has_p1 and not args.compare_only:
        try:
            listing_dir = run_picker(
                all_categories=args.all,
                name=args.name or "",
                html_dir=args.html_dir or "",
                output_dir=args.picker_output or "",
                verbose=args.verbose,
            )
        except (ValueError, RuntimeError, FileNotFoundError) as e:
            print(f"\n❌ Phase 1 选品失败: {e}")
            sys.exit(1)

        # 汇总统计
        try:
            picker_summary = summarize_selection(listing_dir)
            print()
            print_summary(picker_summary)
            print()
        except Exception as e:
            logger.warning("  选品汇总失败: %s", e)
    else:
        # --compare-only: listing_dir 需另行指定
        if args.compare_only:
            listing_dir = args.picker_output or ""
            if not listing_dir:
                # 自动找
                default = str(PROJECT_ROOT / "data" / "ZKH" / "震坤行" / "上架清单")
                if os.path.isdir(default):
                    listing_dir = default
                else:
                    print("❌ --compare-only 需要现有选品清单。请指定:")
                    print("   python -m selection.run_all --compare-only --picker-output /path/to/选品清单")
                    sys.exit(1)
            picker_summary = summarize_selection(listing_dir)

    # ════════════════════════════════════════════════════════════
    #  Phase 2: 缺口比对
    # ════════════════════════════════════════════════════════════
    if has_p2:
        # 确认 listing 目录存在且非空
        if not listing_dir or not os.path.isdir(listing_dir):
            print(f"❌ 选品清单目录不存在: {listing_dir}")
            sys.exit(1)

        inventory = args.inventory or ""
        # 如果未指定 —inventory, 尝试自动发现
        if not inventory:
            from gap.config import GapConfig
            cfg = GapConfig(data_dir=str(PROJECT_ROOT / "data"))
            inventory = cfg.resolve_inventory_file()
            if inventory:
                logger.info("  自动发现: 在售商品 → %s", inventory)

        gap_output = args.gap_output or listing_dir

        try:
            gap_result = run_gap(
                listing_folder=listing_dir,
                inventory_file=inventory,
                output_folder=gap_output,
                fuzzy=args.fuzzy,
                fuzzy_threshold=args.fuzzy_threshold,
                verbose=args.verbose,
            )
        except (FileNotFoundError, ValueError) as e:
            print(f"\n❌ Phase 2 缺口分析失败: {e}")
            if not args.inventory:
                print("   提示: 可通过 --inventory 指定在售商品文件路径")
            sys.exit(1)

        # ── 最终报告 ──
        print()
        print("─" * 55)
        print("  全流程完成")
        print("─" * 55)
        print(gap_result.get("summary", ""))

    elif has_p1:
        print("\n✅ 选品分析完成。添加 --compare 自动执行缺口比对。")

    print()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
选品 → 缺口 全流程自动化 (Picker → Gap Analyzer)
====================================================

一键完成从数据解析到在售商品缺品比对的完整闭环。

支持平台:
  - ZKH: 从搜索页 HTML 解析 → 选品分析 → 缺口比对
  - JD:  从搜索 CSV 解析 → 选品分析 → 缺口比对

用法:
  # 震坤行
  python -m selection.run_all --platform zkh --all --compare
  python -m selection.run_all --platform zkh --name 室内灯具 --html-dir data/ZKH/分析-室内灯具

  # 京东
  python -m selection.run_all --platform jd --csv data/JD/京东-灯具-搜索结果.csv --name 灯具
  python -m selection.run_all --platform jd --csv data/JD/京东-灯具-搜索结果.csv --name 灯具 --compare --inventory 河姆渡-all.xlsx

  # 仅缺口比对
  python -m selection.run_all --compare-only --inventory 河姆渡-all.xlsx

流程:
  Phase 1 [Picker] : 平台相关 — 解析搜索数据 → 分级选品清单
  Phase 2 [Gap]    : 全自动    — 选品清单 vs 在售商品 → 缺品报告
"""

import argparse
import logging
import os
import sys
import subprocess
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

from selection.auto_pick import summarize_selection, print_summary

logger = logging.getLogger("run_all")


# ═══════════════════════════════════════════════════════════════════
#  Phase 1: 选品分析 (平台相关路由)
# ═══════════════════════════════════════════════════════════════════

def run_picker(platform, all_categories, name, html_dir, csv_file, output_dir, verbose, data_dir="", from_html=False):
    """根据平台选择对应的选品分析器。"""
    logger.info("─" * 55)
    logger.info("  Phase 1: 选品分析器 (%s)", platform)
    logger.info("─" * 55)

    if platform == "jd":
        return _run_jd_picker(name, csv_file, output_dir, verbose)
    if platform == "1688":
        return _run_1688_picker(name, data_dir, from_html, output_dir, verbose)
    return _run_zkh_picker(all_categories, name, html_dir, output_dir, verbose)


def _run_zkh_picker(all_categories, name, html_dir, output_dir, verbose):
    """震坤行选品：调用 zkh-picker.py"""
    script = str(_THIS_DIR / "zkh-picker.py")
    cmd = [sys.executable, script]
    if all_categories:
        cmd.append("--all")
    elif name and html_dir:
        cmd.extend([html_dir, "--name", name])
    else:
        raise ValueError("ZKH: 需指定 --all 或 --name + --html-dir")
    if output_dir:
        cmd.extend(["--output", output_dir])
    if verbose:
        cmd.append("--verbose")

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode != 0:
        raise RuntimeError(f"震坤行选品失败 (exit={result.returncode})")

    if output_dir:
        return output_dir
    default = str(PROJECT_ROOT / "data" / "ZKH" / "震坤行" / "上架清单")
    return default if os.path.isdir(default) else default


def _run_jd_picker(name, csv_file, output_dir, verbose):
    """京东选品：调用 jd-picker.py"""
    if not name:
        raise ValueError("JD: 需指定 --name（品类名称）")
    if not csv_file:
        raise ValueError("JD: 需指定 --csv（搜索结果 CSV）")

    script = str(_THIS_DIR / "jd-picker.py")
    cmd = [sys.executable, script, csv_file, "--name", name]
    if output_dir:
        cmd.extend(["--output", output_dir])
    if verbose:
        cmd.append("--verbose")

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode != 0:
        raise RuntimeError(f"京东选品失败 (exit={result.returncode})")

    return output_dir or str(PROJECT_ROOT / "output" / "JD")


def _run_1688_picker(name, data_dir, from_html, output_dir, verbose):
    """1688 选品：调用 1688-picker.py"""
    if not name:
        raise ValueError("1688: 需指定 --name")
    if not data_dir:
        raise ValueError("1688: 需指定 --data-dir（插件 XLSX 或 HTML 目录）")

    script = str(_THIS_DIR / "1688-picker.py")
    cmd = [sys.executable, script, data_dir, "--name", name]
    if from_html:
        cmd.append("--from-html")
    if output_dir:
        cmd.extend(["--output", output_dir])
    if verbose:
        cmd.append("--verbose")

    result = subprocess.run(cmd, capture_output=True, text=True)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    if result.returncode != 0:
        raise RuntimeError(f"1688 选品失败 (exit={result.returncode})")
    return output_dir or str(PROJECT_ROOT / "output" / "1688")


# ═══════════════════════════════════════════════════════════════════
#  Phase 2: 缺口比对 (gap/ analyzer)
# ═══════════════════════════════════════════════════════════════════

def run_gap(listing_folder, inventory_file, output_folder, fuzzy, fuzzy_threshold, verbose):
    """调用 gap/analyzer 执行缺口比对。"""
    from gap.analyzer import run_pipeline
    logger.info("─" * 55)
    logger.info("  Phase 2: 商品缺口分析 (Gap Analyzer)")
    logger.info("─" * 55)
    return run_pipeline(
        listing_folder=listing_folder,
        inventory_file=inventory_file,
        output_folder=output_folder,
        fuzzy=fuzzy,
        fuzzy_threshold=fuzzy_threshold,
        verbose=verbose,
    )


# ═══════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════

def build_parser():
    parser = argparse.ArgumentParser(
        description="选品 → 缺口 全流程自动化",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m selection.run_all --platform zkh --all --compare
  python -m selection.run_all --platform jd --csv data/JD/京东-灯具-搜索结果.csv --name 灯具
  python -m selection.run_all --compare-only --inventory 河姆渡-all.xlsx
        """,
    )
    parser.add_argument("--platform", choices=["zkh", "jd", "1688"], default="zkh",
                        help="目标平台 (默认: zkh)")

    p1 = parser.add_argument_group("Phase 1 — 选品分析")
    p1.add_argument("--all", "-a", action="store_true",
                    help="[ZKH] 批量分析 data/ZKH/分析-* 品类")
    p1.add_argument("--name", "-n", help="品类名称")
    p1.add_argument("--html-dir", help="[ZKH] HTML 搜索页目录")
    p1.add_argument("--csv", help="[JD] 搜索结果 CSV 路径")
    p1.add_argument("--data-dir", help="[1688] 插件 XLSX 目录（默认优先 XLSX，加 --from-html 走 HTML）")
    p1.add_argument("--from-html", action="store_true", help="[1688] 从 HTML 解析（备用）")
    p1.add_argument("--picker-output", help="选品清单输出目录")

    p2 = parser.add_argument_group("Phase 2 — 缺口比对")
    p2.add_argument("--compare", action="store_true", help="选品后自动缺口比对")
    p2.add_argument("--compare-only", action="store_true", help="仅缺口比对")
    p2.add_argument("--inventory", "-i", default="", help="在售商品文件路径")
    p2.add_argument("--fuzzy", "-f", action="store_true", help="启用模糊匹配")
    p2.add_argument("--fuzzy-threshold", type=int, default=55, help="模糊匹配阈值")
    p2.add_argument("--gap-output", help="缺口报告输出目录")

    parser.add_argument("--verbose", "-v", action="store_true", help="详细日志")
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")
    logging.getLogger("gap.analyzer").setLevel(level)

    platform = args.platform
    if platform == "zkh":
        has_p1 = args.all or (args.name and args.html_dir)
    elif platform == "jd":
        has_p1 = bool(args.name and args.csv)
    elif platform == "1688":
        has_p1 = bool(args.name and args.data_dir)
    else:
        has_p1 = False
    has_p2 = args.compare or args.compare_only

    if not has_p1 and not has_p2:
        parser.print_help()
        print("\n❌ 请指定选品参数或缺口比对参数")
        sys.exit(1)

    if args.compare_only and has_p1:
        print("⚠  --compare-only 与选品参数互斥，忽略选品")

    # ── 执行计划 ──
    if has_p1 and not args.compare_only:
        print("═" * 55)
        print("  PageHarvest — 选品 → 缺口 全流程")
        print("═" * 55)
        print(f"  平台:       {platform}")
        print(f"  Phase 1:    {'✓' if has_p1 else '—'}")
        print(f"  Phase 2:    {'✓' if has_p2 else '—'}")
        print()

    # ════════════════════════════════════════════════════════════
    #  Phase 1: 选品
    # ════════════════════════════════════════════════════════════
    listing_dir = ""
    if has_p1 and not args.compare_only:
        try:
            listing_dir = run_picker(
                platform=platform,
                all_categories=args.all,
                name=args.name or "",
                html_dir=args.html_dir or "",
                csv_file=args.csv or "",
                output_dir=args.picker_output or "",
                verbose=args.verbose,
                data_dir=args.data_dir or "",
                from_html=args.from_html,
            )
        except (ValueError, RuntimeError, FileNotFoundError) as e:
            print(f"\n❌ Phase 1 选品失败: {e}")
            sys.exit(1)

        try:
            s = summarize_selection(listing_dir)
            if s:
                print()
                print_summary(s)
                print()
        except Exception as e:
            logger.warning("  汇总失败: %s", e)

    elif args.compare_only:
        listing_dir = args.picker_output or ""
        if not listing_dir:
            candidates = [
                str(PROJECT_ROOT / "data" / "ZKH" / "震坤行" / "上架清单"),
                str(PROJECT_ROOT / "output" / "JD"),
            ]
            for c in candidates:
                if os.path.isdir(c):
                    listing_dir = c
                    break
        if not listing_dir:
            print("❌ 需指定已有选品清单: --picker-output /path/to/清单")
            sys.exit(1)

    # ════════════════════════════════════════════════════════════
    #  Phase 2: 缺口比对
    # ════════════════════════════════════════════════════════════
    if has_p2:
        if not listing_dir or not os.path.isdir(listing_dir):
            print(f"❌ 选品清单目录不存在: {listing_dir}")
            sys.exit(1)

        inventory = args.inventory or ""
        if not inventory:
            from gap.config import GapConfig
            cfg = GapConfig(data_dir=str(PROJECT_ROOT / "data"))
            inventory = cfg.resolve_inventory_file()
            if inventory:
                logger.info("  自动发现: 在售商品 → %s", inventory)

        try:
            r = run_gap(
                listing_folder=listing_dir,
                inventory_file=inventory,
                output_folder=args.gap_output or listing_dir,
                fuzzy=args.fuzzy,
                fuzzy_threshold=args.fuzzy_threshold,
                verbose=args.verbose,
            )
        except (FileNotFoundError, ValueError) as e:
            print(f"\n❌ Phase 2 缺口分析失败: {e}")
            if not args.inventory:
                print("   提示: --inventory 指定在售商品文件")
            sys.exit(1)

        print("\n" + "─" * 55)
        print("  全流程完成")
        print("─" * 55)
        print(r.get("summary", ""))

    elif has_p1:
        print("\n✅ 选品分析完成。添加 --compare 执行缺口比对。")
    print()


if __name__ == "__main__":
    main()

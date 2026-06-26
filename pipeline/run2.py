"""
第二阶段：精选商品详情页深度采集（一键运行）
步骤: 05_manual_urls → 06_detail_collector → 07_process_with_1688lib

用法:
    .venv\Scripts\python.exe pipeline\run2.py --cat 投光灯
"""
import os, sys, subprocess, time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CATEGORY = None
SKIP_URLS = False
for i, a in enumerate(sys.argv[1:], 1):
    if a == '--cat' and i < len(sys.argv):
        CATEGORY = sys.argv[i + 1]
    if a == '--skip-urls':
        SKIP_URLS = True

SCRIPT_DIR = os.path.join(PROJECT_DIR, "pipeline")

def run_step(name, script, *args):
    print(f"\n{'='*50}")
    print(f"  [{name}] {script}")
    print(f"{'='*50}")
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script)]
    if args:
        cmd.extend(args)
    start = time.time()
    result = subprocess.run(cmd, cwd=PROJECT_DIR)
    elapsed = time.time() - start
    if result.returncode == 0:
        print(f"  ✓ {elapsed:.0f}s")
    else:
        print(f"  ✗ exit={result.returncode}")
        sys.exit(result.returncode)

def main():
    label = CATEGORY or '全部品类'
    print(f"\n{'='*50}")
    print(f"  详情页管线 — {label}")
    print(f"{'='*50}")

    cat_args = ['--cat', CATEGORY] if CATEGORY else []

    if not SKIP_URLS:
        run_step("手动录入详情页URL", "05_manual_urls.py", *cat_args)

    run_step("下载详情页 + 1688库解析", "06_detail_collector.py", *cat_args)
    run_step("1688库全流程资源下载", "07_process_with_1688lib.py", *cat_args)

    base_dir = os.path.join(PROJECT_DIR, "data", CATEGORY, "products_detail") if CATEGORY else ""
    csv_path = os.path.join(PROJECT_DIR, "data", CATEGORY, "top_products_details.csv") if CATEGORY else ""

    print(f"\n{'='*50}")
    print(f"  输出")
    print(f"{'='*50}")
    if os.path.exists(csv_path):
        print(f"  ✓ 汇总: {csv_path}  ({os.path.getsize(csv_path):,} bytes)")
    if base_dir and os.path.exists(base_dir):
        dirs = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        print(f"  ✓ 详情页: {len(dirs)} 个商品")
        for d in dirs:
            print(f"      {d}/")
    print(f"\n  ✅ 完成")

if __name__ == '__main__':
    main()

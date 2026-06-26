"""
第一阶段：搜索页数据采集、清洗、分析（一键运行）
步骤: 02_parse → 03_clean → 04_analyze

用法:
    .venv\Scripts\python.exe pipeline\run1.py --cat 投光灯
"""
import os, sys, subprocess, time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CATEGORY = None
for i, a in enumerate(sys.argv[1:], 1):
    if a == '--cat' and i < len(sys.argv):
        CATEGORY = sys.argv[i + 1]

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
    print(f"  搜索页管线 — {label}")
    print(f"{'='*50}")

    cat_args = ['--cat', CATEGORY] if CATEGORY else []
    run_step("解析 HTML→CSV", "02_parse.py", *cat_args)
    run_step("数据清洗", "03_clean.py", *cat_args)
    run_step("数据分析", "04_analyze.py", *cat_args)

    data_dir = os.path.join(PROJECT_DIR, "data", CATEGORY) if CATEGORY else os.path.join(PROJECT_DIR, "data")
    print(f"\n{'='*50}")
    print(f"  输出: {data_dir}")
    print(f"{'='*50}")
    for f in ['all_products.csv', 'cleaned_products.csv', 'analysis_report.txt', 'analysis_chart.png']:
        path = os.path.join(data_dir, f)
        if os.path.exists(path):
            print(f"  ✓ {f}  ({os.path.getsize(path):,} bytes)")
        else:
            print(f"  ✗ {f}")
    print(f"\n  ✅ 完成")

if __name__ == '__main__':
    main()

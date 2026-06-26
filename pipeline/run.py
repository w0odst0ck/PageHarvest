"""
一键运行全流程管道
用法:
    python pipeline\run.py                    # 运行全部品类
    python pipeline\run.py --cat 投光灯        # 运行指定品类
    python pipeline\run.py --cat 户外灯具       # 运行指定品类
    python pipeline\run.py --skip-parse        # 跳过解析（已有CSV时加速）
"""

import os, sys, subprocess, time

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 解析参数
CATEGORY = None
SKIP_PARSE = False
for i, a in enumerate(sys.argv[1:], 1):
    if a == '--cat' and i < len(sys.argv):
        CATEGORY = sys.argv[i + 1]
    if a == '--skip-parse':
        SKIP_PARSE = True

SCRIPT_DIR = os.path.join(PROJECT_DIR, "pipeline")

def run_step(name, script, *args):
    print("\n" + "=" * 50)
    print(f"  [{name}] {script}")
    print("=" * 50)
    
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, script)]
    if args:
        cmd.extend(args)
    
    start = time.time()
    result = subprocess.run(cmd, cwd=PROJECT_DIR)
    elapsed = time.time() - start
    
    if result.returncode == 0:
        print(f"  ✓ {name} 完成 ({elapsed:.1f}s)")
    else:
        print(f"  ✗ {name} 失败 (exit code {result.returncode})")
        sys.exit(result.returncode)


def main():
    print("=" * 50)
    print("  1688 商品数据采集管道")
    print(f"  品类: {CATEGORY or '全部'}")
    if SKIP_PARSE:
        print("  跳过: 解析(02)")
    print("=" * 50)

    cat_args = ['--cat', CATEGORY] if CATEGORY else []

    if not SKIP_PARSE:
        run_step("01 解析 HTML→CSV", "02_parse.py", *cat_args)

    run_step("02 数据清洗", "03_clean.py", *cat_args)
    run_step("03 数据分析", "04_analyze.py", *cat_args)

    # 显示结果文件
    data_dir = os.path.join(PROJECT_DIR, "data", CATEGORY) if CATEGORY else os.path.join(PROJECT_DIR, "data")
    print("\n" + "=" * 50)
    print("  📁 输出目录: " + data_dir)
    print("=" * 50)
    for f in ['all_products.csv', 'cleaned_products.csv', 'analysis_report.txt', 'analysis_chart.png']:
        path = os.path.join(data_dir, f)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  ✓ {f}  ({size:,} bytes)")
        else:
            print(f"  ✗ {f}  (未生成)")
    
    print("\n  ✅ 全部完成")


if __name__ == "__main__":
    main()

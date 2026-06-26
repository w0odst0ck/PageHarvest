"""
将 pipeline 采集的详情页 HTML 交给 1688库处理（下载图片、视频等）
"""
import os
import sys
import time
import subprocess

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB_DIR = os.path.join(PROJECT_DIR, '1688', '1688')  # 1688库目录


def main():
    import argparse
    parser = argparse.ArgumentParser(description='将详情页HTML交给1688库处理')
    parser.add_argument('--cat', default='投光灯')
    args = parser.parse_args()

    # 查找所有已采集的HTML
    detail_dir = os.path.join(PROJECT_DIR, "data", args.cat, "products_detail")
    if not os.path.exists(detail_dir):
        print(f"错误: 未找到 {detail_dir}")
        return

    html_files = []
    for root, dirs, files in os.walk(detail_dir):
        for f in files:
            if f.endswith('.html'):
                html_files.append(os.path.abspath(os.path.join(root, f)))

    if not html_files:
        print(f"未找到HTML文件")
        return

    print(f"\n找到 {len(html_files)} 个详情页HTML")
    for f in html_files:
        print(f"  {os.path.basename(os.path.dirname(f))}/{os.path.basename(f)}")
    print()

    # 处理每个HTML
    for i, html_path in enumerate(html_files, 1):
        oid = os.path.basename(os.path.dirname(html_path))
        print(f"[{i}/{len(html_files)}] {oid}")

        # 创建输出目录（在1688库目录里）
        out_dir = os.path.join(LIB_DIR, oid)
        os.makedirs(out_dir, exist_ok=True)

        # 进入输出目录，运行 main.py
        cmd = [
            sys.executable,
            os.path.join(LIB_DIR, 'main.py'),
            html_path,
            '--no-rebuild',  # 不需要重建脚本
        ]

        print(f"  运行: python main.py {oid}.html")
        start = time.time()

        result = subprocess.run(
            cmd,
            cwd=out_dir,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
        )

        elapsed = time.time() - start
        if result.returncode == 0:
            print(f"  ✅ 完成 ({elapsed:.0f}s)")
        else:
            print(f"  ⚠ 可能有问题 (exit={result.returncode}, {elapsed:.0f}s)")
            # 只打印最后几行日志
            last_lines = [l for l in result.stdout.split('\n') if l.strip()][-3:]
            for line in last_lines:
                print(f"    {line.strip()}")

        print()

    print(f"{'='*60}")
    print("全部处理完成")
    print(f"{'='*60}")
    print(f"输出目录: {LIB_DIR}\\")
    for html_path in html_files:
        oid = os.path.basename(os.path.dirname(html_path))
        print(f"  {oid}\\  ← 图片/视频/属性等")
    print(f"\n也可以直接打开 1688 库的 GUI 查看:")
    print(f"  cd {LIB_DIR} && .venv\\Scripts\\python.exe main.py --gui")


if __name__ == '__main__':
    main()

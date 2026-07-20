"""
统一命令行入口

用法:
    # 搜索页
    python run.py search --platform 1688 --keyword 投光灯 --pages 34
    python run.py search --platform 京东 --keyword 投光灯 --html-dir data/京东/

    # 详情页
    python run.py detail --platform 1688 --keyword 投光灯 --product-ids 732462521472

    # 跨平台对比
    python run.py compare --keyword 投光灯 --platforms 1688,京东

    # 查看可用平台
    python run.py list

说明:
    原有 1688 管线脚本 (run1.py / run2.py) 仍然保留，不受影响。
    新框架通过统一的 run.py 入口调度。
"""

import os, sys, argparse

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
sys.path.insert(0, PROJECT_DIR)


def cmd_search(args):
    """搜索页管线"""
    from core.pipeline import SearchPipeline

    pipeline = SearchPipeline(args.platform, DATA_DIR)

    # 如果指定了 html-dir，读取本地文件；否则在线采集
    if args.html_dir:
        html_dir = args.html_dir
        if not os.path.isabs(html_dir):
            html_dir = os.path.join(PROJECT_DIR, html_dir)
        if not os.path.isdir(html_dir):
            print(f"错误: HTML 目录不存在: {html_dir}")
            sys.exit(1)
        pipeline.run(args.keyword, html_dir=html_dir)
    else:
        pages = args.pages or 1
        pipeline.run(args.keyword, pages=pages)


def cmd_detail(args):
    """详情页管线"""
    from core.pipeline import DetailPipeline

    pipeline = DetailPipeline(args.platform, DATA_DIR)

    ids = []
    if args.product_ids:
        ids.extend(args.product_ids.split(','))

    if args.urls_file:
        with open(args.urls_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    ids.append(line)

    pipeline.run(args.keyword, product_ids=ids)


def cmd_compare(args):
    """跨平台对比"""
    from core.pipeline import CrossPlatformPipeline

    platforms = [p.strip() for p in args.platforms.split(',')]
    pipeline = CrossPlatformPipeline(DATA_DIR)
    pipeline.run(args.keyword, platforms, pages=args.pages or 1)


def cmd_list(args):
    """列出可用平台"""
    from core.registry import list_platforms

    platforms = list_platforms()
    print("已注册的电商平台:")
    for p in platforms:
        print(f"  • {p}")
    print(f"\n共 {len(platforms)} 个平台")
    print("\n提示: 如需新增平台，在 platforms/ 下创建适配器并注册即可。")


def cmd_merge(args):
    """手动触发跨平台合并"""
    from core.merge import merge_csv_by_keyword

    platforms = [p.strip() for p in args.platforms.split(',')]
    output = merge_csv_by_keyword(DATA_DIR, args.keyword, platforms,
                                  output=args.output)
    if output:
        print(f"合并完成: {output}")


def main():
    parser = argparse.ArgumentParser(
        description="多平台电商数据采集框架",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py search --platform 1688 --keyword 投光灯 --pages 34
  python run.py search --platform 京东 --keyword 投光灯 --html-dir data/京东/
  python run.py compare --keyword 投光灯 --platforms 1688,京东
  python run.py list
        """,
    )
    sub = parser.add_subparsers(dest='command', help='子命令')

    # ── search ──
    p_search = sub.add_parser('search', help='执行搜索页管线')
    p_search.add_argument('--platform', required=True, help='平台名称')
    p_search.add_argument('--keyword', required=True, help='搜索关键词')
    p_search.add_argument('--pages', type=int, default=0, help='采集页数')
    p_search.add_argument('--html-dir', help='本地 HTML 目录路径（如已有保存的 HTML 文件）')

    # ── detail ──
    p_detail = sub.add_parser('detail', help='执行详情页管线')
    p_detail.add_argument('--platform', required=True, help='平台名称')
    p_detail.add_argument('--keyword', required=True, help='品类名')
    p_detail.add_argument('--product-ids', help='商品 ID 列表（逗号分隔）')
    p_detail.add_argument('--urls-file', help='URL 列表文件（每行一个）')

    # ── compare ──
    p_compare = sub.add_parser('compare', help='跨平台对比')
    p_compare.add_argument('--keyword', required=True, help='搜索关键词')
    p_compare.add_argument('--platforms', required=True, help='平台列表（逗号分隔，如 1688,京东）')
    p_compare.add_argument('--pages', type=int, default=1, help='每平台采集页数')

    # ── merge ──
    p_merge = sub.add_parser('merge', help='合并已有CSV')
    p_merge.add_argument('--keyword', required=True, help='品类名')
    p_merge.add_argument('--platforms', required=True, help='平台列表（逗号分隔）')
    p_merge.add_argument('--output', help='输出文件路径')

    # ── list ──
    sub.add_parser('list', help='列出已注册的平台')

    args = parser.parse_args()

    # 注册所有平台适配器
    # (import 触发 @register 装饰器)
    for mod_name in ['platforms.alibaba.adapter', 'platforms.jingdong.adapter']:
        try:
            __import__(mod_name)
        except ImportError as e:
            print(f"  跳过 {mod_name}: {e}")

    commands = {
        'search': cmd_search,
        'detail': cmd_detail,
        'compare': cmd_compare,
        'list': cmd_list,
        'merge': cmd_merge,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()

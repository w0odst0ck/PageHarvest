"""price-compare 入口调度器"""

import os
import sys
import importlib

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import config as global_config
from core.loader import load
from core.exporter import export
from core.logger import get_logger
from core import utils
from platforms import get_active


def main():
    log = get_logger(
        level=global_config.LOG_LEVEL,
        log_file=os.path.join(global_config.OUTPUT_DIR, 'run_log.txt'),
    )

    log.info("MAIN", "=" * 50)
    log.info("MAIN", "price-compare 启动")
    log.info("MAIN", f"输入: {global_config.INPUT_FILE}")
    log.info("MAIN", f"DRY_RUN: {global_config.DRY_RUN}")

    # 1. 加载商品
    input_path = os.path.join(PROJECT_ROOT, global_config.INPUT_FILE)
    if not os.path.exists(input_path):
        log.error("MAIN", f"输入文件不存在: {input_path}")
        sys.exit(1)

    products = load(input_path)
    if not products:
        log.error("MAIN", "无商品数据，退出")
        sys.exit(1)

    log.info("MAIN", f"加载 {len(products)} 条商品")

    # 2. 获取活跃平台
    active_platforms = get_active()
    if not active_platforms:
        log.error("MAIN", "没有启用的平台，请检查 platforms/__init__.py")
        sys.exit(1)

    platform_names = [p['name'] for p in active_platforms]
    log.info("MAIN", f"活跃平台: {', '.join(platform_names)}")

    # 3. 依次运行各平台
    all_results = {}
    for pconf in active_platforms:
        pname = pconf['name']
        log.info("MAIN", f"--- 开始: {pname} ---")

        try:
            module = importlib.import_module(pconf['module_path'])
            result = module.run(products)
            all_results[pname] = result

            # 保存原始结果
            raw_path = os.path.join(PROJECT_ROOT, global_config.OUTPUT_DIR, 'raw', f'{pname}_results.json')
            utils.save_json(result, raw_path)

            matched = len(result.get('results', []))
            unmatched = len(result.get('unmatched', []))
            errors = len(result.get('errors', []))
            log.info("MAIN", f"{pname}: 匹配 {matched}, 未匹配 {unmatched}, 错误 {errors}")

        except Exception as e:
            log.error("MAIN", f"{pname} 运行失败: {e}")
            all_results[pname] = {
                'platform': pname,
                'results': [],
                'unmatched': [],
                'errors': [{'sku': '', 'reason': f'模块异常: {e}'}],
            }

    # 4. 输出比价表
    output_dir = os.path.join(PROJECT_ROOT, global_config.OUTPUT_DIR)
    export(products, all_results, output_dir)

    log.info("MAIN", "=" * 50)
    log.info("MAIN", "完成")
    log.info("MAIN", "=" * 50)


if __name__ == '__main__':
    main()

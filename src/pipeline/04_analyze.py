"""
04_analyze.py — 数据分析 + 可视化
输入: data/cleaned_products.csv
输出: data/analysis_*.txt (统计报告)
       data/analysis_chart.png (图表)
"""

import os, csv, sys
from collections import Counter, defaultdict

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 支持 --cat 参数指定品类
CATEGORY = None
for i, a in enumerate(sys.argv[1:], 1):
    if a == '--cat' and i < len(sys.argv):
        CATEGORY = sys.argv[i + 1]
        break

data_dir = os.path.join(PROJECT_DIR, "data", CATEGORY) if CATEGORY else os.path.join(PROJECT_DIR, "data")
INPUT = os.path.join(data_dir, "cleaned_products.csv")
OUTPUT_TXT = os.path.join(data_dir, "analysis_report.txt")
OUTPUT_PNG = os.path.join(data_dir, "analysis_chart.png")


def save_report(text, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(text)
    print("  报告已保存:", filepath)


def main():
    if not os.path.exists(INPUT):
        print("错误: 未找到 {}".format(INPUT))
        print("请先运行 03_clean.py")
        sys.exit(1)

    with open(INPUT, 'r', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))

    print("分析数据: {} 条商品\n".format(len(rows)))
    report_lines = []
    report_lines.append("=" * 55)
    report_lines.append("  1688 商品数据分析报告")
    report_lines.append("  数据源: {} (34页)".format(CATEGORY or "全部品类"))
    report_lines.append("  商品数: {} 条".format(len(rows)))
    report_lines.append("=" * 55)
    report_lines.append("")

    # ========== 1. 价格分析 ==========
    prices = []
    for r in rows:
        try:
            prices.append(float(r['price']))
        except:
            pass
    prices.sort()

    report_lines.append("【价格分布】")
    report_lines.append("  最低价:    ¥{:.2f}".format(prices[0]))
    report_lines.append("  最高价:    ¥{:.2f}".format(prices[-1]))
    report_lines.append("  中位数:    ¥{:.2f}".format(prices[len(prices)//2]))
    report_lines.append("  平均价:    ¥{:.2f}".format(sum(prices)/len(prices)))

    # 价格区间
    ranges = [(0, 20), (20, 50), (50, 100), (100, 200), (200, 500), (500, 2000), (2000, 999999)]
    report_lines.append("\n  价格区间分布:")
    for lo, hi in ranges:
        count = sum(1 for p in prices if lo <= p < hi)
        pct = count / len(prices) * 100
        label = "¥{}~{}".format(lo, hi) if hi < 999999 else "¥{}以上".format(lo)
        bar = '█' * int(pct / 2)
        report_lines.append("    {:>12}: {:>4}条 ({:>4.0f}%) {}".format(label, count, pct, bar))

    # ========== 2. 供应商分析 ==========
    shop_counter = Counter(r['shop_name'] for r in rows if r['shop_name'])
    report_lines.append("\n【供应商分析】")
    report_lines.append("  供应商总数: {} 家".format(len(shop_counter)))
    report_lines.append("\n  头部供应商 (商品数):")
    for shop, count in shop_counter.most_common(10):
        cat = ''
        for r in rows:
            if r['shop_name'] == shop and r.get('category'):
                cat = r['category'].split('>')[-1].strip()[:20]
                break
        report_lines.append("    {:>4} 个 | {} {}".format(count, shop, '(' + cat + ')' if cat else ''))

    # ========== 3. 品类分析 ==========
    cat_counter = Counter()
    for r in rows:
        c = r.get('category', '').strip()
        if c:
            # 取最细分类
            parts = c.split('>')
            cat_counter[parts[-1].strip()] += 1

    report_lines.append("\n【品类分布】")
    for cat, count in cat_counter.most_common(15):
        pct = count / len(rows) * 100
        bar = '█' * int(pct / 2)
        report_lines.append("    {:>20}: {:>4}条 ({:>4.0f}%) {}".format(cat[:20], count, pct, bar))

    # ========== 4. 店铺时长分析 ==========
    age_counter = Counter()
    for r in rows:
        age = r.get('shop_age', '').strip()
        if age:
            m = re.search(r'(\d+)', str(age))
            if m:
                years = int(m.group(1))
                if years <= 1: age_counter['1年以内'] += 1
                elif years <= 3: age_counter['1-3年'] += 1
                elif years <= 5: age_counter['3-5年'] += 1
                else: age_counter['5年以上'] += 1

    if age_counter:
        report_lines.append("\n【店铺经营时长】")
        for age, count in age_counter.most_common():
            report_lines.append("    {}: {} 家".format(age, count))

    # ========== 5. 品牌检测 ==========
    brand_count = sum(1 for r in rows if r.get('brand'))
    report_lines.append("\n【品牌识别】")
    report_lines.append("  识别到品牌: {} 条 / {} 条 ({:.0f}%)".format(
        brand_count, len(rows), brand_count/len(rows)*100))

    brand_stats = Counter(r['brand'] for r in rows if r.get('brand'))
    if brand_stats:
        for brand, n in brand_stats.most_common():
            report_lines.append("    {}: {} 个".format(brand, n))
    else:
        report_lines.append("    (品牌信息需从商品详情页采集)")

    # ========== 6. 回头率分析 ==========
    rates = []
    for r in rows:
        rate = r.get('return_rate', '').replace('%', '')
        try:
            rates.append(int(rate))
        except:
            pass
    if rates:
        report_lines.append("\n【回头率】")
        report_lines.append("  有回头率数据: {} 条".format(len(rates)))
        report_lines.append("  平均回头率: {:.0f}%".format(sum(rates)/len(rates)))

    report_lines.append("\n" + "=" * 55)
    report_lines.append("  报告生成时间: pipeline/04_analyze.py")
    report_lines.append("=" * 55)

    report = '\n'.join(report_lines)
    print(report)
    save_report(report, OUTPUT_TXT)

    # ========== 尝试生成图表 ==========
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib import font_manager

        # 设置中文字体
        for font_name in ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']:
            try:
                plt.rcParams['font.sans-serif'] = [font_name]
                plt.rcParams['axes.unicode_minus'] = False
                # 测试是否能渲染中文
                fig_test, ax_test = plt.subplots()
                ax_test.set_title('测试中文')
                fig_test.savefig(os.devnull, dpi=10)
                plt.close(fig_test)
                print('  使用字体:', font_name)
                break
            except:
                continue
        else:
            print('  警告: 未找到中文字体, 图表中文可能显示为方框')

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('1688 户外灯具 商品数据分析', fontsize=14, fontweight='bold')

        # 1. 价格箱线图
        ax = axes[0, 0]
        p99 = np.percentile(prices, 99)
        filtered_prices = [p for p in prices if p <= p99]
        ax.hist(filtered_prices, bins=50, color='skyblue', edgecolor='white')
        ax.axvline(np.median(prices), color='red', linestyle='--', label='中位数 ¥{:.0f}'.format(np.median(prices)))
        ax.set_xlabel('价格 (¥)')
        ax.set_ylabel('商品数')
        ax.set_title('价格分布 (去除前1%极值)')
        ax.legend()

        # 2. 供应商TOP10
        ax = axes[0, 1]
        top10 = shop_counter.most_common(10)
        shops = [s[:15] for s, _ in top10]
        counts = [c for _, c in top10]
        ax.barh(range(len(shops)), counts, color='lightcoral')
        ax.set_yticks(range(len(shops)))
        ax.set_yticklabels(shops)
        ax.set_xlabel('商品数')
        ax.set_title('TOP10 供应商')

        # 3. 品类分布TOP10
        ax = axes[1, 0]
        top_cats = cat_counter.most_common(10)
        cats = [c[:12] for c, _ in top_cats]
        cat_counts = [c for _, c in top_cats]
        ax.pie(cat_counts, labels=cats, autopct='%1.0f%%', startangle=90)
        ax.set_title('品类分布 TOP10')

        # 4. 店铺经营时长
        ax = axes[1, 1]
        if age_counter:
            labels = list(age_counter.keys())
            values = list(age_counter.values())
            bars = ax.bar(labels, values, color='lightgreen', edgecolor='white')
            ax.set_ylabel('商品数')
            ax.set_title('店铺经营时长')
            for bar, v in zip(bars, values):
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, str(v),
                        ha='center', fontsize=10)

        plt.tight_layout()
        plt.savefig(OUTPUT_PNG, dpi=150)
        print("\n图表已保存:", OUTPUT_PNG)
        plt.close()

    except ImportError:
        print("\n提示: matplotlib未安装, 图表未生成")
        print("  安装: pip install matplotlib")
    except Exception as e:
        print("\n图表生成失败:", str(e))


if __name__ == "__main__":
    import re  # used in analysis
    main()

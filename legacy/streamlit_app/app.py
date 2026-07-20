"""
PageHarvest — Streamlit 前端

搜索页选品 与 详情页解析 两个独立入口。
"""

import os
import sys
import io
import zipfile
from pathlib import Path

import streamlit as st
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.engine import process_upload

st.set_page_config(
    page_title="PageHarvest",
    page_icon="✦",
    layout="wide",
)


# ═══════════════════════════════════════════════════════════════
#  使用说明
# ═══════════════════════════════════════════════════════════════

PLATFORM_HELP = {
    "震坤行": {
        "icon": "🏭",
        "采集方式": "安装油猴脚本 → 打开搜索页 → 自动翻页保存",
        "脚本链接": "https://greasyfork.org/zh-CN/scripts/586396",
    },
    "1688": {
        "icon": "📦",
        "采集方式": "安装 1688采购助手 → 打开搜索页 → 插件导出 XLSX",
        "脚本链接": "https://greasyfork.org/zh-CN/scripts/586397",
    },
    "京东": {
        "icon": "🛒",
        "采集方式": "浏览器打开页面 → 另存为 HTML",
        "脚本链接": None,
    },
}

STEPS_SEARCH = {
    "搜索页选品": [
        "安装对应平台的采集脚本（或直接用浏览器保存）",
        "在平台上搜索商品关键词，等待页面加载完成",
        "浏览器「另存为」HTML，或从采购助手导出 XLSX",
        "将文件打包成 ZIP，上传到左侧入口",
        "自动解析 → 输出推荐上架清单（CSV + 分析报告）",
    ],
}

STEPS_DETAIL = {
    "详情页解析": [
        "打开商品的详情页面，等待页面完全加载（含图片、属性、SKU）",
        "浏览器「另存为」完整 HTML",
        "将多个详情页 HTML 打包成 ZIP，上传到右侧入口",
        "自动解析 → 输出结构化数据（Excel + CSV）",
    ],
}


def show_help():
    with st.expander("📖 数据采集说明", expanded=False):
        tab1, tab2 = st.tabs(["搜索页采集", "详情页采集"])
        with tab1:
            for name, info in PLATFORM_HELP.items():
                parts = [f"**{info['icon']} {name}**", f"{info['采集方式']}"]
                if info["脚本链接"]:
                    parts.append(f"[安装脚本]({info['脚本链接']})")
                st.markdown("  \n".join(parts))
                st.divider()
        with tab2:
            st.markdown("""
            **操作步骤：**
            1. 打开商品详情页
            2. 等图片、属性表、SKU规格都加载完成
            3. Ctrl+S 另存为「网页，全部（*.htm；*.html）」
            4. 打包成 ZIP 上传

            > 支持平台：震坤行 / 京东 / 1688
            """)


# ═══════════════════════════════════════════════════════════════
#  搜索页入口
# ═══════════════════════════════════════════════════════════════

def show_search_tab():
    st.subheader("📤 上传搜索页数据")
    st.caption("上传平台搜索页的 HTML 或 XLSX → 输出推荐上架清单")

    uploaded = st.file_uploader(
        "选择 ZIP 压缩包（含搜索页 HTML 或 1688 采购助手 XLSX）",
        type=["zip"],
        key="search_upload",
        help="将浏览器保存的搜索页 HTML，或 1688采购助手导出的 XLSX，打包成 ZIP 上传",
    )

    if not uploaded:
        st.info("👆 上传后自动开始选品分析")
        return

    with st.spinner("正在解析搜索页，提取商品数据..."):
        result = process_upload(uploaded.getbuffer())

    if result.error:
        st.error(f"处理失败")
        st.code(result.error, language="text")
        st.markdown("""
        **排查建议：**
        - 确认文件是浏览器完整保存的 HTML（非片段）
        - 确认 ZIP 内含 `.html` 或 `.xlsx` 文件
        - 1688 优先使用采购助手导出的 XLSX
        """)
        return

    if result.page_type != "search":
        st.warning(f"上传的文件被识别为「详情页」而非搜索页，结果可能不正确")
        st.code(f"检测类型: {result.page_type}  平台: {result.platform}")

    st.success(f"✅ 选品分析完成 — {result.platform}  |  {result.product_count} 件推荐商品")

    tab_a, tab_b, tab_c = st.tabs(["📋 分析报告", "📊 商品清单", "📥 下载"])

    with tab_a:
        st.text(result.txt_content)

    with tab_b:
        if result.csv_content:
            df = pd.read_csv(io.StringIO(result.csv_content))
            col_config = {}
            if "链接" in df.columns:
                col_config["链接"] = st.column_config.LinkColumn("链接")
            st.dataframe(df, use_container_width=True, hide_index=True,
                         column_config=col_config)

    with tab_c:
        output_buf = io.BytesIO()
        with zipfile.ZipFile(output_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("选品推荐合集.csv", result.csv_content.encode("utf-8-sig"))
            zf.writestr("选品分析报告.txt", result.txt_content.encode("utf-8"))
        output_buf.seek(0)

        st.download_button(
            label="📥 下载结果 (.zip)",
            data=output_buf,
            file_name="pageharvest_选品分析结果.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )


# ═══════════════════════════════════════════════════════════════
#  详情页入口
# ═══════════════════════════════════════════════════════════════

def show_detail_tab():
    st.subheader("📤 上传详情页数据")
    st.caption("上传商品详情页 HTML → 提取结构化数据（属性/SKU/图片）")

    uploaded = st.file_uploader(
        "选择 ZIP 压缩包（含详情页 HTML）",
        type=["zip"],
        key="detail_upload",
        help="将浏览器保存的商品详情页 HTML 打包成 ZIP 上传",
    )

    if not uploaded:
        st.info("👆 上传后自动开始解析")
        return

    with st.spinner("正在解析详情页，提取结构化数据..."):
        result = process_upload(uploaded.getbuffer())

    if result.error:
        st.error(f"处理失败")
        st.code(result.error, language="text")
        st.markdown("""
        **排查建议：**
        - 确认文件是浏览器完整保存的 HTML（含属性表、SKU区域）
        - 确认页面已完全加载后再保存
        - 目前支持：震坤行 / 京东 / 1688 详情页
        """)
        return

    if result.page_type != "detail":
        st.warning(f"上传的文件被识别为「搜索页」而非详情页，结果可能不正确")

    st.success(f"✅ 详情页解析完成 — {result.platform}  |  {result.product_count} 件商品")

    tab_a, tab_b = st.tabs(["📊 解析概览", "📥 下载"])

    with tab_a:
        if result.detail_csv:
            df = pd.read_csv(io.StringIO(result.detail_csv))
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("无数据")

    with tab_b:
        output_buf = io.BytesIO()
        with zipfile.ZipFile(output_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("详情页数据.xlsx", result.xlsx_bytes)
            if result.detail_csv:
                zf.writestr("parsed_summary.csv", result.detail_csv.encode("utf-8-sig"))
        output_buf.seek(0)

        st.download_button(
            label="📥 下载结果 (.zip)",
            data=output_buf,
            file_name="pageharvest_详情页结果.zip",
            mime="application/zip",
            type="primary",
            use_container_width=True,
        )


# ═══════════════════════════════════════════════════════════════
#  主界面
# ═══════════════════════════════════════════════════════════════

def main():
    st.title("✦ PageHarvest")
    st.caption("多平台商品数据采集 & 选品分析")

    show_help()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("## 🔍 搜索页选品")
        st.markdown("上传搜索页 HTML/XLSX → 自动排名 → 输出推荐清单")
        show_search_tab()

    with col2:
        st.markdown("## 📄 详情页解析")
        st.markdown("上传详情页 HTML → 提取属性/SKU/图片 → 结构化输出")
        show_detail_tab()


if __name__ == "__main__":
    main()

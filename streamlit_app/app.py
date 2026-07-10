"""
PageHarvest — Streamlit 前端
==============================
仅通过 api.engine（子进程封装层）调用底层引擎，不直接接触任何原工程代码。
"""

import os
import sys
import io
import zipfile
from pathlib import Path

import streamlit as st
import pandas as pd

# 将项目根加入路径
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from api.engine import process_upload, run_search_pipeline, run_detail_pipeline, Job

st.set_page_config(
    page_title="PageHarvest",
    page_icon="✦",
    layout="centered",
)


def main():
    st.title("✦ PageHarvest")
    st.caption("上传搜索页 HTML → 选品分析 | 上传详情页 HTML → 结构化数据")

    uploaded_file = st.file_uploader(
        "上传 ZIP 压缩包",
        type=["zip"],
        help="将 HTML 文件打包成 zip 上传。文件放在根目录或子目录均可。",
    )

    if not uploaded_file:
        st.info("上传 ZIP 文件后自动开始处理")
        return

    # ── 通过 API 处理 ──
    with st.spinner("正在处理..."):
        result = process_upload(uploaded_file.getbuffer())

    if result.error:
        st.error(f"处理失败:\n{result.error}")
        return

    # ── 搜索页结果 ──
    if result.page_type == "search":
        st.success(f"✅ 选品分析完成 — {result.platform}  {result.product_count} 件商品")

        with st.expander("📋 查看报告摘要", expanded=True):
            st.text(result.txt_content[:2000])

        df_preview = pd.read_csv(io.StringIO(result.csv_content))
        st.dataframe(df_preview.head(30), use_container_width=True, hide_index=True)

        # 打包下载
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
        )

    # ── 详情页结果 ──
    elif result.page_type == "detail":
        st.success(f"✅ 详情页解析完成 — {result.platform}  {result.product_count} 件商品")

        # 预览
        if result.detail_csv:
            with st.expander("📋 查看解析结果预览", expanded=True):
                df_preview = pd.read_csv(io.StringIO(result.detail_csv))
                st.dataframe(df_preview, use_container_width=True, hide_index=True)
        else:
            st.info("无数据")

        # 打包下载
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
        )

        st.info("📄 说明：下载的 ZIP 包含 Excel + CSV 汇总")


if __name__ == "__main__":
    main()

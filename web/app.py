"""PageHarvest — Flask Web 应用

搜索页选品 / 详情页解析 完全隔离。
"""

# ══ 调试日志（启动时写 ph_debug.log，和 exe 同目录） ══
import sys as _sys, pathlib as _pl
try:
    _dbg = _pl.Path(getattr(_sys, '_MEIPASS', str(_pl.Path(__file__).resolve().parent)))
    _log = _dbg.parent / "ph_debug.log"
    with open(_log, "w", encoding="utf-8") as _f:
        _f.write(f"_MEIPASS={getattr(_sys, '_MEIPASS', 'N/A')}\n")
        _f.write(f"__file__={__file__}\n")
        _f.write(f"cwd={_pl.Path.cwd()}\n")
        _f.write(f"sys.argv[0]={_sys.argv[0] if len(_sys.argv) > 0 else 'N/A'}\n")
        _f.write(f"sys.executable={_sys.executable}\n")
        _mp = getattr(_sys, '_MEIPASS', None)
        if _mp:
            _p = _pl.Path(_mp)
            _f.write(f"\n--- _MEIPASS 第一层 ---\n")
            for _x in sorted(_p.iterdir()):
                _f.write(f"  {'📁' if _x.is_dir() else '📄'} {_x.name}\n")
            _w = _p / "web"
            if _w.is_dir():
                _f.write(f"\n--- _MEIPASS/web/ ---\n")
                for _x in sorted(_w.iterdir()):
                    _f.write(f"  {'📁' if _x.is_dir() else '📄'} {_x.name}\n")
        _f.write("\n")
except Exception:
    pass  # 日志不是必需的

import os
import sys
import csv
import io
import json
import uuid
import threading
import tempfile
import shutil
import zipfile
from pathlib import Path
from io import BytesIO

from flask import Flask, render_template, request, jsonify, send_file, Response, stream_with_context

# ── 确保项目根在 sys.path（同时支持开发模式和 PyInstaller 打包） ──
import sys as _sys
try:
    # PyInstaller 打包后，资源在 sys._MEIPASS
    _base = Path(getattr(_sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
except Exception:
    _base = Path(__file__).resolve().parent.parent

if str(_base) not in _sys.path:
    _sys.path.insert(0, str(_base))

HERE = Path(__file__).resolve().parent
ROOT = _base

# PyInstaller 打包后 resources 在 sys._MEIPASS/web/ 下
_WEB_DIR = ROOT / "web"
_TEMPLATES = _WEB_DIR / "templates"
_STATIC = _WEB_DIR / "static"

from api.engine import process_upload
from core.detail_parser import parse_detail, detect_platform

app = Flask(__name__,
    template_folder=str(_TEMPLATES),
    static_folder=str(_STATIC),
    static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

# ── 作业状态 + 结果存储（线程安全） ──
_status: dict[str, dict] = {}
_results: dict[str, dict] = {}
_lock = threading.Lock()


def sget(job_id: str):
    with _lock:
        return _status.get(job_id, {}).copy()


def sput(job_id: str, key: str, value):
    with _lock:
        _status.setdefault(job_id, {})[key] = value


def rget(job_id: str):
    with _lock:
        return _results.get(job_id, {}).copy()


def rput(job_id: str, data: dict):
    with _lock:
        _results[job_id] = data


def cleanup(job_id: str):
    with _lock:
        _status.pop(job_id, None)
        _results.pop(job_id, None)


# ── 工具：解压 ZIP ──

def _extract_zip(zip_bytes: bytes) -> tuple[Path, list[Path]]:
    """解压到临时目录，返回 (tmp_dir, [文件路径列表])"""
    tmp = Path(tempfile.mkdtemp(prefix="ph_"))
    zpath = tmp / "upload.zip"
    zpath.write_bytes(zip_bytes)
    with zipfile.ZipFile(zpath, "r") as z:
        z.extractall(tmp)
    files = sorted(tmp.rglob("*")) if any(tmp.iterdir()) else []
    return tmp, [f for f in files if f.is_file() and not f.name.startswith(".")]


# ═══════════════════════════════════════════════════════════════
#  路由 — 首页
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


# ═══════════════════════════════════════════════════════════════
#  路由 — 搜索页选品
# ═══════════════════════════════════════════════════════════════

@app.route("/upload-search", methods=["POST"])
def upload_search():
    if "file" not in request.files:
        return "未选择文件", 400
    file = request.files["file"]
    if file.filename == "":
        return "文件名为空", 400

    job_id = uuid.uuid4().hex[:12]
    sput(job_id, "status", "uploading")
    sput(job_id, "filename", file.filename)
    sput(job_id, "mode", "search")

    zip_bytes = file.read()
    thread = threading.Thread(target=_run_search, args=(job_id, zip_bytes), daemon=True)
    thread.start()

    return render_template("processing.html", job_id=job_id, filename=file.filename, mode="search")


def _run_search(job_id: str, zip_bytes: bytes):
    """搜索页选品：通过 api.engine.process_upload 路由"""
    try:
        sput(job_id, "status", "extracting")
        sput(job_id, "message", "正在解压...")

        pipeline_result = process_upload(zip_bytes)

        if not pipeline_result.success:
            sput(job_id, "status", "error")
            sput(job_id, "error", pipeline_result.error)
            return

        sput(job_id, "status", "analyzing")
        sput(job_id, "message", "正在分析...")

        display = {
            "mode": "search",
            "platform": pipeline_result.platform,
            "product_count": pipeline_result.product_count,
            "csv_content": pipeline_result.csv_content,
            "txt_content": pipeline_result.txt_content,
        }
        if pipeline_result.xlsx_bytes:
            display["has_xlsx"] = True
            display["_xlsx_bytes"] = pipeline_result.xlsx_bytes

        if pipeline_result.csv_content:
            reader = csv.DictReader(io.StringIO(pipeline_result.csv_content))
            display["table"] = list(reader)
            display["columns"] = reader.fieldnames or []

        rput(job_id, display)
        sput(job_id, "status", "done")
        sput(job_id, "message", "分析完成")

    except Exception as e:
        sput(job_id, "status", "error")
        sput(job_id, "error", str(e))


# ═══════════════════════════════════════════════════════════════
#  路由 — 详情页解析
# ═══════════════════════════════════════════════════════════════

@app.route("/upload-detail", methods=["POST"])
def upload_detail():
    if "file" not in request.files:
        return "未选择文件", 400
    file = request.files["file"]
    if file.filename == "":
        return "文件名为空", 400

    job_id = uuid.uuid4().hex[:12]
    sput(job_id, "status", "uploading")
    sput(job_id, "filename", file.filename)
    sput(job_id, "mode", "detail")

    zip_bytes = file.read()
    thread = threading.Thread(target=_run_detail, args=(job_id, zip_bytes), daemon=True)
    thread.start()

    return render_template("processing.html", job_id=job_id, filename=file.filename, mode="detail")


def _run_detail(job_id: str, zip_bytes: bytes):
    """详情页解析：直接调用 core.detail_parser，不经过 api.engine"""
    try:
        sput(job_id, "status", "extracting")
        sput(job_id, "message", "正在解析详情页...")

        tmp_dir, files = _extract_zip(zip_bytes)
        html_files = [f for f in files if f.suffix.lower() == ".html"]

        if not html_files:
            sput(job_id, "status", "error")
            sput(job_id, "error", "ZIP 中未找到 HTML 文件")
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return

        results = []
        for i, html_path in enumerate(html_files):
            sput(job_id, "message", f"解析第 {i+1}/{len(html_files)} 页...")

            html = html_path.read_text(encoding="utf-8", errors="replace")
            platform = detect_platform(html)
            detail = parse_detail(html)

            # 补充：从 _files/ 目录提取本地化图片
            # 仅当解析器本身未提取到主图时才启用，避免覆盖解析器的精确提取
            if detail:
                # 浏览器保存页面的 _files/ 目录补充
                # 浏览器保存后，动态加载的图全在 _files/ 目录（JD 页面尤其明显）
                # 解析器只从静态 HTML 提取，通常只拿到 0~3 张
                # 策略：当主图不足时，从 _files/ 按大小取最大 20 张补充
                files_dir = html_path.parent / (html_path.stem + "_files")
                if files_dir.is_dir() and len(detail.main_images) < 5:
                    per_product_dir = ROOT / "web" / "static" / "detail-images" / job_id / str(i)
                    per_product_dir.mkdir(parents=True, exist_ok=True)
                    candidates = []
                    for img_file in files_dir.iterdir():
                        if img_file.suffix.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif"):
                            continue
                        if img_file.stat().st_size < 10240:  # < 10KB 跳过（UI 图标）
                            continue
                        candidates.append(img_file)
                    candidates.sort(key=lambda f: f.stat().st_size, reverse=True)
                    img_urls = []
                    for img_file in candidates[:20]:
                        try:
                            dst = per_product_dir / img_file.name
                            shutil.copy2(str(img_file), str(dst))
                            img_urls.append(f"/static/detail-images/{job_id}/{i}/{img_file.name}")
                        except Exception:
                            pass
                    if img_urls:
                        detail.main_images = img_urls

                # 解析器提取到了主图，但含相对路径 → 转绝对
                if detail.main_images:
                    resolved = []
                    for img_path in detail.main_images:
                        if img_path.startswith("./"):
                            abs_path = html_path.parent / img_path[2:]
                            if abs_path.exists():
                                resolved.append(str(abs_path))
                            else:
                                resolved.append(img_path)
                        else:
                            resolved.append(img_path)
                    detail.main_images = resolved

            if detail:
                attrs = detail.attributes or {}
                results.append({
                    "file": html_path.name,
                    "platform": platform or "未知",
                    "product_id": detail.product_id,
                    "title": detail.title[:80],
                    "brand": detail.brand or "-",
                    "spec": detail.spec or "-",
                    "price_min": detail.price_min,
                    "price_max": detail.price_max,
                    "attributes": len(attrs),
                    "sku_count": detail.sku_count,
                    "image_count": len(detail.main_images or []),
                    "status": "✅",
                    "_raw": detail,
                })
            else:
                results.append({
                    "file": html_path.name,
                    "platform": platform or "未知",
                    "product_id": "",
                    "title": "",
                    "brand": "",
                    "spec": "",
                    "price_min": 0,
                    "price_max": 0,
                    "attributes": 0,
                    "sku_count": 0,
                    "image_count": 0,
                    "status": "❌",
                    "_raw": None,
                })

        sput(job_id, "status", "analyzing")
        sput(job_id, "message", "生成报告...")

        # ── 构建 CSV ──
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        writer.writerow(["文件", "平台", "商品ID", "标题", "品牌", "型号",
                         "最低价", "最高价", "属性数", "SKU数", "主图数", "状态"])
        for r in results:
            writer.writerow([r["file"], r["platform"], r["product_id"], r["title"],
                             r["brand"], r["spec"], r["price_min"], r["price_max"],
                             r["attributes"], r["sku_count"], r["image_count"], r["status"]])

        # ── 构建 TXT 报告 ──
        ok = [r for r in results if r["status"] == "✅"]
        fail = [r for r in results if r["status"] == "❌"]
        txt_lines = [f"PageHarvest 详情页解析报告", f""]
        platforms = set(r["platform"] for r in ok)
        txt_lines.append(f"共 {len(results)} 页，成功 {len(ok)}，失败 {len(fail)}")
        txt_lines.append(f"涉及平台: {', '.join(sorted(platforms))}")
        txt_lines.append("")
        for r in ok:
            txt_lines.append(f"  ✅ {r['brand']:12s} ¥{r['price_min']:<8.2f}  "
                             f"{r['sku_count']} SKU  {r['attributes']} 属性  {r['image_count']} 图  "
                             f"{r['title'][:35]}")

        success_count = len(ok)

        # ── Excel（直接由 JSON 转换，不过度加工） ──
        xlsx_bytes = b""
        try:
            from openpyxl import Workbook

            full_json = []
            for r in results:
                item = {k: v for k, v in r.items() if k != "_raw"}
                raw = r.get("_raw")
                if raw:
                    import dataclasses
                    item["_parsed"] = dataclasses.asdict(raw)
                else:
                    item["_parsed"] = None
                full_json.append(item)

            wb = Workbook()
            ws = wb.active
            ws.title = "解析结果"

            all_cols = ["file", "platform", "product_id", "title", "brand", "spec",
                        "price_min", "price_max", "attributes_count", "sku_count",
                        "image_count", "status"]
            parsed_cols = ["ship_from", "sales_count", "yearly_sales", "repurchase_rate",
                           "listing_date", "product_code", "min_order"]
            all_cols += [f"parsed.{c}" for c in parsed_cols]
            all_cols += ["attributes", "sku_matrix", "main_images", "detail_images"]

            ws.append(all_cols)

            for item in full_json:
                row = []
                for c in ["file", "platform", "product_id", "title", "brand", "spec",
                          "price_min", "price_max"]:
                    row.append(item.get(c, ""))
                row.append(len(item.get("_parsed", {}).get("attributes", {})))
                row.append(item.get("sku_count", 0))
                row.append(item.get("image_count", 0))
                row.append(item.get("status", ""))
                parsed = item.get("_parsed", {}) or {}
                for c in parsed_cols:
                    row.append(parsed.get(c, ""))
                row.append(str(parsed.get("attributes", {})))
                row.append(str(parsed.get("sku_matrix", [])))
                row.append("\n".join(parsed.get("main_images", [])))
                row.append("\n".join(parsed.get("detail_images", [])))
                ws.append(row)

            xlsx_buf = BytesIO()
            wb.save(xlsx_buf)
            xlsx_bytes = xlsx_buf.getvalue()
        except Exception:
            pass

        # 构建图片预览数据
        detail_images_preview = []
        detail_desc_images_preview = []
        for r in ok:
            raw = r.get("_raw")
            if raw:
                if raw.main_images:
                    detail_images_preview.append({
                        "title": f"{raw.brand or '?'} - {raw.title[:40]}",
                        "images": raw.main_images[:10],
                    })
                if raw.detail_images:
                    detail_desc_images_preview.append({
                        "title": f"{raw.brand or '?'} - {raw.title[:40]}",
                        "images": raw.detail_images[:10],
                    })

        # 构建完整解析 JSON
        raw_json = []
        for r in results:
            item = {k: v for k, v in r.items() if k != "_raw"}
            raw = r.get("_raw")
            if raw:
                import dataclasses
                item["_parsed"] = dataclasses.asdict(raw)
            else:
                item["_parsed"] = None
            raw_json.append(item)

        display = {
            "mode": "detail",
            "product_count": len(results),
            "success_count": success_count,
            "csv_content": csv_buf.getvalue(),
            "txt_content": "\n".join(txt_lines),
            "table": [{k: v for k, v in r.items() if k != "_raw"} for r in results],
            "columns": ["文件", "平台", "商品ID", "标题", "品牌", "型号",
                        "最低价", "最高价", "属性数", "SKU数", "主图数", "状态"],
            "_detail_raw": raw_json,
            "_detail_images": detail_images_preview,
            "_detail_desc_images": detail_desc_images_preview,
        }
        if xlsx_bytes:
            display["has_xlsx"] = True
            display["_xlsx_bytes"] = xlsx_bytes

        rput(job_id, display)
        sput(job_id, "status", "done")
        sput(job_id, "message", "解析完成")

        shutil.rmtree(tmp_dir, ignore_errors=True)

    except Exception as e:
        sput(job_id, "status", "error")
        sput(job_id, "error", str(e))
        import traceback
        sput(job_id, "traceback", traceback.format_exc())


# ═══════════════════════════════════════════════════════════════
#  通用路由 — 进度 / 处理中 / 结果 / 下载
# ═══════════════════════════════════════════════════════════════

@app.route("/progress/<job_id>")
def progress(job_id: str):
    """SSE 进度"""
    def generate():
        import time
        while True:
            p = sget(job_id)
            safe = {k: v for k, v in p.items() if isinstance(v, (str, int, float, bool, type(None)))}
            yield f"data: {json.dumps(safe, ensure_ascii=False)}\n\n"
            if safe.get("status") in ("done", "error"):
                break
            time.sleep(0.3)
    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/processing/<job_id>")
def processing_page(job_id: str):
    """处理等待页"""
    result = rget(job_id)
    if result:
        return render_template("results.html", job_id=job_id, result=result)
    s = sget(job_id)
    return render_template(
        "processing.html",
        job_id=job_id,
        filename=s.get("filename", ""),
        mode=s.get("mode", ""),
        error=s.get("status") == "error" and s.get("error") or None,
    )


@app.route("/results/<job_id>")
def results_page(job_id: str):
    """结果页"""
    result = rget(job_id)
    if result:
        return render_template("results.html", job_id=job_id, result=result)
    return render_template("processing.html", job_id=job_id, filename="", error=None)


@app.route("/download/<job_id>/<fmt>")
def download(job_id: str, fmt: str):
    result = rget(job_id)
    if fmt == "csv":
        content = result.get("csv_content", "")
        if not content:
            return "无数据", 404
        return Response(content, mimetype="text/csv; charset=utf-8-sig",
                        headers={"Content-Disposition": f"attachment; filename=ph_{job_id[:8]}.csv"})
    elif fmt == "txt":
        content = result.get("txt_content", "")
        if not content:
            return "无数据", 404
        return Response(content, mimetype="text/plain; charset=utf-8",
                        headers={"Content-Disposition": f"attachment; filename=ph_{job_id[:8]}.txt"})
    elif fmt == "xlsx":
        b = result.get("_xlsx_bytes")
        if not b:
            return "无数据", 404
        return send_file(BytesIO(b), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name=f"ph_{job_id[:8]}.xlsx")
    elif fmt == "json":
        clean = {}
        for k, v in result.items():
            if k == "_xlsx_bytes":
                continue
            if k == "_detail_raw":
                clean["detail_raw"] = v
            elif not k.startswith("_"):
                clean[k] = v
        return Response(
            json.dumps(clean, ensure_ascii=False, indent=2, default=str),
            mimetype="application/json; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=ph_{job_id[:8]}.json"},
        )
    return "不支持", 400


if __name__ == "__main__":
    import argparse, re
    parser = argparse.ArgumentParser(description="PageHarvest Web App")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址")
    parser.add_argument("--port", default=8080, type=int, help="端口")
    parser.add_argument("--debug", action="store_true", help="调试模式")
    args = parser.parse_args()

    print(f"✦ PageHarvest Web App  →  http://localhost:{args.port}")
    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)

#!/usr/bin/env bash
# usage: bash scaffold.sh my-new-crawler

set -euo pipefail

NAME="${1:-}"
if [ -z "$NAME" ]; then
    echo "Usage: bash scaffold.sh <project-name>"
    exit 1
fi

SRC="$(dirname "$0")/_project"
DST="$NAME"

if [ -d "$DST" ]; then
    echo "Error: $DST already exists"
    exit 1
fi

cp -r "$SRC" "$DST"
echo "✅ Created $DST from crawler template"
echo ""
echo "Next steps:"
echo "  cd $DST"
echo "  pip install -r requirements.txt"
echo "  playwright install chromium"
echo "  # Then edit these files for your target platform:"
echo "  #   collector/list_page.py   — 搜索页选择器 + URL"
echo "  #   collector/detail_page.py — 详情页选择器"
echo "  #   core/db.py               — 数据库 schema"
echo "  #   engine/filter.py         — 过滤规则"
echo "  #   engine/alerter.py        — 预警规则"

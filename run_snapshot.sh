#!/usr/bin/env sh
# Thu thập snapshot VNTRIP và cập nhật các bảng phân tích tăng trưởng.
# Dùng thủ công: ./run_snapshot.sh
# Dùng cấu hình khác: ./run_snapshot.sh .env.local

set -eu

ROOT_DIR="$(CDPATH= cd "$(dirname "$0")" && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Không tìm thấy tệp cấu hình: $ENV_FILE" >&2
  exit 1
fi

set -a
. "$ENV_FILE"
set +a

if [ -z "${PYTHON_BIN:-}" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi
if [ ! -x "$PYTHON_BIN" ]; then
  echo "Không tìm thấy Python thực thi: $PYTHON_BIN" >&2
  exit 1
fi

cd "$ROOT_DIR"
echo "===== Snapshot VNTRIP $(date -u '+%Y-%m-%dT%H:%M:%SZ') ====="
"$PYTHON_BIN" VNTRIP/crawl_vntrip.py
"$PYTHON_BIN" analysis_pipeline.py
"$PYTHON_BIN" dashboard.py

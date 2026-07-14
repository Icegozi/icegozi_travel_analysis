#!/usr/bin/env sh
# Chạy toàn bộ luồng crawl và phân tích. Dùng: ./run_all.sh
# Có thể truyền tệp cấu hình khác: ./run_all.sh .env.local

set -eu

ROOT_DIR="$(CDPATH= cd "$(dirname "$0")" && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Không tìm thấy tệp cấu hình: $ENV_FILE" >&2
  exit 1
fi

# .env là tệp cục bộ do nhóm quản lý; các biến được export cho crawler và analysis_pipeline.py.
set -a
. "$ENV_FILE"
set +a

if [ -z "${PYTHON_BIN:-}" ]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi
if [ ! -x "$PYTHON_BIN" ]; then
  echo "Không tìm thấy Python thực thi: $PYTHON_BIN" >&2
  echo "Hãy tạo .venv hoặc đặt PYTHON_BIN trong .env." >&2
  exit 1
fi

run_step() {
  name="$1"
  shift
  echo
  echo "===== $name ====="
  "$@"
}

cd "$ROOT_DIR"

if [ "${RUN_VNTRIP_CRAWLER:-1}" = "1" ]; then
  run_step "Crawl VNTRIP" "$PYTHON_BIN" VNTRIP/crawl_vntrip.py
else
  echo "Bỏ qua crawl VNTRIP (RUN_VNTRIP_CRAWLER=0)."
fi

if [ "${RUN_VIETNAM_TRAVEL_CRAWLER:-1}" = "1" ]; then
  run_step "Crawl Vietnam.travel" "$PYTHON_BIN" VIETNAM_TRAVEL/crawl_vietnam_travel.py
else
  echo "Bỏ qua crawl Vietnam.travel (RUN_VIETNAM_TRAVEL_CRAWLER=0)."
fi

run_step "Phân tích dữ liệu" "$PYTHON_BIN" analysis_pipeline.py
run_step "Tạo dashboard HTML" "$PYTHON_BIN" dashboard.py
echo
echo "Hoàn tất. Dashboard nằm trong: $ROOT_DIR/docs/index.html"

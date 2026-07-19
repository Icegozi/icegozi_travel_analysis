"""Chặn xuất bản dashboard khi dữ liệu crawl/phan tich không đạt ngưỡng tối thiểu."""

import os
import sys
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT_DIR / "data" / "analysis"


def read_csv(name):
    path = ANALYSIS_DIR / name
    if not path.exists():
        return None
    return pd.read_csv(path)


def write_summary(lines):
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as output:
            output.write("## Quality gate dashboard\n\n" + "\n".join(lines) + "\n")


def check_manifest(required_sources, max_age_days, required, errors, report):
    """Kiểm tra crawler có chạy gần đây và có báo cáo được tạo đúng định dạng."""
    if not required:
        return
    path = ANALYSIS_DIR / "run_metadata.json"
    if not path.exists():
        errors.append("Thiếu run_metadata.json; không thể xác nhận độ mới của dữ liệu crawl.")
        return
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        errors.append("run_metadata.json không phải JSON hợp lệ.")
        return
    manifests = metadata.get("sources", {})
    now = datetime.now(UTC)
    for source in required_sources:
        manifest = manifests.get(source)
        if not manifest:
            errors.append(f"Không có manifest crawl cho nguồn {source}.")
            continue
        try:
            finished_at = datetime.fromisoformat(manifest["finished_at"].replace("Z", "+00:00"))
            age_days = (now - finished_at).total_seconds() / 86400
        except (KeyError, TypeError, ValueError):
            errors.append(f"Manifest của {source} thiếu thời gian hoàn tất hợp lệ.")
            continue
        report.append(f"- Manifest {source}: **{age_days:.1f} ngày tuổi**, {manifest.get('new_records', 0)} bản ghi mới")
        if age_days > max_age_days:
            errors.append(f"Manifest {source} đã cũ {age_days:.1f} ngày, vượt ngưỡng {max_age_days} ngày.")


def main():
    min_total = int(os.getenv("QUALITY_MIN_TOTAL_ARTICLES", "20"))
    min_per_source = int(os.getenv("QUALITY_MIN_SOURCE_ARTICLES", "5"))
    max_review_rate = float(os.getenv("QUALITY_MAX_LABEL_REVIEW_RATE", "0.90"))
    require_opportunity_scores = os.getenv("QUALITY_REQUIRE_OPPORTUNITY_SCORES", "1") == "1"
    required_sources = [item.strip() for item in os.getenv("QUALITY_REQUIRED_SOURCES", "").split(",") if item.strip()]
    require_fresh_manifest = os.getenv("QUALITY_REQUIRE_FRESH_MANIFEST", "0") == "1"
    max_manifest_age_days = float(os.getenv("QUALITY_MAX_MANIFEST_AGE_DAYS", "4"))
    errors, report = [], []

    articles = read_csv("normalized_articles.csv")
    if articles is None or articles.empty:
        errors.append("Không có normalized_articles.csv hoặc bảng không có dữ liệu.")
    else:
        total = len(articles)
        report.append(f"- Bài hợp lệ: **{total}** (ngưỡng: {min_total})")
        if total < min_total:
            errors.append(f"Chỉ có {total} bài hợp lệ, thấp hơn ngưỡng {min_total}.")
        source_counts = articles.groupby("source").size().to_dict()
        for source in required_sources:
            count = int(source_counts.get(source, 0))
            report.append(f"- {source}: **{count}** bài (ngưỡng: {min_per_source})")
            if count < min_per_source:
                errors.append(f"Nguồn {source} chỉ có {count} bài.")
        for column, label in [("destination_status", "địa danh"), ("theme_status", "chủ đề")]:
            if column in articles:
                rate = float((articles[column] == "needs_review").mean())
                report.append(f"- Nhãn {label} cần rà soát: **{rate:.1%}** (tối đa: {max_review_rate:.0%})")
                if rate > max_review_rate:
                    errors.append(f"Tỷ lệ nhãn {label} cần rà soát quá cao: {rate:.1%}.")

    check_manifest(required_sources, max_manifest_age_days, require_fresh_manifest, errors, report)

    scores = read_csv("destination_opportunity_scores.csv")
    if scores is None or scores.empty:
        if require_opportunity_scores:
            errors.append("Không có điểm cơ hội để hiển thị trên dashboard.")
        else:
            report.append("- Điểm cơ hội: **không áp dụng** (không có dữ liệu lượt xem VNTRIP)")
    else:
        report.append(f"- Điểm đến được chấm điểm: **{len(scores)}**")

    dashboard_file = ROOT_DIR / "docs" / "index.html"
    if not dashboard_file.exists() or "<!doctype html>" not in dashboard_file.read_text(encoding="utf-8").lower():
        errors.append("docs/index.html chưa được tạo hợp lệ.")
    else:
        report.append("- Dashboard HTML: **hợp lệ**")

    if errors:
        lines = ["**Kết quả: KHÔNG ĐẠT**", *report, "", "### Lý do chặn publish", *[f"- {error}" for error in errors]]
        write_summary(lines)
        print("QUALITY GATE FAILED")
        print("\n".join(errors))
        sys.exit(1)

    lines = ["**Kết quả: ĐẠT**", *report]
    write_summary(lines)
    print("QUALITY GATE PASSED")
    print("\n".join(report))


if __name__ == "__main__":
    main()

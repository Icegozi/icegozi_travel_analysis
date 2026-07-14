"""Sinh dashboard tĩnh từ template; CSS và JavaScript được tách để dễ bảo trì."""

import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from string import Template

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent
ANALYSIS_DIR = ROOT_DIR / "data" / "analysis"
ASSET_DIR = ROOT_DIR / "dashboard_assets"
OUTPUT_FILE = ROOT_DIR / "docs" / "index.html"
DATA_EXPORTS = [
    ("VNTRIP — dữ liệu bài viết thô", "data/VNTRIP/rawdata.csv", "rawdata_vntrip.csv", "Bài viết HTML đã parse từ VNTRIP."),
    ("VNTRIP — danh sách liên kết", "data/VNTRIP/links_vntrip.csv", "links_vntrip.csv", "Các URL bài viết phát hiện từ trang danh mục."),
    ("VNTRIP — lịch sử snapshot", "data/VNTRIP/article_snapshots.csv", "article_snapshots.csv", "Lượt xem theo từng lần thu thập."),
    ("Vietnam.travel — dữ liệu bài viết thô", "data/VIETNAM_TRAVEL/rawdata.csv", "rawdata_vietnam_travel.csv", "Bài viết và trang điểm đến đã parse."),
    ("Vietnam.travel — danh sách liên kết", "data/VIETNAM_TRAVEL/links_vietnam_travel.csv", "links_vietnam_travel.csv", "Các URL công khai đã phát hiện."),
    ("Dữ liệu đã chuẩn hóa", "data/analysis/normalized_articles.csv", "normalized_articles.csv", "Nội dung đã làm sạch, khử trùng và gán nhãn."),
    ("Báo cáo điểm cơ hội", "data/analysis/destination_opportunity_scores.csv", "destination_opportunity_scores.csv", "Xếp hạng điểm đến và khuyến nghị hành động."),
    ("Thống kê mùa vụ", "data/analysis/destination_season_stats.csv", "destination_season_stats.csv", "Lượt xem/ngày theo điểm đến và mùa."),
    ("Rà soát nhãn", "data/analysis/label_review.csv", "label_review.csv", "Nhãn tự động, bằng chứng từ khóa và trạng thái kiểm tra."),
]


def read_csv(name, columns):
    path = ANALYSIS_DIR / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame(columns=columns)


def safe_json(value):
    """Không để dữ liệu crawl vô tình đóng thẻ script khi được nhúng vào HTML."""
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e")


def copy_downloads():
    export_dir = OUTPUT_FILE.parent / "data"
    export_dir.mkdir(parents=True, exist_ok=True)
    downloads = []
    for title, relative_source, filename, description in DATA_EXPORTS:
        source = ROOT_DIR / relative_source
        if source.exists():
            destination = export_dir / filename
            shutil.copy2(source, destination)
            downloads.append({"title": title, "file": f"data/{filename}", "description": description,
                              "size_kb": round(destination.stat().st_size / 1024, 1)})
    return downloads


def build_dashboard():
    scores = read_csv("destination_opportunity_scores.csv", ["destination"]).fillna(0)
    scores = scores.sort_values("opportunity_score", ascending=False)
    seasons = read_csv("destination_season_stats.csv", ["destination", "season", "median_views_per_day"]).fillna(0)
    articles = read_csv("normalized_articles.csv", ["source", "collected_at"])
    validation = read_csv("label_validation_summary.csv", ["article_count", "duplicate_removed", "destination_needs_review", "theme_needs_review"])
    metrics = {
        "destinations": len(scores),
        "articles": int(pd.to_numeric(scores.get("article_count", pd.Series(dtype=float)), errors="coerce").sum()),
        "views": float(pd.to_numeric(scores.get("total_views", pd.Series(dtype=float)), errors="coerce").sum()),
        "growth": float(pd.to_numeric(scores.get("latest_views_growth", pd.Series(dtype=float)), errors="coerce").sum()),
    }
    summary = articles.groupby("source", as_index=False).agg(article_count=("source", "size"), latest_collected_at=("collected_at", "max")) if not articles.empty else pd.DataFrame()
    lookup = summary.set_index("source").to_dict("index") if not summary.empty else {}
    source_cards = []
    for source, label in {"VNTRIP": "VNTRIP", "VIETNAM_TRAVEL": "Vietnam.travel"}.items():
        row = lookup.get(source, {"article_count": 0, "latest_collected_at": None})
        collected = pd.to_datetime(row["latest_collected_at"], errors="coerce", utc=True)
        timestamp = collected.strftime("%d/%m/%Y %H:%M UTC") if not pd.isna(collected) else "chưa có dữ liệu"
        source_cards.append(f'<div class="source-card"><b>{html.escape(label)}</b><span>{int(row["article_count"])} bài đã parse</span><small>Cập nhật: {timestamp}</small></div>')
    checks = validation.iloc[0].to_dict() if not validation.empty else {}
    check_text = (f'{int(checks.get("article_count", 0))} bài hợp lệ; {int(checks.get("duplicate_removed", 0))} bản ghi trùng đã loại; '
                  f'{int(checks.get("destination_needs_review", 0))} nhãn địa danh và {int(checks.get("theme_needs_review", 0))} nhãn chủ đề cần rà soát.')
    values = {
        "source_cards": "".join(source_cards), "check_text": html.escape(check_text),
        "generated_at": datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC"),
        "scores_json": safe_json(scores.to_dict(orient="records")),
        "seasons_json": safe_json(seasons.to_dict(orient="records")),
        "metrics_json": safe_json(metrics), "downloads_json": safe_json(copy_downloads()),
    }
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    shutil.copytree(ASSET_DIR, OUTPUT_FILE.parent / "assets", dirs_exist_ok=True)
    template = Template((ASSET_DIR / "dashboard.html").read_text(encoding="utf-8"))
    OUTPUT_FILE.write_text(template.substitute(values), encoding="utf-8")
    print(f"Đã tạo dashboard: {OUTPUT_FILE}")


if __name__ == "__main__":
    build_dashboard()

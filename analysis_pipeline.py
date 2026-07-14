"""Chạy tự động các phân tích dữ liệu du lịch không cần mở notebook."""

import json
import re
import unicodedata
from datetime import UTC, datetime
from math import log
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd

from common.csv_utils import export_csv

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
ANALYSIS_DIR = DATA_DIR / "analysis"
LABEL_OVERRIDES_FILE = ANALYSIS_DIR / "label_overrides.csv"
RUN_METADATA_FILE = ANALYSIS_DIR / "run_metadata.json"
SCHEMA_VERSION = "1.0"

DESTINATIONS = {
    "Hà Nội": ["hà nội", "hanoi"], "Hạ Long": ["hạ long", "ha long"],
    "Sa Pa": ["sa pa", "sapa"], "Ninh Bình": ["ninh bình", "ninh binh"],
    "Đà Nẵng": ["đà nẵng", "da nang"], "Hội An": ["hội an", "hoi an"],
    "Huế": ["huế", "hue"], "Đà Lạt": ["đà lạt", "da lat"],
    "Nha Trang": ["nha trang"], "Phú Quốc": ["phú quốc", "phu quoc"],
    "TP. Hồ Chí Minh": ["hồ chí minh", "ho chi minh", "sài gòn", "sai gon"],
    "Cần Thơ": ["cần thơ", "can tho"], "Hà Giang": ["hà giang", "ha giang"],
    "Phong Nha": ["phong nha"], "Mũi Né": ["mũi né", "mui ne"],
}
THEMES = {
    "Biển - đảo": ["biển", "beach", "đảo", "island"],
    "Văn hóa - di sản": ["di sản", "heritage", "văn hóa", "cố đô", "bảo tàng"],
    "Thiên nhiên - khám phá": ["núi", "hang", "trekking", "thiên nhiên", "thác"],
    "Ẩm thực": ["ẩm thực", "món ăn", "food", "cà phê", "coffee"],
    "Nghỉ dưỡng": ["resort", "nghỉ dưỡng", "wellness", "spa"],
    "Lễ hội - sự kiện": ["lễ hội", "festival", "sự kiện", "event"],
}
BOILERPLATE_MARKERS = (
    "gửi 0 bình luận", "bạn có thể quan tâm", "một số cẩm nang khác",
    "cần tìm khách sạn giá tốt", "đăng ký nhận tin", "bản quyền ©",
)


def clean_text(value):
    """Chuẩn hóa text đã crawl và cắt phần giao diện còn sót lại."""
    text = str(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    lowered = text.lower()
    cut_positions = [lowered.find(marker) for marker in BOILERPLATE_MARKERS if lowered.find(marker) >= 0]
    if cut_positions:
        text = text[:min(cut_positions)].strip()
    return text


def normalize_for_match(value):
    value = unicodedata.normalize("NFD", str(value or "").lower())
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def normalize_url(value):
    parts = urlsplit(str(value or "").strip())
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def label_with_evidence(title, excerpt, dictionary):
    """Gán nhãn theo điểm số; tiêu đề quan trọng hơn mô tả và lưu từ khóa khớp."""
    title_text = normalize_for_match(title)
    excerpt_text = normalize_for_match(excerpt)
    scores, evidence = {}, {}
    for label, terms in dictionary.items():
        hits = []
        score = 0
        for term in terms:
            normalized_term = normalize_for_match(term)
            title_hits = title_text.count(normalized_term)
            excerpt_hits = excerpt_text.count(normalized_term)
            if title_hits or excerpt_hits:
                score += title_hits * 3 + excerpt_hits
                hits.append(term)
        if score:
            scores[label] = score
            evidence[label] = ", ".join(hits)
    if not scores:
        return "Khác", "", 0, "needs_review"
    ranked = sorted(scores, key=lambda label: (-scores[label], label))
    best = ranked[0]
    tied = len(ranked) > 1 and scores[ranked[1]] == scores[best]
    status = "needs_review" if tied or len(ranked) > 1 else "auto"
    return best, evidence[best], scores[best], status


def apply_label_overrides(articles):
    """Áp dụng nhãn thủ công nếu nhóm đã điền label_overrides.csv."""
    if not LABEL_OVERRIDES_FILE.exists():
        return articles
    overrides = pd.read_csv(LABEL_OVERRIDES_FILE)
    if "article_id" not in overrides:
        raise ValueError("label_overrides.csv phải có cột article_id")
    overrides = overrides.drop_duplicates("article_id", keep="last").set_index("article_id")
    for field in ("destination", "travel_theme"):
        override_field = f"validated_{field}"
        if override_field in overrides:
            mapped = articles["article_id"].map(overrides[override_field])
            articles[field] = mapped.fillna(articles[field])
    return articles


def normalize_articles():
    frames = []
    for raw_file in DATA_DIR.glob("*/rawdata.csv"):
        if raw_file.parent.name == "analysis":
            continue
        frame = pd.read_csv(raw_file)
        missing = {"article_id", "title", "article_text", "source_url", "collected_at"} - set(frame.columns)
        if missing:
            raise ValueError(f"{raw_file} thiếu cột bắt buộc: {sorted(missing)}")
        if not frame.empty:
            frame["source"] = raw_file.parent.name
            frames.append(frame)
    if not frames:
        print("Không có dữ liệu bài viết để phân tích.")
        return pd.DataFrame()

    articles = pd.concat(frames, ignore_index=True, sort=False)
    for column in ["published_date", "collected_at", "title", "excerpt"]:
        if column not in articles:
            articles[column] = pd.NA
    articles["published_date"] = pd.to_datetime(articles["published_date"], errors="coerce")
    articles["collected_at"] = pd.to_datetime(articles["collected_at"], errors="coerce", utc=True)
    articles["published_year"] = articles["published_date"].dt.year.fillna(
        pd.to_numeric(articles.get("published_year"), errors="coerce")
    )
    articles["published_month"] = articles["published_date"].dt.month.fillna(
        pd.to_numeric(articles.get("published_month"), errors="coerce")
    )
    articles["view_count"] = pd.to_numeric(articles.get("view_count"), errors="coerce")
    articles["article_text_clean"] = articles["article_text"].apply(clean_text)
    articles["source_url_normalized"] = articles["source_url"].apply(normalize_url)
    articles["content_fingerprint"] = (
        articles["source"].fillna("") + "|" + articles["title"].apply(normalize_for_match) + "|" +
        articles["article_text_clean"].apply(normalize_for_match).str[:1000]
    )
    duplicate_mask = articles.duplicated("source_url_normalized", keep="first") | articles.duplicated("content_fingerprint", keep="first")
    duplicates = articles.loc[duplicate_mask, ["article_id", "source", "title", "source_url", "source_url_normalized", "content_fingerprint"]].copy()
    duplicates["duplicate_reason"] = "duplicate_url_or_content"
    export_csv(duplicates, ANALYSIS_DIR / "duplicate_articles.csv")
    articles = articles.loc[~duplicate_mask].copy()

    articles["text_for_label"] = articles["title"].fillna("") + " " + articles["excerpt"].fillna("")
    destination_labels = articles.apply(lambda row: label_with_evidence(row["title"], row["excerpt"], DESTINATIONS), axis=1)
    theme_labels = articles.apply(lambda row: label_with_evidence(row["title"], row["excerpt"], THEMES), axis=1)
    articles[["destination", "destination_evidence", "destination_score", "destination_status"]] = pd.DataFrame(destination_labels.tolist(), index=articles.index)
    articles[["travel_theme", "theme_evidence", "theme_score", "theme_status"]] = pd.DataFrame(theme_labels.tolist(), index=articles.index)
    articles = apply_label_overrides(articles)
    articles["season"] = pd.cut(
        articles["published_month"], [0, 3, 6, 9, 12], labels=["Xuân", "Hè", "Thu", "Đông"]
    )
    age = (articles["collected_at"].dt.tz_localize(None) - articles["published_date"]).dt.days
    articles["article_age_days"] = age.clip(lower=1)
    articles["views_per_day"] = articles["view_count"] / articles["article_age_days"]
    review_columns = ["article_id", "source", "title", "source_url", "destination", "destination_evidence",
                      "destination_score", "destination_status", "travel_theme", "theme_evidence", "theme_score", "theme_status"]
    review = articles[review_columns].copy()
    review["validated_destination"] = ""
    review["validated_travel_theme"] = ""
    review["review_note"] = ""
    export_csv(review, ANALYSIS_DIR / "label_review.csv")
    if not LABEL_OVERRIDES_FILE.exists():
        export_csv(review[["article_id", "validated_destination", "validated_travel_theme", "review_note"]].iloc[0:0], LABEL_OVERRIDES_FILE)
    validation_summary = pd.DataFrame([{
        "article_count": len(articles), "duplicate_removed": len(duplicates),
        "destination_needs_review": (articles["destination_status"] == "needs_review").sum(),
        "theme_needs_review": (articles["theme_status"] == "needs_review").sum(),
    }])
    export_csv(validation_summary, ANALYSIS_DIR / "label_validation_summary.csv")
    export_csv(articles, ANALYSIS_DIR / "normalized_articles.csv")
    return articles


def analyze_interest(articles):
    if articles.empty:
        return
    vntrip = articles[(articles["source"] == "VNTRIP") & (articles["destination"] != "Khác")]
    season_stats = (
        vntrip.groupby(["destination", "season"], observed=True, as_index=False)
        .agg(article_count=("article_id", "count"), total_views=("view_count", "sum"),
             median_views_per_day=("views_per_day", "median"))
    )
    export_csv(season_stats, ANALYSIS_DIR / "destination_season_stats.csv")
    theme_stats = (
        articles[articles["destination"] != "Khác"]
        .groupby(["source", "destination", "travel_theme", "season"], observed=True, as_index=False)
        .agg(article_count=("article_id", "count"), total_views=("view_count", "sum"),
             median_views_per_day=("views_per_day", "median"))
    )
    export_csv(theme_stats, ANALYSIS_DIR / "destination_theme_stats.csv")
    print(f"Đã phân tích xu hướng từ {len(articles)} nội dung.")


def analyze_snapshots():
    """Tính tăng trưởng lượt xem giữa các lần snapshot của cùng bài viết."""
    snapshot_file = DATA_DIR / "VNTRIP" / "article_snapshots.csv"
    output_file = ANALYSIS_DIR / "article_snapshot_trends.csv"
    columns = ["article_id", "snapshot_date", "view_count", "previous_snapshot_date",
               "previous_view_count", "view_delta", "days_between", "views_per_day_delta"]
    if not snapshot_file.exists():
        export_csv(pd.DataFrame(columns=columns), output_file)
        print("Chưa có snapshot lượt xem; bỏ qua phân tích tăng trưởng.")
        return
    snapshots = pd.read_csv(snapshot_file)
    required = {"article_id", "snapshot_date", "view_count"}
    missing = required - set(snapshots.columns)
    if missing:
        raise ValueError(f"article_snapshots.csv thiếu cột: {sorted(missing)}")
    snapshots["snapshot_date"] = pd.to_datetime(snapshots["snapshot_date"], errors="coerce")
    snapshots["view_count"] = pd.to_numeric(snapshots["view_count"], errors="coerce")
    snapshots = snapshots.dropna(subset=["article_id", "snapshot_date", "view_count"])
    snapshots = snapshots.sort_values(["article_id", "snapshot_date"]).drop_duplicates(
        ["article_id", "snapshot_date"], keep="last"
    )
    snapshots["previous_snapshot_date"] = snapshots.groupby("article_id")["snapshot_date"].shift()
    snapshots["previous_view_count"] = snapshots.groupby("article_id")["view_count"].shift()
    snapshots["view_delta"] = snapshots["view_count"] - snapshots["previous_view_count"]
    snapshots["days_between"] = (snapshots["snapshot_date"] - snapshots["previous_snapshot_date"]).dt.days
    snapshots["views_per_day_delta"] = snapshots["view_delta"] / snapshots["days_between"]
    trends = snapshots.dropna(subset=["previous_snapshot_date"]).copy()
    trends = trends[(trends["days_between"] > 0) & (trends["view_delta"] >= 0)]
    trends["snapshot_date"] = trends["snapshot_date"].dt.date
    trends["previous_snapshot_date"] = trends["previous_snapshot_date"].dt.date
    export_csv(trends[columns], output_file)
    print(f"Đã tạo {output_file.name} từ {len(trends)} khoảng snapshot hợp lệ.")


def scale_to_100(series):
    """Chuẩn hóa một chỉ số thành 0–100, xử lý trường hợp chỉ có một giá trị."""
    values = pd.to_numeric(series, errors="coerce")
    if values.notna().sum() == 0:
        return pd.Series(0.0, index=series.index)
    low, high = values.min(), values.max()
    if low == high:
        return pd.Series(100.0, index=series.index)
    return (values - low) / (high - low) * 100


def build_opportunity_scores():
    """Chấm điểm cơ hội từ mức quan tâm của nội dung HTML đã parse."""
    interest_file = ANALYSIS_DIR / "destination_season_stats.csv"
    output_file = ANALYSIS_DIR / "destination_opportunity_scores.csv"
    if not interest_file.exists():
        print("Chưa có dữ liệu quan tâm để tính điểm cơ hội.")
        return pd.DataFrame()
    interest = pd.read_csv(interest_file)
    if interest.empty:
        export_csv(pd.DataFrame(), output_file)
        return pd.DataFrame()
    scores = interest.groupby("destination", as_index=False).agg(
        article_count=("article_count", "sum"), total_views=("total_views", "sum"),
        median_views_per_day=("median_views_per_day", "median"),
    )
    scores["interest_score"] = (
        scale_to_100(scores["median_views_per_day"].clip(lower=0).add(1).map(log)) * 0.70
        + scale_to_100(scores["article_count"]) * 0.30
    )
    trends_file = ANALYSIS_DIR / "article_snapshot_trends.csv"
    normalized_file = ANALYSIS_DIR / "normalized_articles.csv"
    scores["latest_views_growth"] = 0.0
    if trends_file.exists() and normalized_file.exists():
        trends = pd.read_csv(trends_file)
        normalized = pd.read_csv(normalized_file, usecols=["article_id", "destination"])
        if not trends.empty and {"article_id", "snapshot_date", "views_per_day_delta"}.issubset(trends.columns):
            latest_date = pd.to_datetime(trends["snapshot_date"], errors="coerce").max()
            latest = trends[pd.to_datetime(trends["snapshot_date"], errors="coerce") == latest_date]
            growth = latest.merge(normalized, on="article_id", how="left").dropna(subset=["destination"])
            growth = growth.groupby("destination", as_index=False).agg(
                latest_views_growth=("views_per_day_delta", "sum")
            )
            scores = scores.drop(columns="latest_views_growth").merge(growth, on="destination", how="left")
            scores["latest_views_growth"] = scores["latest_views_growth"].fillna(0)
    scores["opportunity_score"] = scores["interest_score"]
    scores["score_basis"] = "Dữ liệu nội dung trực tuyến"

    def recommendation(row):
        if row["latest_views_growth"] >= 50:
            return "Nhu cầu đang tăng nhanh: triển khai nội dung và chiến dịch ngay."
        if row["interest_score"] >= 60:
            return "Ưu tiên nội dung, chiến dịch và sản phẩm theo mùa."
        if row["interest_score"] >= 35:
            return "Theo dõi theo mùa và mở rộng nhóm bài viết liên quan."
        return "Tăng số bài và theo dõi thêm trước khi ưu tiên đầu tư."

    scores["recommendation"] = scores.apply(recommendation, axis=1)
    scores = scores.sort_values("opportunity_score", ascending=False).reset_index(drop=True)
    numeric_columns = ["total_views", "median_views_per_day", "latest_views_growth", "interest_score", "opportunity_score"]
    scores[numeric_columns] = scores[numeric_columns].round(2)
    export_csv(scores, output_file)
    print(f"Đã tạo {output_file.name} cho {len(scores)} điểm đến.")
    return scores


def write_run_metadata(articles):
    """Tổng hợp manifest crawler; quality gate dùng tệp này để kiểm tra độ mới dữ liệu."""
    sources = {}
    for source_dir in DATA_DIR.iterdir():
        manifest_file = source_dir / "crawl_manifest.json"
        if source_dir.is_dir() and manifest_file.exists():
            try:
                sources[source_dir.name] = json.loads(manifest_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise ValueError(f"Manifest không hợp lệ: {manifest_file}: {error}") from error
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "normalized_article_count": int(len(articles)),
        "sources": sources,
    }
    RUN_METADATA_FILE.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã tạo {RUN_METADATA_FILE.name} với {len(sources)} manifest nguồn.")


if __name__ == "__main__":
    ANALYSIS_DIR.mkdir(exist_ok=True)
    articles = normalize_articles()
    analyze_interest(articles)
    analyze_snapshots()
    build_opportunity_scores()
    write_run_metadata(articles)

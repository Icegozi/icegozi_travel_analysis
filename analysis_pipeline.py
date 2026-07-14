"""Chạy tự động các phân tích dữ liệu du lịch không cần mở notebook."""

import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
ANALYSIS_DIR = DATA_DIR / "analysis"
LABEL_OVERRIDES_FILE = ANALYSIS_DIR / "label_overrides.csv"

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
RATING_COLUMNS = [
    "overall_rating", "landscape_rating", "service_rating", "price_rating",
    "food_rating", "transport_rating", "safety_rating", "cleanliness_rating",
]
FACTOR_COLUMNS = RATING_COLUMNS[1:]


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
    duplicates.to_csv(ANALYSIS_DIR / "duplicate_articles.csv", encoding="utf-8-sig", index=False)
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
    review.to_csv(ANALYSIS_DIR / "label_review.csv", encoding="utf-8-sig", index=False)
    if not LABEL_OVERRIDES_FILE.exists():
        review[["article_id", "validated_destination", "validated_travel_theme", "review_note"]].iloc[0:0].to_csv(
            LABEL_OVERRIDES_FILE, encoding="utf-8-sig", index=False
        )
    validation_summary = pd.DataFrame([{
        "article_count": len(articles), "duplicate_removed": len(duplicates),
        "destination_needs_review": (articles["destination_status"] == "needs_review").sum(),
        "theme_needs_review": (articles["theme_status"] == "needs_review").sum(),
    }])
    validation_summary.to_csv(ANALYSIS_DIR / "label_validation_summary.csv", encoding="utf-8-sig", index=False)
    articles.to_csv(ANALYSIS_DIR / "normalized_articles.csv", encoding="utf-8-sig", index=False)
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
    season_stats.to_csv(ANALYSIS_DIR / "destination_season_stats.csv", encoding="utf-8-sig", index=False)
    theme_stats = (
        articles[articles["destination"] != "Khác"]
        .groupby(["source", "destination", "travel_theme", "season"], observed=True, as_index=False)
        .agg(article_count=("article_id", "count"), total_views=("view_count", "sum"),
             median_views_per_day=("views_per_day", "median"))
    )
    theme_stats.to_csv(ANALYSIS_DIR / "destination_theme_stats.csv", encoding="utf-8-sig", index=False)
    print(f"Đã phân tích xu hướng từ {len(articles)} nội dung.")


def analyze_survey():
    survey_file = DATA_DIR / "SURVEY" / "tourist_survey.csv"
    survey = pd.read_csv(survey_file)
    if survey.empty:
        print("Chưa có phản hồi khảo sát; bỏ qua phân tích đánh giá.")
        return pd.DataFrame()
    clean = survey.copy()
    for column in RATING_COLUMNS:
        clean[column] = pd.to_numeric(clean[column], errors="coerce")
    answers = {"có": 1, "co": 1, "yes": 1, "1": 1, "không": 0, "khong": 0, "no": 0, "0": 0}
    clean["revisit_binary"] = clean["revisit_intention"].astype(str).str.lower().map(answers)
    clean["recommend_binary"] = clean["recommend_intention"].astype(str).str.lower().map(answers)
    clean = clean.dropna(subset=["destination", "overall_rating"])
    clean.to_csv(ANALYSIS_DIR / "tourist_survey_clean.csv", encoding="utf-8-sig", index=False)
    stats = (
        clean.groupby("destination", as_index=False)
        .agg(respondent_count=("respondent_id", "count"),
             average_overall_rating=("overall_rating", "mean"),
             revisit_rate=("revisit_binary", "mean"), recommend_rate=("recommend_binary", "mean"))
    )
    stats.to_csv(ANALYSIS_DIR / "destination_rating_stats.csv", encoding="utf-8-sig", index=False)
    model_data = clean.dropna(subset=FACTOR_COLUMNS + ["revisit_binary"])
    if len(model_data) >= 30 and model_data["revisit_binary"].nunique() == 2:
        X = StandardScaler().fit_transform(model_data[FACTOR_COLUMNS])
        model = LogisticRegression(max_iter=1000, random_state=365).fit(X, model_data["revisit_binary"])
        coefficients = pd.DataFrame({"factor": FACTOR_COLUMNS, "coefficient": model.coef_[0]})
        coefficients.sort_values("coefficient", ascending=False).to_csv(
            ANALYSIS_DIR / "revisit_factor_coefficients.csv", encoding="utf-8-sig", index=False
        )
    else:
        print("Cần tối thiểu 30 phản hồi hợp lệ để mô hình hóa ý định quay lại.")
    return stats


def combine_results():
    interest_file = ANALYSIS_DIR / "destination_season_stats.csv"
    rating_file = ANALYSIS_DIR / "destination_rating_stats.csv"
    if not interest_file.exists() or not rating_file.exists():
        print("Chưa đủ dữ liệu để tổng hợp xu hướng và đánh giá.")
        return
    interest = pd.read_csv(interest_file)
    ratings = pd.read_csv(rating_file)
    summary = interest.groupby("destination", as_index=False).agg(
        article_count=("article_count", "sum"), total_views=("total_views", "sum"),
        median_views_per_day=("median_views_per_day", "median")
    ).merge(ratings, on="destination", how="outer")
    summary.to_csv(ANALYSIS_DIR / "destination_combined_summary.csv", encoding="utf-8-sig", index=False)
    print("Đã tạo destination_combined_summary.csv")


if __name__ == "__main__":
    ANALYSIS_DIR.mkdir(exist_ok=True)
    articles = normalize_articles()
    analyze_interest(articles)
    if os.getenv("RUN_SURVEY_ANALYSIS", "1") == "1":
        analyze_survey()
    if os.getenv("RUN_COMBINED_ANALYSIS", "1") == "1":
        combine_results()

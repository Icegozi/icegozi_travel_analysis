"""Thu thập bài viết/điểm đến công khai từ Vietnam.travel khi robots.txt cho phép."""

import hashlib
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

# Hỗ trợ chạy trực tiếp từ workflow hoặc terminal mà vẫn import được common/.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.config import crawler_limits
from common.csv_utils import export_csv
from common.http_client import CrawlHttpClient
from common.run_manifest import CrawlReport

BASE_URL = "https://vietnam.travel"
# Trang danh mục hiện dùng `place-to-go` (số ít), còn URL trang chi tiết
# vẫn dùng `/places-to-go/<region>/<destination>`.
CATEGORY_URLS = [BASE_URL + "/things-to-do", BASE_URL + "/place-to-go"]
LIMITS = crawler_limits("VIETNAM_TRAVEL", default_pages=50, default_new_articles=300)
DATA_DIR = ROOT_DIR / "data" / "VIETNAM_TRAVEL"
RAW_FILE = DATA_DIR / "rawdata.csv"
LINKS_FILE = DATA_DIR / "links_vietnam_travel.csv"
MANIFEST_FILE = DATA_DIR / "crawl_manifest.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TourismResearchBot/1.0)"}
RAW_COLUMNS = [
    "article_id", "content_type", "title", "published_date", "published_year", "published_month",
    "excerpt", "article_text", "source_url", "image_url", "collected_at",
]


def parse_iso_date(value):
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", value or "")
    if not match:
        return "", "", ""
    year, month, day = map(int, match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}", year, month


def is_content_url(url):
    parsed = urlparse(url)
    return parsed.netloc in {"vietnam.travel", "www.vietnam.travel"} and (
        parsed.path.startswith("/things-to-do/") or parsed.path.startswith("/places-to-go/")
    )


def get_content_links(soup):
    links = []
    for anchor in soup.select("a[href]"):
        url = urljoin(BASE_URL, anchor["href"]).split("#")[0]
        if is_content_url(url) and url not in links:
            links.append(url)
    return links


def parse_content(soup, url):
    title = soup.select_one("h1")
    content = soup.select_one(".article-content, .entry-content, .post-content") or soup.select_one("article") or soup.select_one("main") or soup.body
    if content:
        for node in content.select("nav, header, footer, aside, form, script, style, noscript, "
                                   ".related, .related-post, .sidebar, .comments, .share, "
                                   ".social-share, .newsletter, .advertisement, .ads"):
            node.decompose()
    text = content.get_text(" ", strip=True) if content else ""
    published_meta = soup.select_one('meta[property="article:published_time"], meta[name="date"]')
    published_date, year, month = parse_iso_date(published_meta.get("content", "") if published_meta else "")
    description = soup.select_one('meta[name="description"]')
    image = soup.select_one('meta[property="og:image"]')
    content_type = "destination" if "/places-to-go/" in url else "article"
    return {
        "article_id": "VIETNAM_TRAVEL_" + hashlib.sha1(url.encode()).hexdigest()[:12],
        "content_type": content_type,
        "title": title.get_text(" ", strip=True) if title else "",
        "published_date": published_date,
        "published_year": year,
        "published_month": month,
        "excerpt": description.get("content", "").strip() if description else "",
        "article_text": text,
        "source_url": url,
        "image_url": image.get("content", "") if image else "",
        "collected_at": datetime.now(UTC).isoformat(),
    }


def load_existing_records():
    """Nạp dữ liệu cũ theo URL để không parse lại bài đã thu thập."""
    if not RAW_FILE.exists():
        return {}
    frame = pd.read_csv(RAW_FILE)
    if "source_url" not in frame:
        return {}
    frame = frame.dropna(subset=["source_url"]).drop_duplicates("source_url", keep="last")
    return {row["source_url"]: row.reindex(RAW_COLUMNS).to_dict() for _, row in frame.iterrows()}


def load_existing_links():
    if not LINKS_FILE.exists():
        return []
    frame = pd.read_csv(LINKS_FILE)
    columns = ["category_url", "listing_page", "source_url"]
    if not set(columns).issubset(frame.columns):
        return []
    return frame[columns].dropna(subset=["source_url"]).to_dict(orient="records")


def save_outputs(records, links):
    frame = pd.DataFrame(records.values(), columns=RAW_COLUMNS)
    export_csv(frame, RAW_FILE)
    link_frame = pd.DataFrame(links, columns=["category_url", "listing_page", "source_url"])
    export_csv(link_frame.drop_duplicates("source_url", keep="last"), LINKS_FILE)
    return frame


def crawl():
    """Chỉ parse URL mới; dữ liệu cũ được giữ lại và không tạo dòng trùng."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = CrawlHttpClient(HEADERS["User-Agent"], LIMITS.delay_seconds, LIMITS.timeout_seconds, LIMITS.retries)
    records = load_existing_records()
    links = load_existing_links()
    report = CrawlReport(source="VIETNAM_TRAVEL")
    seen_urls, new_article_count = set(), 0
    for category_url in CATEGORY_URLS:
        for page in range(LIMITS.max_pages):
            if new_article_count >= LIMITS.max_new_articles:
                break
            list_url = category_url if page == 0 else f"{category_url}?page={page}"
            print(f"Trang {page + 1}: {list_url}")
            try:
                content_urls = get_content_links(client.get_soup(list_url))
            except (requests.RequestException, PermissionError) as error:
                print(f"  Bỏ qua trang danh mục do lỗi: {error}")
                report.errors.append(f"Danh mục {list_url}: {error}")
                break
            report.listing_pages_seen += 1
            report.urls_discovered += len(content_urls)
            if not content_urls:
                break
            page_urls = [url for url in content_urls if url not in seen_urls]
            if not page_urls:
                continue
            for url in page_urls:
                if new_article_count >= LIMITS.max_new_articles:
                    break
                seen_urls.add(url)
                links.append({"category_url": category_url, "listing_page": page + 1, "source_url": url})
                if url in records:
                    report.existing_urls += 1
                    print(f"  Đã có dữ liệu: {url}")
                    continue
                print(f"  {url}")
                try:
                    records[url] = parse_content(client.get_soup(url), url)
                    new_article_count += 1
                    report.new_records += 1
                except (requests.RequestException, PermissionError) as error:
                    report.errors.append(f"Nội dung {url}: {error}")
                    print(f"  Bỏ qua nội dung do lỗi: {error}")

    frame = save_outputs(records, links)
    report.write(MANIFEST_FILE)
    print(f"Đã thêm {new_article_count} nội dung mới; tổng cộng {len(frame)} nội dung trong {RAW_FILE}")


if __name__ == "__main__":
    crawl()

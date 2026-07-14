"""Thu thập bài viết/điểm đến công khai từ Vietnam.travel khi robots.txt cho phép."""

import hashlib
import os
import re
import time
import urllib.robotparser
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://vietnam.travel"
# Trang danh mục hiện dùng `place-to-go` (số ít), còn URL trang chi tiết
# vẫn dùng `/places-to-go/<region>/<destination>`.
CATEGORY_URLS = [BASE_URL + "/things-to-do", BASE_URL + "/place-to-go"]
MAX_PAGES = int(os.getenv("VIETNAM_TRAVEL_MAX_PAGES", "50"))
MAX_ARTICLES = int(os.getenv("VIETNAM_TRAVEL_MAX_ARTICLES", "300"))
REQUEST_DELAY_SECONDS = float(os.getenv("VIETNAM_TRAVEL_DELAY_SECONDS", "3"))
HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "VIETNAM_TRAVEL"
RAW_FILE = DATA_DIR / "rawdata.csv"
LINKS_FILE = DATA_DIR / "links_vietnam_travel.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TourismResearchBot/1.0)"}
ROBOTS = None
RAW_COLUMNS = [
    "article_id", "content_type", "title", "published_date", "published_year", "published_month",
    "excerpt", "article_text", "source_url", "image_url", "collected_at",
]


def export_csv(df, output_file):
    """Xuất CSV UTF-8 BOM, dùng dấu phẩy để tương thích Excel."""
    df.to_csv(output_file, index=False, sep=",", encoding="utf-8-sig")


def allowed_by_robots(url):
    global ROBOTS
    if ROBOTS is None:
        ROBOTS = urllib.robotparser.RobotFileParser()
        ROBOTS.set_url(BASE_URL + "/robots.txt")
        ROBOTS.read()
    return ROBOTS.can_fetch(HEADERS["User-Agent"], url)


def get_soup(session, url):
    if not allowed_by_robots(url):
        raise PermissionError(f"robots.txt không cho phép thu thập: {url}")
    response = session.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return BeautifulSoup(response.text, "html.parser")


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


def crawl():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    rows, links, seen_urls = [], [], set()
    for category_url in CATEGORY_URLS:
        for page in range(MAX_PAGES):
            if len(rows) >= MAX_ARTICLES:
                break
            list_url = category_url if page == 0 else f"{category_url}?page={page}"
            print(f"Trang {page + 1}: {list_url}")
            try:
                content_urls = get_content_links(get_soup(session, list_url))
            except (requests.RequestException, PermissionError) as error:
                print(f"  Bỏ qua trang danh mục do lỗi: {error}")
                break
            if not content_urls:
                break
            new_urls = [url for url in content_urls if url not in seen_urls]
            if not new_urls:
                break
            for url in new_urls:
                if len(rows) >= MAX_ARTICLES:
                    break
                seen_urls.add(url)
                links.append({"category_url": category_url, "listing_page": page + 1, "source_url": url})
                print(f"  {url}")
                try:
                    rows.append(parse_content(get_soup(session, url), url))
                except (requests.RequestException, PermissionError) as error:
                    print(f"  Bỏ qua nội dung do lỗi: {error}")

    export_csv(pd.DataFrame(rows, columns=RAW_COLUMNS), RAW_FILE)
    export_csv(pd.DataFrame(links, columns=["category_url", "listing_page", "source_url"]), LINKS_FILE)
    print(f"Đã lưu {len(rows)} nội dung vào {RAW_FILE}")


if __name__ == "__main__":
    crawl()

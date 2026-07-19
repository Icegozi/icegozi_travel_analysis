"""Thu thập có giới hạn nội dung công khai từ các cổng du lịch địa phương."""

import hashlib
import re
import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pandas as pd
import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.config import crawler_limits
from common.csv_utils import export_csv
from common.http_client import CrawlHttpClient
from common.run_manifest import CrawlReport

SOURCES = {
    "Hà Nội": "https://sodulich.hanoi.gov.vn/", "Quảng Ninh": "https://dulich.quangninh.gov.vn/",
    "Ninh Bình": "https://visitninhbinh.com.vn/", "Thanh Hóa": "https://thanhhoa.travel/",
    "Huế": "https://visithue.vn/", "Đà Nẵng": "https://danangfantasticity.com/",
    "Quảng Nam": "https://quangnamtourism.com.vn/", "Lâm Đồng": "https://visitlamdong.vn/",
    "Bà Rịa - Vũng Tàu": "https://diemden.baria-vungtau.gov.vn/", "Cần Thơ": "https://canthotourism.vn/",
}
LIMITS = crawler_limits("PORTALS", default_pages=20, default_new_articles=100)
DATA_DIR = ROOT_DIR / "data" / "PROVINCIAL_PORTALS"
RAW_FILE, LINKS_FILE, MANIFEST_FILE = DATA_DIR / "rawdata.csv", DATA_DIR / "links_portals.csv", DATA_DIR / "crawl_manifest.json"
HEADERS = {"User-Agent": "TourismResearchBot/1.0 (+research; respectful robots.txt)"}
RAW_COLUMNS = ["article_id", "portal_province", "portal_home", "title", "published_date", "excerpt", "article_text", "source_url", "image_url", "collected_at"]


def same_site(url, home):
    return urlsplit(url).netloc.lower() == urlsplit(home).netloc.lower()


def article_links(soup, home):
    """Lấy các liên kết có văn bản như một bài viết, không giả định CMS cụ thể."""
    links = []
    ignored = ("#", "javascript:", "mailto:", "/tag/", "/category/", "/contact", "/login", "/search")
    for anchor in soup.select("a[href]"):
        text = anchor.get_text(" ", strip=True)
        url = urljoin(home, anchor["href"]).split("#")[0]
        path = urlsplit(url).path.lower()
        if len(text) < 24 or not same_site(url, home) or any(item in url.lower() for item in ignored) or path in {"", "/"}:
            continue
        if url not in links:
            links.append(url)
    return links


def pagination_links(soup, home):
    """Nhận diện phân trang phổ biến; chỉ theo liên kết cùng domain."""
    links = []
    for anchor in soup.select("a[href]"):
        url = urljoin(home, anchor["href"]).split("#")[0]
        text = anchor.get_text(" ", strip=True).lower()
        if not same_site(url, home):
            continue
        if re.search(r"(?:[?&](?:page|paged|p)=|/page/|/trang/)", url.lower()) or text in {"next", "sau", "trang sau", ">", ">>"}:
            if url not in links:
                links.append(url)
    return links


def parse_date(soup, text):
    meta = soup.select_one('meta[property="article:published_time"], meta[name="date"], meta[name="publishdate"]')
    value = meta.get("content", "") if meta else text
    iso = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", value)
    if iso:
        year, month, day = map(int, iso.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    vietnamese = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](20\d{2})", value)
    if vietnamese:
        day, month, year = map(int, vietnamese.groups())
        return f"{year:04d}-{month:02d}-{day:02d}"
    return ""


def parse_article(soup, province, home, url):
    title = soup.select_one("h1")
    content = soup.select_one("article, main, .entry-content, .post-content, .article-content") or soup.body
    if content:
        for node in content.select("nav, header, footer, aside, form, script, style, noscript, .related, .sidebar, .share, .social"):
            node.decompose()
    text = content.get_text(" ", strip=True) if content else ""
    description = soup.select_one('meta[name="description"]')
    image = soup.select_one('meta[property="og:image"]')
    return {"article_id": "PORTAL_" + hashlib.sha1(url.encode()).hexdigest()[:12], "portal_province": province,
            "portal_home": home, "title": title.get_text(" ", strip=True) if title else "", "published_date": parse_date(soup, text),
            "excerpt": description.get("content", "").strip() if description else "", "article_text": text,
            "source_url": url, "image_url": image.get("content", "") if image else "", "collected_at": datetime.now(UTC).isoformat()}


def crawl():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    existing = pd.read_csv(RAW_FILE).set_index("source_url").to_dict("index") if RAW_FILE.exists() else {}
    links, report = [], CrawlReport(source="PROVINCIAL_PORTALS")
    client = CrawlHttpClient(HEADERS["User-Agent"], LIMITS.delay_seconds, LIMITS.timeout_seconds, LIMITS.retries)
    per_source_limit = max(1, LIMITS.max_new_articles // len(SOURCES))
    # Giống VNTRIP/VIETNAM_TRAVEL: MAX_PAGES là ngân sách listing toàn crawler.
    # Khởi tạo trang đầu của mọi cổng trước để dữ liệu không bị lệch về nguồn đầu tiên.
    listing_queue = deque((province, home, home) for province, home in SOURCES.items())
    seen_listings = {province: set() for province in SOURCES}
    candidates_by_source = {province: [] for province in SOURCES}
    while listing_queue and report.listing_pages_seen < LIMITS.max_pages:
        province, home, listing_url = listing_queue.popleft()
        if listing_url in seen_listings[province]:
            continue
        print(f"[Listing {report.listing_pages_seen + 1}/{LIMITS.max_pages}] {province}: {listing_url}", flush=True)
        try:
            listing_soup = client.get_soup(listing_url)
        except (requests.RequestException, PermissionError) as error:
            report.errors.append(f"{province} {listing_url}: {error}")
            print(f"  Bỏ qua: {error}", flush=True)
            continue
        seen_listings[province].add(listing_url)
        report.listing_pages_seen += 1
        page_candidates = article_links(listing_soup, home)
        candidates_by_source[province].extend(page_candidates)
        report.urls_discovered += len(page_candidates)
        for page_url in pagination_links(listing_soup, home):
            if page_url not in seen_listings[province]:
                listing_queue.append((province, home, page_url))

    for province, home in SOURCES.items():
        candidates = list(dict.fromkeys(candidates_by_source[province]))
        for url in candidates[:per_source_limit]:
            links.append({"portal_province": province, "portal_home": home, "source_url": url})
            if url in existing:
                report.existing_urls += 1
                continue
            try:
                print(f"[Bài mới] {province}: {url}", flush=True)
                existing[url] = parse_article(client.get_soup(url), province, home, url)
                report.new_records += 1
            except (requests.RequestException, PermissionError) as error:
                report.errors.append(f"{province} {url}: {error}")
                print(f"  Bỏ qua: {error}", flush=True)
    export_csv(pd.DataFrame(existing.values(), columns=RAW_COLUMNS), RAW_FILE)
    export_csv(pd.DataFrame(links, columns=["portal_province", "portal_home", "source_url"]).drop_duplicates(), LINKS_FILE)
    report.write(MANIFEST_FILE)
    print(f"Đã lưu {report.new_records} bài mới từ cổng du lịch địa phương; tổng: {len(existing)}")


if __name__ == "__main__":
    crawl()

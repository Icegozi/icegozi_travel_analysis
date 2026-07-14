"""Thu thập bài viết công khai từ Vntrip Cẩm nang một cách có giới hạn."""

import hashlib
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests

# Khi chạy trực tiếp `python VNTRIP/crawl_vntrip.py`, Python chỉ thêm thư mục
# VNTRIP vào sys.path. Bổ sung thư mục gốc để import được package common.
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common.config import crawler_limits
from common.csv_utils import export_csv
from common.http_client import CrawlHttpClient
from common.run_manifest import CrawlReport

BASE_URL = "https://www.vntrip.vn"
LIST_URL = BASE_URL + "/cam-nang/du-lich"
LIMITS = crawler_limits("VNTRIP", default_pages=50, default_new_articles=500)
DATA_DIR = ROOT_DIR / "data" / "VNTRIP"
RAW_FILE = DATA_DIR / "rawdata.csv"
LINKS_FILE = DATA_DIR / "links_vntrip.csv"
SNAPSHOTS_FILE = DATA_DIR / "article_snapshots.csv"
MONTHLY_STATS_FILE = DATA_DIR / "monthly_article_stats.csv"
MANIFEST_FILE = DATA_DIR / "crawl_manifest.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TourismResearchBot/1.0)"}

RAW_COLUMNS = [
    "article_id", "title", "published_date", "published_year", "published_month",
    "view_count", "excerpt", "article_text", "source_url", "image_url", "collected_at",
]


def parse_date(text):
    match = re.search(r"\b(\d{1,2})\s+Th(\d{1,2}),\s*(\d{4})\b", text, re.I)
    if not match:
        return "", "", ""
    day, month, year = map(int, match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}", year, month


def parse_view_count(text):
    match = re.search(r"([\d.,]+)\s*([KkMm]?)\s+lượt xem", text)
    if not match:
        return ""
    number, suffix = match.groups()
    if suffix:
        multiplier = 1_000 if suffix.lower() == "k" else 1_000_000
        return round(float(number.replace(",", ".")) * multiplier)
    return int(re.sub(r"[.,]", "", number))


def get_article_cards(soup):
    """Lấy URL, ngày đăng và lượt xem hiển thị tại trang danh mục."""
    cards = {}
    for heading in soup.select("h2, h3, h4"):
        anchor = heading.select_one("a[href]")
        if not anchor:
            continue
        url = urljoin(BASE_URL, anchor["href"])
        if "/cam-nang/" not in url:
            continue
        container = heading.find_parent(["article", "li"]) or heading.parent
        text = container.get_text(" ", strip=True) if container else heading.get_text(" ", strip=True)
        date, year, month = parse_date(text)
        cards[url] = {
            "title": heading.get_text(" ", strip=True),
            "published_date": date,
            "published_year": year,
            "published_month": month,
            "view_count": parse_view_count(text),
            "source_url": url,
        }
    return list(cards.values())


def parse_article(soup, card):
    """Kết hợp metadata danh mục và nội dung chi tiết thành một dòng dữ liệu."""
    title = soup.select_one("h1")
    # Chỉ giữ phần thân bài.  Các khối giao diện thường nằm trong article trên
    # VNTRIP nên cần loại chúng trước khi lấy text.
    content = soup.select_one(".entry-content, .post-content, .article-content") or soup.select_one("article") or soup.body
    if content:
        for node in content.select("nav, header, footer, aside, form, script, style, noscript, "
                                   ".related, .related-post, .sidebar, .comments, .comment, "
                                   ".share, .social-share, .newsletter, .advertisement, .ads"):
            node.decompose()
    text = content.get_text(" ", strip=True) if content else ""
    date, year, month = parse_date(text)
    image = soup.select_one('meta[property="og:image"]')
    description = soup.select_one('meta[name="description"]')
    return {
        "article_id": "VNTRIP_" + hashlib.sha1(card["source_url"].encode()).hexdigest()[:12],
        "title": title.get_text(" ", strip=True) if title else card["title"],
        "published_date": card["published_date"] or date,
        "published_year": card["published_year"] or year,
        "published_month": card["published_month"] or month,
        "view_count": card["view_count"] or parse_view_count(text),
        "excerpt": description.get("content", "").strip() if description else "",
        "article_text": text,
        "source_url": card["source_url"],
        "image_url": image.get("content", "") if image else "",
        "collected_at": datetime.now(UTC).isoformat(),
    }


def load_existing_records():
    if not RAW_FILE.exists():
        return {}
    frame = pd.read_csv(RAW_FILE)
    return {row["source_url"]: row.to_dict() for _, row in frame.iterrows() if row["source_url"]}


def save_outputs(records, links):
    frame = pd.DataFrame(records.values(), columns=RAW_COLUMNS)
    frame["view_count"] = pd.to_numeric(frame["view_count"], errors="coerce")
    frame["published_year"] = pd.to_numeric(frame["published_year"], errors="coerce")
    frame["published_month"] = pd.to_numeric(frame["published_month"], errors="coerce")
    export_csv(frame, RAW_FILE)
    export_csv(pd.DataFrame(links, columns=["listing_page", "source_url"]).drop_duplicates(), LINKS_FILE)
    return frame


def save_snapshots(frame):
    snapshot_date = datetime.now(UTC).date().isoformat()
    snapshots = frame[["article_id", "source_url", "view_count", "collected_at"]].copy()
    snapshots.insert(1, "snapshot_date", snapshot_date)
    if SNAPSHOTS_FILE.exists():
        snapshots = pd.concat([pd.read_csv(SNAPSHOTS_FILE), snapshots], ignore_index=True)
    export_csv(snapshots.drop_duplicates(["article_id", "snapshot_date"], keep="last"), SNAPSHOTS_FILE)


def save_monthly_stats(frame):
    statistics = (
        frame.dropna(subset=["published_year", "published_month"])
        .groupby(["published_year", "published_month"], as_index=False)
        .agg(article_count=("article_id", "count"), total_view_count=("view_count", "sum"),
             average_view_count=("view_count", "mean"))
    )
    export_csv(statistics, MONTHLY_STATS_FILE)


def crawl():
    """Crawl tối đa số bài *mới*, vẫn giữ dữ liệu đã có và lưu báo cáo lần chạy."""
    DATA_DIR.mkdir(exist_ok=True)
    records = load_existing_records()
    links = []
    report = CrawlReport(source="VNTRIP")
    client = CrawlHttpClient(HEADERS["User-Agent"], LIMITS.delay_seconds, LIMITS.timeout_seconds, LIMITS.retries)
    new_article_count = 0
    for page in range(1, LIMITS.max_pages + 1):
        if new_article_count >= LIMITS.max_new_articles:
            break
        # VNTRIP dùng đường dẫn /page/<n>, không dùng query ?page=<n>.
        # Query cũ luôn trả về danh sách trang đầu nên chỉ thu được các URL trùng nhau.
        listing_url = LIST_URL if page == 1 else f"{LIST_URL}/page/{page}"
        print(f"Trang {page}: {listing_url}")
        try:
            cards = get_article_cards(client.get_soup(listing_url))
        except (requests.RequestException, PermissionError) as error:
            report.errors.append(f"Danh mục {listing_url}: {error}")
            print(f"  Bỏ qua trang danh mục do lỗi: {error}")
            break
        report.listing_pages_seen += 1
        report.urls_discovered += len(cards)
        if not cards:
            print("Không còn bài viết ở trang này.")
            break
        new_urls = sum(card["source_url"] not in records for card in cards)
        print(f"  Phát hiện {len(cards)} bài viết, trong đó có {new_urls} URL mới.")
        for card in cards:
            links.append({"listing_page": page, "source_url": card["source_url"]})
            if card["source_url"] in records:
                report.existing_urls += 1
                records[card["source_url"]].update({
                    key: value for key, value in card.items() if value not in ("", None)
                })
                records[card["source_url"]]["collected_at"] = datetime.now(UTC).isoformat()
                continue
            print(f"  {card['source_url']}")
            try:
                records[card["source_url"]] = parse_article(client.get_soup(card["source_url"]), card)
                new_article_count += 1
                report.new_records += 1
            except (requests.RequestException, PermissionError) as error:
                report.errors.append(f"Nội dung {card['source_url']}: {error}")
                print(f"  Bỏ qua nội dung do lỗi: {error}")
            if new_article_count >= LIMITS.max_new_articles:
                break
        save_outputs(records, links)

    frame = save_outputs(records, links)
    save_snapshots(frame)
    save_monthly_stats(frame)
    report.write(MANIFEST_FILE)
    print(f"Đã lưu {len(frame)} bài viết vào {RAW_FILE}")


if __name__ == "__main__":
    crawl()

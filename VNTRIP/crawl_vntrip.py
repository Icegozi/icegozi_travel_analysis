"""Thu thập bài viết công khai từ Vntrip Cẩm nang một cách có giới hạn."""

import hashlib
import os
import re
import time
import urllib.robotparser
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.vntrip.vn"
LIST_URL = BASE_URL + "/cam-nang/du-lich"
MAX_PAGES = int(os.getenv("VNTRIP_MAX_PAGES", "50"))
MAX_ARTICLES = int(os.getenv("VNTRIP_MAX_ARTICLES", "500"))
REQUEST_DELAY_SECONDS = float(os.getenv("VNTRIP_DELAY_SECONDS", "3"))
HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "VNTRIP"
RAW_FILE = DATA_DIR / "rawdata.csv"
LINKS_FILE = DATA_DIR / "links_vntrip.csv"
SNAPSHOTS_FILE = DATA_DIR / "article_snapshots.csv"
MONTHLY_STATS_FILE = DATA_DIR / "monthly_article_stats.csv"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TourismResearchBot/1.0)"}
ROBOTS = None

RAW_COLUMNS = [
    "article_id", "title", "published_date", "published_year", "published_month",
    "view_count", "excerpt", "article_text", "source_url", "image_url", "collected_at",
]


def allowed_by_robots(url):
    global ROBOTS
    if ROBOTS is None:
        ROBOTS = urllib.robotparser.RobotFileParser()
        ROBOTS.set_url(BASE_URL + "/robots.txt")
        ROBOTS.read()
    return ROBOTS.can_fetch(HEADERS["User-Agent"], url)


def getdata(session, url):
    """Tải một trang sau khi kiểm tra robots.txt và giới hạn tốc độ."""
    if not allowed_by_robots(url):
        raise PermissionError(f"robots.txt không cho phép thu thập: {url}")
    response = session.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return BeautifulSoup(response.text, "html.parser")


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
    frame.to_csv(RAW_FILE, encoding="utf-8-sig", index=False)
    pd.DataFrame(links, columns=["listing_page", "source_url"]).drop_duplicates().to_csv(
        LINKS_FILE, encoding="utf-8-sig", index=False
    )
    return frame


def save_snapshots(frame):
    snapshot_date = datetime.now(UTC).date().isoformat()
    snapshots = frame[["article_id", "source_url", "view_count", "collected_at"]].copy()
    snapshots.insert(1, "snapshot_date", snapshot_date)
    if SNAPSHOTS_FILE.exists():
        snapshots = pd.concat([pd.read_csv(SNAPSHOTS_FILE), snapshots], ignore_index=True)
    snapshots.drop_duplicates(["article_id", "snapshot_date"], keep="last").to_csv(
        SNAPSHOTS_FILE, encoding="utf-8-sig", index=False
    )


def save_monthly_stats(frame):
    statistics = (
        frame.dropna(subset=["published_year", "published_month"])
        .groupby(["published_year", "published_month"], as_index=False)
        .agg(article_count=("article_id", "count"), total_view_count=("view_count", "sum"),
             average_view_count=("view_count", "mean"))
    )
    statistics.to_csv(MONTHLY_STATS_FILE, encoding="utf-8-sig", index=False)


def crawl():
    """Crawl tối đa MAX_ARTICLES, lưu checkpoint sau từng trang để có thể chạy tiếp."""
    DATA_DIR.mkdir(exist_ok=True)
    records = load_existing_records()
    links = []
    session = requests.Session()
    for page in range(1, MAX_PAGES + 1):
        if len(records) >= MAX_ARTICLES:
            break
        # VNTRIP dùng đường dẫn /page/<n>, không dùng query ?page=<n>.
        # Query cũ luôn trả về danh sách trang đầu nên chỉ thu được các URL trùng nhau.
        listing_url = LIST_URL if page == 1 else f"{LIST_URL}/page/{page}"
        print(f"Trang {page}: {listing_url}")
        cards = get_article_cards(getdata(session, listing_url))
        if not cards:
            print("Không còn bài viết ở trang này.")
            break
        new_urls = sum(card["source_url"] not in records for card in cards)
        print(f"  Phát hiện {len(cards)} bài viết, trong đó có {new_urls} URL mới.")
        for card in cards:
            links.append({"listing_page": page, "source_url": card["source_url"]})
            if card["source_url"] in records:
                records[card["source_url"]].update({
                    key: value for key, value in card.items() if value not in ("", None)
                })
                records[card["source_url"]]["collected_at"] = datetime.now(UTC).isoformat()
                continue
            print(f"  {card['source_url']}")
            records[card["source_url"]] = parse_article(getdata(session, card["source_url"]), card)
            if len(records) >= MAX_ARTICLES:
                break
        save_outputs(records, links)

    frame = save_outputs(records, links)
    save_snapshots(frame)
    save_monthly_stats(frame)
    print(f"Đã lưu {len(frame)} bài viết vào {RAW_FILE}")


if __name__ == "__main__":
    crawl()

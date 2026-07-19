"""Kiểm thử hồi quy không cần mạng cho phần refactor lõi."""

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import requests
from bs4 import BeautifulSoup

from common.config import crawler_limits
from common.run_manifest import CrawlReport
from common.http_client import CrawlHttpClient
from analysis_pipeline import REVIEW_FACTORS, canonical_destination, contains_normalized_term, label_with_evidence, normalize_for_match, normalize_url
from VNTRIP.crawl_vntrip import parse_comment_count
from PROVINCIAL_PORTALS.crawl_portals import article_links, pagination_links, parse_date
from VIETNAM_TRAVEL.crawl_vietnam_travel import get_content_links, parse_content


class RefactorTests(unittest.TestCase):
    def test_new_article_limit_accepts_legacy_environment_name(self):
        with patch.dict(os.environ, {"TEST_MAX_ARTICLES": "17"}, clear=False):
            limits = crawler_limits("TEST", 2, 10)
        self.assertEqual(limits.max_new_articles, 17)

    def test_url_normalization_removes_query_and_fragment(self):
        self.assertEqual(
            normalize_url("HTTPS://Vietnam.Travel/things-to-do/foo/?utm_source=x#part"),
            "https://vietnam.travel/things-to-do/foo",
        )

    def test_label_has_evidence(self):
        label, evidence, score, status = label_with_evidence(
            "Cẩm nang Phú Quốc", "Kinh nghiệm du lịch đảo Phú Quốc", {"Phú Quốc": ["phú quốc"]}
        )
        self.assertEqual((label, evidence, score, status), ("Phú Quốc", "phú quốc", 4, "auto"))

    def test_review_factor_terms_are_normalized_for_vietnamese_text(self):
        text = normalize_for_match("Dịch vụ tốt, bãi biển sạch.")
        self.assertIn(normalize_for_match("dịch vụ"), text)
        self.assertTrue(any(contains_normalized_term(text, term) for term in REVIEW_FACTORS["Dịch vụ"]))

    def test_review_destination_is_canonicalized(self):
        self.assertEqual(canonical_destination("da nang"), "Đà Nẵng")

    def test_content_comment_count_is_not_a_rating(self):
        self.assertEqual(parse_comment_count("Gửi 12 bình luận"), 12)
        self.assertEqual(parse_comment_count("Không có phản hồi"), "")

    def test_portal_link_filter_keeps_only_same_site_article_links(self):
        soup = BeautifulSoup('<a href="/news/a">Một bài viết du lịch đủ dài để được chọn</a><a href="https://other.example/a">Một bài viết du lịch đủ dài để được chọn</a>', "html.parser")
        self.assertEqual(article_links(soup, "https://tourism.example/"), ["https://tourism.example/news/a"])
        self.assertEqual(parse_date(BeautifulSoup("<html></html>", "html.parser"), "Ngày 12/07/2026"), "2026-07-12")
        pages = BeautifulSoup('<a href="/news?page=2">2</a><a href="https://other.example/?page=2">2</a>', "html.parser")
        self.assertEqual(pagination_links(pages, "https://tourism.example/"), ["https://tourism.example/news?page=2"])

    def test_crawler_stops_when_robots_cannot_be_checked(self):
        client = CrawlHttpClient("test", 0, 1, 0)
        with patch.object(client.session, "get", side_effect=requests.Timeout("offline")):
            with self.assertRaises(PermissionError):
                client.allowed_by_robots("https://tourism.example/article")

    def test_vietnam_travel_parser_extracts_only_content_urls(self):
        soup = BeautifulSoup(
            '<a href="/things-to-do/food">Ẩm thực</a><a href="/place-to-go">Danh mục</a>', "html.parser"
        )
        self.assertEqual(get_content_links(soup), ["https://vietnam.travel/things-to-do/food"])
        article = parse_content(
            BeautifulSoup('<html><head><meta name="description" content="Mô tả"></head><body><main><h1>Ẩm thực</h1><p>Nội dung</p></main></body></html>', "html.parser"),
            "https://vietnam.travel/things-to-do/food",
        )
        self.assertEqual(article["title"], "Ẩm thực")
        self.assertIn("Nội dung", article["article_text"])

    def test_crawl_manifest_is_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.json"
            report = CrawlReport(source="TEST", new_records=2)
            report.write(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["source"], "TEST")
        self.assertTrue(payload["finished_at"])


if __name__ == "__main__":
    unittest.main()

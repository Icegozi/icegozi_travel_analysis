"""Kiểm thử hồi quy không cần mạng cho phần refactor lõi."""

import json
import os
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from common.config import crawler_limits
from common.run_manifest import CrawlReport
from analysis_pipeline import label_with_evidence, normalize_url
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

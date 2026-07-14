"""Lưu báo cáo có cấu trúc của lần crawl để phát hiện dữ liệu cũ/lỗi."""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path


@dataclass
class CrawlReport:
    source: str
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    finished_at: str = ""
    listing_pages_seen: int = 0
    urls_discovered: int = 0
    existing_urls: int = 0
    new_records: int = 0
    errors: list[str] = field(default_factory=list)

    def finish(self) -> None:
        self.finished_at = datetime.now(UTC).isoformat()

    def write(self, output_file: Path) -> None:
        self.finish()
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

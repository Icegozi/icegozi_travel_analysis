"""Đọc cấu hình môi trường tại một nơi, có kiểm tra giá trị cơ bản."""

import os
from dataclasses import dataclass


def env_int(name: str, default: int, minimum: int = 0) -> int:
    value = int(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} phải lớn hơn hoặc bằng {minimum}.")
    return value


def env_float(name: str, default: float, minimum: float = 0) -> float:
    value = float(os.getenv(name, str(default)))
    if value < minimum:
        raise ValueError(f"{name} phải lớn hơn hoặc bằng {minimum}.")
    return value


@dataclass(frozen=True)
class CrawlLimits:
    max_pages: int
    max_new_articles: int
    delay_seconds: float
    timeout_seconds: int
    retries: int


def crawler_limits(prefix: str, default_pages: int, default_new_articles: int) -> CrawlLimits:
    """Đọc biến mới, vẫn hỗ trợ MAX_ARTICLES cũ để không phá cấu hình hiện tại."""
    legacy_articles = os.getenv(f"{prefix}_MAX_ARTICLES", str(default_new_articles))
    return CrawlLimits(
        max_pages=env_int(f"{prefix}_MAX_PAGES", default_pages, 1),
        max_new_articles=env_int(f"{prefix}_MAX_NEW_ARTICLES", int(legacy_articles), 1),
        delay_seconds=env_float(f"{prefix}_DELAY_SECONDS", 3, 0),
        timeout_seconds=env_int("HTTP_TIMEOUT_SECONDS", 30, 1),
        retries=env_int("HTTP_RETRIES", 2, 0),
    )

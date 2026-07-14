"""HTTP client lịch sự: robots.txt, retry có backoff và giới hạn tốc độ."""

import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup


class CrawlHttpClient:
    def __init__(self, user_agent: str, delay_seconds: float, timeout_seconds: int, retries: int = 2):
        self.user_agent = user_agent
        self.delay_seconds = delay_seconds
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.session = requests.Session()
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}

    def allowed_by_robots(self, url: str) -> bool:
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self._robots:
            robots = urllib.robotparser.RobotFileParser()
            robots.set_url(f"{origin}/robots.txt")
            robots.read()
            self._robots[origin] = robots
        return self._robots[origin].can_fetch(self.user_agent, url)

    def get_soup(self, url: str) -> BeautifulSoup:
        if not self.allowed_by_robots(url):
            raise PermissionError(f"robots.txt không cho phép thu thập: {url}")
        last_error = None
        for attempt in range(self.retries + 1):
            try:
                response = self.session.get(url, headers={"User-Agent": self.user_agent}, timeout=self.timeout_seconds)
                response.raise_for_status()
                time.sleep(self.delay_seconds)
                return BeautifulSoup(response.text, "html.parser")
            except requests.RequestException as error:
                last_error = error
                if attempt < self.retries:
                    time.sleep(min(2 ** attempt, 8))
        raise last_error  # type: ignore[misc]

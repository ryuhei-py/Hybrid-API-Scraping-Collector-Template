from __future__ import annotations

from typing import Any, Tuple

import requests
from bs4 import BeautifulSoup

from .config import SourceConfig


class ScrapeError(Exception):
    """Raised when HTML scraping fails after retries or parsing issues occur."""


def fetch_html(
    url: str,
    timeout: float = 10.0,
    max_retries: int = 3,
    headers: dict[str, str] | None = None,
) -> str:
    """Fetch HTML content with basic retry logic on network errors and 5xx responses."""
    headers = headers or {}
    last_status: int | None = None
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=headers)
        except requests.exceptions.RequestException as exc:
            last_error = exc
            if attempt >= max_retries:
                raise ScrapeError(f"Failed to fetch HTML from {url}") from exc
            continue

        last_status = getattr(response, "status_code", None)

        if last_status is not None and 500 <= last_status < 600:
            if attempt >= max_retries:
                raise ScrapeError(f"Server error while fetching {url} (status {last_status})")
            continue

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise ScrapeError(f"HTTP error while fetching {url} (status {last_status})") from exc

        # Prefer requests' encoding when it’s trustworthy; otherwise fall back to apparent_encoding.
        enc = (response.encoding or "").lower()
        if not enc or enc in {"iso-8859-1", "latin-1", "latin1"}:
            enc = (response.apparent_encoding or "utf-8").lower()

    raise ScrapeError(f"Failed to fetch HTML from {url} (status {last_status})") from last_error


def _split_selector(selector: str) -> Tuple[str, str | None]:
    if "::attr(" in selector and selector.endswith(")"):
        before, _, remainder = selector.partition("::attr(")
        attr_name = remainder[:-1]  # remove trailing ')'
        return before, attr_name
    return selector, None


class HtmlScraper:
    def __init__(self, timeout: float = 10.0, max_retries: int = 3, headers: dict[str, str] | None = None):
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = headers or {}

    def fetch_and_parse(self, source: SourceConfig, context: dict[str, Any] | None = None) -> dict[str, Any] | None:
        html_cfg = source.html
        if html_cfg is None or not html_cfg.enabled:
            return None

        url = html_cfg.url or ""
        if context:
            try:
                url = url.format(**context)
            except KeyError as exc:
                raise ScrapeError(f"Missing context key '{exc.args[0]}' for URL formatting") from exc

        html_text = fetch_html(url, timeout=self.timeout, max_retries=self.max_retries, headers=self.headers)
        soup = BeautifulSoup(html_text, "html.parser")

        selectors = html_cfg.selectors or {}
        html_values: dict[str, Any] = {}

        for field, selector in selectors.items():
            base_selector, attr_name = _split_selector(selector)
            matches = soup.select(base_selector)
            if not matches:
                html_values[field] = None
                continue

            element = matches[0]

            if attr_name:
                value = element.get(attr_name)
                html_values[field] = value.strip() if isinstance(value, str) else value
            else:
                html_values[field] = element.get_text(strip=True)

        return html_values

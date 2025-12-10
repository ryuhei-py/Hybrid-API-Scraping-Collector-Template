from __future__ import annotations

from typing import Any

import requests

from .config import SourceConfig


class ApiError(Exception):
    """Raised when an API request fails after retries."""

    def __init__(self, message: str, url: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.url = url
        self.status_code = status_code


def extract_json_value(data: dict, path: str) -> Any:
    """Extract a nested value from a JSON-like dict using dot-separated keys."""
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            if idx < 0 or idx >= len(current):
                return None
            current = current[idx]
        else:
            return None
        if current is None:
            return None
    return current


class ApiClient:
    def __init__(self, timeout: float = 10.0, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries

    def fetch(self, source: SourceConfig, context: dict[str, Any] | None = None) -> dict[str, Any] | None:
        api_cfg = source.api
        if api_cfg is None or not api_cfg.enabled:
            return None

        url = api_cfg.base_url or ""
        if context:
            try:
                url = url.format(**context)
            except KeyError as exc:
                raise ApiError(f"Missing context key '{exc.args[0]}' for URL formatting", url=url) from exc

        params = api_cfg.params or {}
        headers = api_cfg.headers or {}
        method = api_cfg.method or "GET"

        last_status: int | None = None
        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.request(method, url, params=params, headers=headers, timeout=self.timeout)
            except requests.exceptions.RequestException as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    raise ApiError("API request failed", url=url) from exc
                continue

            last_status = getattr(response, "status_code", None)

            if last_status is not None and 500 <= last_status < 600:
                if attempt >= self.max_retries:
                    raise ApiError("API request failed with server error", url=url, status_code=last_status)
                continue

            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as exc:
                raise ApiError("API request failed", url=url, status_code=last_status) from exc

            try:
                payload = response.json()
            except ValueError as exc:
                raise ApiError("API response was not valid JSON", url=url, status_code=last_status) from exc

            key_map = api_cfg.json_key_map or {}
            api_values = {key: extract_json_value(payload, path) for key, path in key_map.items()}
            return api_values

        if last_error:
            raise ApiError("API request failed", url=url, status_code=last_status) from last_error

        raise ApiError("API request failed", url=url, status_code=last_status)

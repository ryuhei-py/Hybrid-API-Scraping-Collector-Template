import requests
import pytest

from hybrid_collector.api_client import ApiClient, ApiError, extract_json_value
from hybrid_collector.config import ApiConfig, MappingConfig, SourceConfig


def _build_source(json_key_map: dict[str, str], base_url: str = "https://api.example.com/items/{external_id}") -> SourceConfig:
    api_cfg = ApiConfig(
        enabled=True,
        base_url=base_url,
        method="GET",
        params=None,
        headers=None,
        json_key_map=json_key_map,
    )
    mapping_cfg = MappingConfig(unified_fields={"id": "id"}, field_types=None)
    return SourceConfig(id="source1", api=api_cfg, html=None, mapping=mapping_cfg)


def test_extract_json_value():
    data = {"data": {"price": {"current": 9.99}, "items": [{"id": 1}, {"id": 2}]}}
    assert extract_json_value(data, "data.price.current") == 9.99
    assert extract_json_value(data, "data.items.1.id") == 2
    assert extract_json_value(data, "data.missing") is None


def test_fetch_formats_url_and_extracts(monkeypatch):
    called = []

    def fake_request(method, url, params=None, headers=None, timeout=None):
        called.append((method, url, params, headers, timeout))

        class Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"data": {"price": {"current": 12.5}, "name": "Widget"}}

        return Resp()

    monkeypatch.setattr("hybrid_collector.api_client.requests.request", fake_request)

    source = _build_source({"price": "data.price.current", "title": "data.name"})
    client = ApiClient(timeout=1, max_retries=2)

    result = client.fetch(source, context={"external_id": "123"})

    assert called[0][1] == "https://api.example.com/items/123"
    assert result == {"price": 12.5, "title": "Widget"}


def test_retries_on_5xx(monkeypatch):
    attempts = {"count": 0}

    def fake_request(method, url, params=None, headers=None, timeout=None):
        attempts["count"] += 1

        class Resp:
            def __init__(self, status_code, data=None):
                self.status_code = status_code
                self._data = data or {}

            def raise_for_status(self):
                if 400 <= self.status_code < 600:
                    raise requests.exceptions.HTTPError(response=self)

            def json(self):
                return self._data

        if attempts["count"] == 1:
            return Resp(500)
        return Resp(200, {"value": {"id": 10}})

    monkeypatch.setattr("hybrid_collector.api_client.requests.request", fake_request)

    source = _build_source({"id": "value.id"})
    client = ApiClient(timeout=1, max_retries=3)

    result = client.fetch(source)

    assert attempts["count"] == 2  # retried after 500
    assert result == {"id": 10}


def test_no_retry_on_4xx(monkeypatch):
    attempts = {"count": 0}

    def fake_request(method, url, params=None, headers=None, timeout=None):
        attempts["count"] += 1

        class Resp:
            status_code = 404

            def raise_for_status(self):
                raise requests.exceptions.HTTPError(response=self)

            def json(self):
                return {}

        return Resp()

    monkeypatch.setattr("hybrid_collector.api_client.requests.request", fake_request)

    source = _build_source({"id": "value.id"})
    client = ApiClient(timeout=1, max_retries=3)

    with pytest.raises(ApiError):
        client.fetch(source)

    assert attempts["count"] == 1  # no retry for 4xx

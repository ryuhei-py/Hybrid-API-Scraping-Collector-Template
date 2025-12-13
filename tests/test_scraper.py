
from hybrid_collector.config import HtmlConfig, MappingConfig, SourceConfig
from hybrid_collector.scraper import HtmlScraper, fetch_html


def _build_source(selectors: dict[str, str], url: str = "https://example.com/{slug}") -> SourceConfig:
    html_cfg = HtmlConfig(enabled=True, url=url, selectors=selectors)
    mapping_cfg = MappingConfig(unified_fields={"id": "id"}, field_types=None)
    return SourceConfig(id="source_html", api=None, html=html_cfg, mapping=mapping_cfg)


def test_fetch_and_parse_text_and_attr(monkeypatch):
    called = []

    def fake_get(url, timeout=None, headers=None):
        called.append((url, timeout, headers))

        class Resp:
            status_code = 200
            text = """
            <div class="item">
                <span class="price"> $9.99 </span>
                <img class="thumb" src="http://example.com/img.png" />
            </div>
            """

            def raise_for_status(self):
                return None

        return Resp()

    monkeypatch.setattr("requests.get", fake_get)

    selectors = {"price": "span.price", "thumb": "img.thumb::attr(src)"}
    source = _build_source(selectors)
    scraper = HtmlScraper(timeout=1, max_retries=2, headers={"X-Test": "1"})

    result = scraper.fetch_and_parse(source, context={"slug": "item"})

    assert called[0][0] == "https://example.com/item"
    assert result == {"price": "$9.99", "thumb": "http://example.com/img.png"}


def test_fetch_html_retries_on_5xx(monkeypatch):
    attempts = {"count": 0}

    def fake_get(url, timeout=None, headers=None):
        attempts["count"] += 1

        class Resp:
            def __init__(self, status_code):
                self.status_code = status_code
                self.text = "<html></html>"

            def raise_for_status(self):
                if self.status_code >= 400:
                    import requests

                    raise requests.exceptions.HTTPError(response=self)

        if attempts["count"] == 1:
            return Resp(500)
        return Resp(200)

    monkeypatch.setattr("requests.get", fake_get)

    html = fetch_html("https://example.com", timeout=1, max_retries=2)
    assert attempts["count"] == 2
    assert "<html" in html


def test_disabled_html_returns_none():
    html_cfg = HtmlConfig(enabled=False, url="https://example.com", selectors={"title": "h1"})
    mapping_cfg = MappingConfig(unified_fields={"id": "id"}, field_types=None)
    source = SourceConfig(id="s", api=None, html=html_cfg, mapping=mapping_cfg)

    scraper = HtmlScraper()
    assert scraper.fetch_and_parse(source) is None

from hybrid_collector.config import ApiConfig, HtmlConfig, MappingConfig, SourceConfig
from hybrid_collector.normalizer import normalize_record


def _build_source(unified_fields, field_types=None):
    mapping_cfg = MappingConfig(unified_fields=unified_fields, field_types=field_types)
    api_cfg = ApiConfig(enabled=True, base_url="", method="GET", params=None, headers=None, json_key_map=None)
    html_cfg = HtmlConfig(enabled=True, url="", selectors=None)
    return SourceConfig(id="s1", api=api_cfg, html=html_cfg, mapping=mapping_cfg)


def test_combine_api_and_html():
    source = _build_source({"id": "api.external_id", "title": "html.title"})
    api_vals = {"external_id": "123"}
    html_vals = {"title": "Hello"}

    result = normalize_record(source, api_vals, html_vals)

    assert result == {"id": "123", "title": "Hello"}


def test_missing_side_yields_none():
    source = _build_source({"id": "api.external_id", "title": "html.title"})
    api_vals = None
    html_vals = {"title": "Hello"}

    result = normalize_record(source, api_vals, html_vals)

    assert result["id"] is None
    assert result["title"] == "Hello"


def test_type_conversion():
    source = _build_source(
        {"price": "api.price", "count": "html.count"},
        field_types={"price": "float", "count": "int"},
    )
    api_vals = {"price": "9.99"}
    html_vals = {"count": "5"}

    result = normalize_record(source, api_vals, html_vals)

    assert result["price"] == 9.99
    assert result["count"] == 5

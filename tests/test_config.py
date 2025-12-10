import pytest

from hybrid_collector.config import ConfigError, load_sources


def _write_yaml(tmp_path, content: str) -> str:
    path = tmp_path / "sources.yml"
    path.write_text(content, encoding="utf-8")
    return str(path)


def test_load_sources_success(tmp_path, monkeypatch):
    monkeypatch.setenv("API_BASE", "https://api.example.com")
    monkeypatch.setenv("API_TOKEN", "secret")

    yaml_content = """
- id: source1
  api:
    enabled: true
    base_url: "${API_BASE}"
    method: GET
    params:
      q: demo
    headers:
      Authorization: "Bearer ${API_TOKEN}"
    json_key_map:
      id: data.id
  html:
    enabled: false
  mapping:
    unified_fields:
      name: data.name
      price: data.price
    field_types:
      price: float
- id: source2
  html:
    enabled: true
    url: "https://example.com"
    selectors:
      title: "h1::text"
  mapping:
    unified_fields:
      title: title
"""

    config_path = _write_yaml(tmp_path, yaml_content)
    sources = load_sources(config_path)

    assert len(sources) == 2

    api_source = sources[0]
    assert api_source.id == "source1"
    assert api_source.api is not None
    assert api_source.api.base_url == "https://api.example.com"
    assert api_source.api.headers == {"Authorization": "Bearer secret"}
    assert api_source.mapping.unified_fields["name"] == "data.name"

    html_source = sources[1]
    assert html_source.api is None
    assert html_source.html is not None
    assert html_source.html.url == "https://example.com"


def test_missing_required_fields_raises(tmp_path):
    yaml_content = """
- api:
    enabled: true
    method: GET
  mapping:
    unified_fields:
      name: data.name
"""
    config_path = _write_yaml(tmp_path, yaml_content)

    with pytest.raises(ConfigError):
        load_sources(config_path)

    yaml_no_mapping = """
- id: source_no_mapping
  api:
    enabled: false
    method: GET
"""
    config_path2 = _write_yaml(tmp_path, yaml_no_mapping)
    with pytest.raises(ConfigError):
        load_sources(config_path2)

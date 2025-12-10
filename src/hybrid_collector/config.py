from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import os

import yaml


class ConfigError(Exception):
    """Raised when the sources configuration is invalid or missing required data."""


def _expand_env(value: Any) -> Any:
    """Recursively expand environment variables in strings within a nested structure."""
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


@dataclass
class ApiConfig:
    enabled: bool
    base_url: str | None
    method: str
    params: dict[str, Any] | None
    headers: dict[str, str] | None
    json_key_map: dict[str, str] | None


@dataclass
class HtmlConfig:
    enabled: bool
    url: str | None
    selectors: dict[str, str] | None


@dataclass
class MappingConfig:
    unified_fields: dict[str, str]
    field_types: dict[str, str] | None


@dataclass
class SourceConfig:
    id: str
    api: ApiConfig | None
    html: HtmlConfig | None
    mapping: MappingConfig


def _validate_mapping(mapping_data: dict[str, Any]) -> MappingConfig:
    if not isinstance(mapping_data, dict):
        raise ConfigError("mapping must be a mapping object")

    unified_fields = mapping_data.get("unified_fields")
    if not isinstance(unified_fields, dict) or not unified_fields:
        raise ConfigError("mapping.unified_fields is required and must be a non-empty mapping")

    field_types = mapping_data.get("field_types")
    if field_types is not None and not isinstance(field_types, dict):
        raise ConfigError("mapping.field_types must be a mapping if provided")

    return MappingConfig(unified_fields=unified_fields, field_types=field_types)


def _build_api(api_data: dict[str, Any] | None) -> ApiConfig | None:
    if api_data is None:
        return None
    if not isinstance(api_data, dict):
        raise ConfigError("api must be a mapping object")

    enabled = bool(api_data.get("enabled", False))
    method = api_data.get("method") or "GET"
    base_url = api_data.get("base_url")
    params = api_data.get("params")
    headers = api_data.get("headers")
    json_key_map = api_data.get("json_key_map")

    if enabled and not base_url:
        raise ConfigError("api.base_url is required when api is enabled")

    if not isinstance(method, str):
        raise ConfigError("api.method must be a string")

    if headers is not None and not isinstance(headers, dict):
        raise ConfigError("api.headers must be a mapping if provided")

    if params is not None and not isinstance(params, dict):
        raise ConfigError("api.params must be a mapping if provided")

    if json_key_map is not None and not isinstance(json_key_map, dict):
        raise ConfigError("api.json_key_map must be a mapping if provided")

    return ApiConfig(
        enabled=enabled,
        base_url=base_url,
        method=method,
        params=params,
        headers=headers,
        json_key_map=json_key_map,
    )


def _build_html(html_data: dict[str, Any] | None) -> HtmlConfig | None:
    if html_data is None:
        return None
    if not isinstance(html_data, dict):
        raise ConfigError("html must be a mapping object")

    enabled = bool(html_data.get("enabled", False))
    url = html_data.get("url")
    selectors = html_data.get("selectors")

    if enabled and not url:
        raise ConfigError("html.url is required when html is enabled")

    if selectors is not None and not isinstance(selectors, dict):
        raise ConfigError("html.selectors must be a mapping if provided")

    return HtmlConfig(enabled=enabled, url=url, selectors=selectors)


def load_sources(path: str) -> list[SourceConfig]:
    """Load and validate source configurations from a YAML file."""
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {path}")

    raw_content = config_path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw_content)

    if not isinstance(data, list):
        raise ConfigError("Configuration file must contain a list of sources")

    sources: list[SourceConfig] = []
    for idx, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"Each source entry must be a mapping (index {idx})")

        expanded = _expand_env(item)

        source_id = expanded.get("id")
        if not source_id:
            raise ConfigError(f"Source at index {idx} is missing required 'id'")

        mapping_data = expanded.get("mapping")
        if mapping_data is None:
            raise ConfigError(f"Source '{source_id}' is missing required 'mapping'")

        mapping = _validate_mapping(mapping_data)
        api = _build_api(expanded.get("api"))
        html = _build_html(expanded.get("html"))

        if api is None and html is None:
            raise ConfigError(f"Source '{source_id}' must define at least one of 'api' or 'html'")

        sources.append(SourceConfig(id=str(source_id), api=api, html=html, mapping=mapping))

    return sources

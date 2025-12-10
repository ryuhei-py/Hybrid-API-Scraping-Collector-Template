from __future__ import annotations

from typing import Any, Dict, List

from .config import SourceConfig


def _convert_value(value: Any, target_type: str | None) -> Any:
    if value is None or target_type is None:
        return value
    try:
        if target_type == "float":
            return float(value)
        if target_type == "int":
            return int(value)
    except (TypeError, ValueError):
        return None
    return value


def normalize_record(
    source: SourceConfig,
    api_values: dict[str, Any] | None,
    html_values: dict[str, Any] | None,
) -> dict[str, Any]:
    unified: Dict[str, Any] = {}
    unified_fields = source.mapping.unified_fields
    field_types = source.mapping.field_types or {}

    for unified_key, mapping_expr in unified_fields.items():
        parts = mapping_expr.split(".")
        if len(parts) < 2:
            unified[unified_key] = None
            continue

        source_type, field_key = parts[0], ".".join(parts[1:])
        value: Any = None

        if source_type == "api":
            if api_values is not None:
                value = api_values.get(field_key)
        elif source_type == "html":
            if html_values is not None:
                value = html_values.get(field_key)
        else:
            value = None

        target_type = field_types.get(unified_key)
        unified[unified_key] = _convert_value(value, target_type)

    return unified


def normalize_all(
    sources: list[SourceConfig],
    api_results: dict[str, dict[str, Any] | None],
    html_results: dict[str, dict[str, Any] | None],
) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for source in sources:
        api_vals = api_results.get(source.id)
        html_vals = html_results.get(source.id)
        records.append(normalize_record(source, api_vals, html_vals))
    return records

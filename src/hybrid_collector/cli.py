from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from .api_client import ApiClient
from .config import ConfigError, SourceConfig, load_sources
from .exporter import export_to_csv, export_to_json
from .normalizer import normalize_record
from .scraper import HtmlScraper
from .validator import validate_records


def _build_context(source: SourceConfig) -> dict[str, Any]:
    # Simple placeholder context; in real usage this might come from upstream data.
    return {"external_id": source.id}


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid API + HTML collector")
    parser.add_argument("--config", default="config/sources.example.yml", help="Path to sources YAML config")
    parser.add_argument("--output-dir", default="sample_output", help="Directory to write outputs")
    parser.add_argument("--dry-run", action="store_true", help="Skip writing outputs")
    args = parser.parse_args()

    try:
        sources = load_sources(args.config)
    except ConfigError as exc:
        print(f"[config error] {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # pragma: no cover
        print(f"[error] Failed to load config: {exc}", file=sys.stderr)
        sys.exit(1)

    api_client = ApiClient()
    scraper = HtmlScraper()

    records: list[dict[str, Any]] = []
    validation_issues: list[str] = []
    api_results: dict[str, dict[str, Any] | None] = {}
    html_results: dict[str, dict[str, Any] | None] = {}

    for source in sources:
        context = _build_context(source)
        try:
            api_values = api_client.fetch(source, context=context)
            html_values = scraper.fetch_and_parse(source, context=context)
        except Exception as exc:  # pragma: no cover - surface unexpected errors
            print(f"[error] Source '{source.id}' failed: {exc}", file=sys.stderr)
            continue

        api_results[source.id] = api_values
        html_results[source.id] = html_values

        record = normalize_record(source, api_values, html_values)
        records.append(record)

        required_fields = list(source.mapping.unified_fields.keys())
        issues = validate_records([record], required_fields)
        if issues:
            for issue in issues:
                validation_issues.append(f"{source.id}:{issue.field}@{issue.index}")

    if validation_issues:
        print(f"[validation] Issues found: {', '.join(validation_issues)}")
    else:
        print("[validation] No issues")

    if args.dry_run:
        print("[dry-run] Skipping export")
        return

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "unified_records.csv"
    json_path = output_dir / "unified_records.json"

    export_to_csv(records, csv_path)
    export_to_json(records, json_path)
    print(f"[export] Wrote {len(records)} records to {csv_path} and {json_path}")


if __name__ == "__main__":  # pragma: no cover
    main()

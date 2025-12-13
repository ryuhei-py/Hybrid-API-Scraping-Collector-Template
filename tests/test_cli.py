import sys
from pathlib import Path



def test_dry_run_skips_export(monkeypatch, tmp_path):
    # Prepare fake sources config file
    sources_yaml = """
- id: s1
  api:
    enabled: false
  html:
    enabled: false
    url: "https://example.com"
    selectors: {}
  mapping:
    unified_fields:
      title: html.title
"""
    config_path = tmp_path / "sources.yml"
    config_path.write_text(sources_yaml, encoding="utf-8")

    # Stub ApiClient, HtmlScraper, and exporters
    class FakeApiClient:
        def fetch(self, source, context=None):
            return {"id": source.id}

    class FakeScraper:
        def fetch_and_parse(self, source, context=None):
            return {"title": "ok"}

    called_exports = []

    def fake_export_csv(records, path):
        called_exports.append(("csv", path))

    def fake_export_json(records, path):
        called_exports.append(("json", path))

    monkeypatch.setenv("PYTHONPATH", str(Path.cwd()))
    monkeypatch.setattr("hybrid_collector.cli.ApiClient", FakeApiClient)
    monkeypatch.setattr("hybrid_collector.cli.HtmlScraper", FakeScraper)
    monkeypatch.setattr("hybrid_collector.cli.export_to_csv", fake_export_csv)
    monkeypatch.setattr("hybrid_collector.cli.export_to_json", fake_export_json)

    from hybrid_collector import cli

    argv = [sys.argv[0], "--config", str(config_path), "--dry-run", "--output-dir", str(tmp_path / "out")]
    monkeypatch.setattr(sys, "argv", argv)

    cli.main()

    assert called_exports == []

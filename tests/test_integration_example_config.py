import json
import sys
from pathlib import Path

import requests

import hybrid_collector.cli as collector_cli


class DummyResponse:
    def __init__(self, *, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = {}

    def json(self):
        if self._json_data is None:
            raise ValueError("No JSON payload set for this response")
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _fake_session_request(self, method, url, **kwargs):
    # API endpoint used in sources.example.yml
    if url == "https://jsonplaceholder.typicode.com/posts/1":
        return DummyResponse(
            status_code=200,
            json_data={
                "userId": 1,
                "id": 1,
                "title": "demo title",
                "body": "demo body",
            },
        )

    # HTML endpoint used in sources.example.yml
    if url == "https://example.com/":
        html = """
        <!doctype html>
        <html lang="en">
          <head><title>Example Domain</title></head>
          <body>
            <h1>Example Domain</h1>
            <p>This domain is for use in documentation examples without needing permission.</p>
          </body>
        </html>
        """
        return DummyResponse(status_code=200, text=html)

    return DummyResponse(status_code=404, text="not found")

def _run_cli(argv):
    """
    For CLIs where main() takes no argv argument and reads sys.argv.
    Returns an int exit code (0 on success).
    """
    old_argv = sys.argv[:]
    sys.argv = ["hybrid-collector", *argv]
    try:
        try:
            ret = collector_cli.main()
        except SystemExit as e:
            ret = e.code
    finally:
        sys.argv = old_argv

    return 0 if ret is None else int(ret)



def test_sources_example_end_to_end_exports_non_null_fields(tmp_path, monkeypatch):
    # Mock ALL HTTP calls through requests.Session.request (covers requests.get/requests.request internally).
    monkeypatch.setattr(requests.sessions.Session, "request", _fake_session_request, raising=True)

    out_dir = tmp_path / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg_path = Path("config/sources.example.yml")
    assert cfg_path.exists(), "Expected config/sources.example.yml to exist"

    code = _run_cli(["--config", str(cfg_path), "--output-dir", str(out_dir)])
    assert code == 0

    json_path = out_dir / "unified_records.json"
    csv_path = out_dir / "unified_records.csv"
    assert json_path.exists()
    assert csv_path.exists()

    records = json.loads(json_path.read_text(encoding="utf-8"))
    assert isinstance(records, list) and len(records) >= 1

    rec0 = records[0]
    assert rec0["post_id"] is not None
    assert isinstance(rec0["post_title"], str) and rec0["post_title"].strip()
    assert isinstance(rec0["site_heading"], str) and rec0["site_heading"].strip()
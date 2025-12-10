# Testing
This document describes how to verify, maintain, and extend the Hybrid-API-Scraping-Collector-Template using automated tests.

## How to run the tests
This section explains how to execute the test suite.

### One-time setup
From the project root:

```bash
python -m venv .venv
# Windows: .venv/Scripts/activate
# macOS / Linux: source .venv/bin/activate

pip install -r requirements.txt
```

### Run all tests
From the project root:

```bash
pytest
```

This will discover all tests under `tests/`, execute them with pytest, and print a summary with pass/fail counts.

### Run a subset of tests
You can run tests for a specific module or keyword:

```bash
# Run only config-related tests
pytest tests/test_config.py

# Run tests whose names contain "cli"
pytest -k "cli"
```

This is useful when you are iterating on a specific part of the pipeline.

### Optional: show verbose output
Use verbose output to see each test name:

```bash
pytest -v
```

This prints each test case name explicitly, which is helpful when debugging or demonstrating the suite to clients.

## Test suite structure
This section describes how tests are organized to mirror pipeline components.

Tests live under `tests/` and typically follow this pattern:

```text
tests/
  test_config.py        # Configuration loading and validation
  test_api_client.py    # API client behavior (URL build, headers, errors)
  test_html_scraper.py  # HTML scraping and selector behavior
  test_normalizer.py    # Raw → unified record mapping and type coercion
  test_validator.py     # Data quality and schema-level checks
  test_exporter.py      # CSV/JSON export behavior
  test_cli.py           # End-to-end CLI interactions (happy/failed paths)
  conftest.py           # Shared fixtures (sample configs, sample HTML, etc.)
```

Any file starting with `test_` or ending with `_test.py` will be discovered as a test.

## Unit tests by component
This section outlines expected coverage for each module.

### Config loader (test_config.py)
Purpose: ensure configuration loading is robust so misconfigured YAML does not silently break your pipeline.

Typical scenarios:

- Happy path: a valid `config/sources.yml` loads successfully and required sections are present.
- Missing file: referencing a non-existent config path raises a clear exception.
- Invalid YAML: malformed YAML raises a parsing error.
- Missing required keys: missing fields trigger a validation error.
- Environment variable expansion: `${API_TOKEN}` expands correctly; missing env vars fail with a helpful message.

### API client (test_api_client.py)
Purpose: verify the API client builds requests correctly and handles errors cleanly.

Typical scenarios:

- URL building: base URL and parameters produce the correct final URL.
- Headers and auth: headers from config (including env-var references) are applied.
- Successful responses: a mocked 200 JSON response is parsed.
- Error responses: 4xx / 5xx raise a well-defined exception.
- Timeouts / connection errors: network issues surface clearly, not as generic exceptions.

Implementation note: monkeypatch `requests` calls to avoid real network traffic.

### HTML scraper (test_html_scraper.py)
Purpose: ensure scraping logic is stable even when HTML is imperfect.

Typical scenarios:

- Basic extraction: sample HTML and selectors yield expected values.
- Missing elements: absent elements return `None` or a safe default.
- Multiple matches: list handling or first-match selection is correct.
- Whitespace handling: text is trimmed appropriately.

Implementation note: use small HTML samples or fixture files; avoid real HTTP requests.

### Normalizer (test_normalizer.py)
Purpose: confirm mapping converts heterogeneous results into a unified record.

Typical scenarios:

- Simple mapping: expected keys and values appear in the unified record.
- Type conversions: strings like `"19.99"` or `"5"` cast to `float` or `int`.
- Defaults and fallback: missing fields become `None` when intended.
- Field renaming: source fields map to unified fields correctly.

### Validator (test_validator.py)
Purpose: enforce data quality rules at the unified-record level.

Typical scenarios:

- Valid record passes with no issues.
- Missing required fields produce specific issue messages.
- Type or range violations are flagged.
- Multiple problems yield multiple issues, not just the first one.

### Exporter (test_exporter.py)
Purpose: verify unified records are written correctly and safely.

Typical scenarios:

- CSV export: file exists, header row contains expected columns, row count matches records.
- JSON export: valid JSON with the correct number of records.
- Empty input: exporting empty lists does not crash.
- Write errors: missing or unwritable target directories raise clear errors.

Implementation note: use pytest’s `tmp_path` fixture to isolate filesystem writes.

### CLI (test_cli.py)
Purpose: ensure the end-to-end entrypoint behaves correctly for typical user flows.

Typical scenarios:

- Happy path: valid config and output directory run end to end.
- Dry-run mode: pipeline runs but does not write files; console summarizes processed sources.
- Invalid config path: fails fast with a helpful error.
- Invalid output directory: clear error when writing is impossible.

Implementation note: prefer calling the main CLI function directly and use `capsys`/`caplog` to inspect output.

## Fixtures and test data
This section describes shared fixtures and sample assets.

Shared fixtures live in `tests/conftest.py`. Typical fixtures include:

- Sample config: a minimal `sources.yml` with fake URLs and both API/HTML sources.
- Sample raw responses: fake API JSON payloads and small HTML snippets.
- Sample unified records: representative “ideal” outputs.
- Environment variables: temporary settings so tests do not depend on the developer’s local `.env`.

Test data files, if any, should be placed under a dedicated directory:

```text
tests/data/
  sample_sources.yml
  sample_api_response.json
  sample_page.html
```

This keeps test artifacts organized and explicit.

## Extending the test suite
This section offers a workflow for adding new coverage.

When adding new behavior (new source type, validation rule, or export format), follow this workflow:

1. Add or update tests first: define expected behavior with clear, small cases.
2. Implement or modify the feature.
3. Run tests locally:

    ```bash
    pytest
    ```

4. Refactor if necessary, keeping tests green.
5. Commit with a clear message (e.g. “Add validator rule for negative prices” or “Support JSONL export and tests”).

## Continuous integration (CI)
This section explains how CI typically runs the suite.

On each push or pull request, a typical CI flow will:

- Set up Python.
- Install dependencies:

  ```bash
  pip install -r requirements.txt
  ```

- Run pytest.

This provides automatic verification of contributions and confidence that the template remains stable.

You can extend CI later with coverage reporting, linting (Ruff/flake8), or type checking (mypy/pyright).

## Using tests as a portfolio asset
This section highlights how tests support client work.

For client work (e.g. on Upwork), the test suite is a selling point:

- A clean `tests/` directory.
- Clear, readable test cases.
- pytest output showing all tests passing.

This demonstrates reliability and professional development standards. When you adapt this template for a specific client project, extend the tests to cover the client’s business rules.

## Summary
This section recaps the key points about testing in this template.

- Tests are organized by component (config, API, HTML, normalizer, validator, exporter, CLI).
- Running `pytest` from the project root executes the entire suite.
- Fixtures provide stable sample data and environment settings.
- When you change or extend the pipeline, update tests together with the code.
- A solid test suite is both a technical and business advantage when presenting this template as a professional asset.

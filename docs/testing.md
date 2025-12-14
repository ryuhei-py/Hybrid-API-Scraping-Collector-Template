# Testing

This repository is designed to be verifiable in a deterministic way. The test suite runs **offline by default** by mocking HTTP requests, enabling reliable and reproducible verification in CI and on local machines.

---

## Scope

### Covered by this test suite
- Configuration parsing and validation (including environment variable expansion)
- API client behavior
  - JSON-path extraction
  - retry policy for transient failures (5xx / request exceptions)
  - fail-fast behavior for non-retryable failures (4xx)
- HTML fetching and parsing
  - CSS selector extraction
  - attribute extraction via `::attr(name)`
  - retry policy for transient failures (5xx / request exceptions)
  - fail-fast behavior for non-retryable failures (4xx)
- Normalization (mapping API/HTML outputs into unified records)
- Type casting (`int`, `float`) for unified fields
- Validation (required fields must be present and non-empty)
- Exporters (CSV + JSON)
- CLI wiring (including `--dry-run`)
- Offline end-to-end pipeline using `config/sources.example.yml` (mocked HTTP)

### Not covered (intentionally out of scope)
- Live scraping validation against real websites
- Performance/load testing at scale
- Enforcement of website ToS/robots policies (operational responsibility)

---

## Prerequisites

- Python version: use a version supported by CI (see `.github/workflows/ci.yml`)
- `pip` and `venv`
- Tools used for local verification:
  - `ruff`
  - `pytest`

---

## Environment setup

### Create and activate a virtual environment

**Windows (PowerShell)**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
````

**macOS/Linux**

```bash
python -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
python -m pip install -U pip
pip install -r requirements.txt
```

Optional (editable install):

```bash
pip install -e .
```

---

## Static checks

### Ruff (lint)

Run lint locally:

```bash
ruff check src tests
```

This is the same lint gate enforced by CI. If this command passes locally, it should match CI behavior.

---

## Run tests

### Run the full test suite

```bash
pytest -q
```

You should see a clean summary such as:

* `18 passed` (the number may change as tests evolve)

### Run a specific test module

```bash
pytest tests/test_config.py -q
pytest tests/test_api_client.py -q
pytest tests/test_scraper.py -q
pytest tests/test_integration_example_config.py -q
```

### Run by pattern

```bash
pytest -k "retry" -q
```

---

## Test design: layers and guarantees

### 1) Unit tests (pure logic, no HTTP)

These tests validate behavior without network access:

* **Config parsing and validation**

  * YAML structure validation
  * required keys and basic shape checks
  * recursive expansion of environment variables in strings (e.g., `${API_TOKEN}`)
* **Normalization**

  * mapping expressions (`api.*`, `html.*`) into unified fields
  * type casting via `field_types` (`int`, `float`)
  * cast failures produce `None` (no exceptions)
* **Validation**

  * required fields must exist and be non-empty (`None` and `""` are treated as missing)

### 2) HTTP behavior tests (mocked)

These tests monkeypatch HTTP calls so **no real requests** are sent:

* **API client**

  * retries on request exceptions and 5xx responses
  * fail-fast on 4xx responses
  * JSON-path extraction supports dot paths and list indices (e.g., `a.b.0.c`)
  * retries are immediate (no backoff/jitter)
* **HTML scraping**

  * retries on request exceptions and 5xx responses
  * fail-fast on 4xx responses
  * extraction behavior:

    * first-match selector strategy
    * text extraction via `get_text(strip=True)`
    * attribute extraction via `::attr(name)`

### 3) Integration-style test (offline end-to-end)

`tests/test_integration_example_config.py` runs the full pipeline using:

* `config/sources.example.yml`

The test patches HTTP at the requests layer so the run remains offline and deterministic, then validates:

* the pipeline completes successfully
* unified records contain expected keys
* exporters produce outputs under the test’s temporary directory (when not a dry-run path)

This provides a practical, CI-safe proof that the modules integrate correctly.

---

## CI parity

CI is defined in:

* `.github/workflows/ci.yml`

CI runs:

* `ruff check src tests`
* `pytest -q`

To reproduce CI locally, run those same commands from the repository root:

```bash
ruff check src tests
pytest -q
```

---

## Optional: Coverage (local only)

Coverage is not required by CI, but can be useful during development.

```bash
python -m pip install coverage
coverage run -m pytest
coverage report -m
```

When interpreting coverage, prioritize core modules:

* `src/hybrid_collector/config.py`
* `src/hybrid_collector/api_client.py`
* `src/hybrid_collector/scraper.py`
* `src/hybrid_collector/normalizer.py`
* `src/hybrid_collector/cli.py`

---

## Common failures and troubleshooting

### Import/module resolution errors

Symptoms:

* `ModuleNotFoundError` when running tests

Fix:

* ensure you are in the repository root
* install dependencies: `pip install -r requirements.txt`
* if needed, use editable install: `pip install -e .`

### Python version mismatch

Symptoms:

* CI passes but local fails (or vice versa)

Fix:

* align your local interpreter with a CI-tested version (see `.github/workflows/ci.yml`)
* recreate the venv after switching Python versions

### Network-related confusion

The test suite is offline by design.

However, running the CLI directly can perform real network requests depending on your config file. If you need a deterministic verification run, rely on the tests.

### Config-related failures

Key constraints enforced by config validation:

* The config file is a **YAML list** of sources (not a top-level dict such as `sources:`)
* Each source requires:

  * `id`
  * `mapping.unified_fields`
* Each source must include at least one of:

  * `api` section (can be disabled via `enabled: false`)
  * `html` section (can be disabled via `enabled: false`)
* `api.base_url` and `html.url` are required only if their section is enabled

---

## Quality gates before publishing changes

Run these locally before pushing updates:

```bash
ruff check src tests
pytest -q
```

Also confirm:

* documentation matches the implemented configuration schema
* repository hygiene (do not commit `.venv/`, cache directories, or local output artifacts)

---

## Appendix: Test file map

* `tests/test_config.py` — config parsing, env expansion, and schema validation
* `tests/test_api_client.py` — API retries, 4xx/5xx behavior, JSON-path extraction
* `tests/test_scraper.py` — HTML retries, selector extraction, `::attr(...)` handling
* `tests/test_normalizer.py` — unified field mapping and type casting
* `tests/test_validator.py` — required-field checks
* `tests/test_exporter.py` — CSV/JSON output format correctness
* `tests/test_cli.py` — CLI behavior (`--dry-run`, pipeline wiring)
* `tests/test_integration_example_config.py` — offline end-to-end pipeline using example config
* `tests/test_scheduler_stub.py` — scheduling stub behavior
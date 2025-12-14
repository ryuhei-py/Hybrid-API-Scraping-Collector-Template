# Operations

This document describes how to run and operate the Hybrid API + HTML Collector reliably: installation, configuration practices, execution workflows, scheduling, and practical troubleshooting. It is written to match the current implementation and CLI behavior.

---

## Table of Contents

- [Operational overview](#operational-overview)
- [Prerequisites](#prerequisites)
- [Install and verify](#install-and-verify)
- [Configuration operations](#configuration-operations)
  - [Config file contract](#config-file-contract)
  - [Environment variables](#environment-variables)
  - [URL templating with context](#url-templating-with-context)
  - [API configuration semantics](#api-configuration-semantics)
  - [HTML configuration semantics](#html-configuration-semantics)
  - [Normalization and validation semantics](#normalization-and-validation-semantics)
- [Running the collector](#running-the-collector)
  - [Common commands](#common-commands)
  - [Dry-run mode](#dry-run-mode)
  - [Outputs](#outputs)
  - [Exit codes and failure behavior](#exit-codes-and-failure-behavior)
- [Reliability controls](#reliability-controls)
  - [Timeouts](#timeouts)
  - [Retries](#retries)
  - [No backoff or rate limiting](#no-backoff-or-rate-limiting)
- [Logging and observability](#logging-and-observability)
- [Scheduling](#scheduling)
  - [Cron](#cron)
  - [Windows Task Scheduler](#windows-task-scheduler)
  - [GitHub Actions schedule](#github-actions-schedule)
- [Operational safety and compliance](#operational-safety-and-compliance)
- [Troubleshooting](#troubleshooting)
- [Production hardening ideas](#production-hardening-ideas)
- [Related documentation](#related-documentation)

---

## Operational overview

- **Execution model:** single-run CLI invocation (`python -m hybrid_collector.cli`). This project is not a long-running service.
- **Per-source pipeline:**
  1. Optional API fetch (if enabled)
  2. Optional HTML fetch + parse (if enabled)
  3. Normalize into unified fields using mapping rules
  4. Validate required fields (simple “missing value” checks)
  5. Export CSV + JSON (unless `--dry-run`)
- **State:** no database and no incremental state. Each run produces output files.
- **Network behavior:** the CLI performs real HTTP requests. The test suite is deterministic and mocks all HTTP calls.

---

## Prerequisites

- Python supported by `pyproject.toml`
- Ability to reach the configured targets over the network (for real runs)
- Authorization/permission to access the targets and collect the intended data

---

## Install and verify

### Create a virtual environment

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
````

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Install dependencies

Editable install (recommended while working on the repo):

```bash
pip install -e .
```

Alternatively:

```bash
pip install -r requirements.txt
```

### Verify with offline tests (recommended)

The test suite is designed to run without live network access:

```bash
pytest -q
```

If you have Ruff installed (CI runs this):

```bash
ruff check src tests
```

---

## Configuration operations

### Config file contract

The CLI reads a YAML file containing **a list of source entries** (top-level YAML must be a list).

* Default config path (CLI): `config/sources.example.yml`
* Recommended operational pattern:

  * Keep `config/sources.example.yml` committed as a working reference.
  * Create a local config for real targets (e.g., `config/sources.yml`) and keep it out of version control if it includes sensitive endpoints or tokens.

A minimal source entry contains:

* `id` (required)
* `mapping` (required)
* at least one of `api` or `html` (at least one must be present)

Canonical examples live in:

* `config/sources.example.yml` (recommended starting point)

#### Minimal example (list-only contract)

```yaml
- id: "example_source"
  api:
    enabled: true
    base_url: "https://example.com/api/items"
    method: "GET"
    params:
      limit: 10
    headers:
      Authorization: "Bearer ${API_TOKEN}"
    json_key_map:
      item_id: "data.0.id"
      price: "data.0.price"
  html:
    enabled: true
    url: "https://example.com/items/{external_id}"
    selectors:
      title: "h1"
      image_url: "img.hero::attr(src)"
  mapping:
    unified_fields:
      id: "api.item_id"
      price: "api.price"
      title: "html.title"
      image_url: "html.image_url"
    field_types:
      price: "float"
```

---

### Environment variables

All strings in YAML are processed through environment-variable expansion using `os.path.expandvars()`.

Common patterns:

* Unix-style: `${API_TOKEN}` or `$API_TOKEN`
* Windows-style: `%API_TOKEN%` (when applicable)

Linux/macOS:

```bash
export API_TOKEN="..."
```

Windows (PowerShell):

```powershell
$env:API_TOKEN="..."
```

Notes:

* A `.env.example` is included as a reference.
* The CLI does **not** automatically load a `.env` file. If you want `.env` loading, do it externally (shell tooling/CI) or add it explicitly in code.

---

### URL templating with context

Both API and HTML URLs support Python `str.format(**context)` substitution:

* API: `api.base_url` is formatted with context
* HTML: `html.url` is formatted with context

The CLI provides a minimal context per source:

* `external_id` is set to the source `id`

Example:

```yaml
- id: "user_123"
  html:
    enabled: true
    url: "https://example.com/users/{external_id}"
    selectors:
      name: "h1"
  mapping:
    unified_fields:
      external_id: "api.external_id"   # (example only; depends on your API mapping)
      name: "html.name"
```

If a placeholder is missing, the run logs an error for that source and continues with other sources.

---

### API configuration semantics

API settings are defined under the `api` block.

Supported fields:

* `enabled` (bool, default `true`)
* `base_url` (string; required if enabled)
* `method` (string; default `"GET"`)
* `params` (mapping; sent as query parameters)
* `headers` (mapping; sent as HTTP headers)
* `json_key_map` (mapping of output-field → JSON path)

JSON extraction rules:

* JSON paths are dot-delimited (e.g., `data.id`)
* List indexing is supported using numeric segments (e.g., `items.0.id`)
* Missing paths yield `None` (no exception)

Important operational detail:

* `json_key_map` produces an **API result dictionary** whose keys are used by normalization.
* In mapping expressions, `api.<key>` refers to keys produced by `json_key_map` (not to raw JSON paths).

Limitations to be aware of:

* The API client sends `params` as query parameters. It does not currently support request bodies (`json=`/`data=`), even if `method` is set to `"POST"`.

---

### HTML configuration semantics

HTML settings are defined under the `html` block.

Supported fields:

* `enabled` (bool, default `true`)
* `url` (string; required if enabled)
* `selectors` (mapping of output-field → CSS selector)

Selector rules:

* Selectors are executed with BeautifulSoup’s `select()` (soupsieve CSS selectors).
* Only the **first match** is used.
* If no match exists, the extracted value is `None`.
* Supported selector extension: `::attr(name)` to extract an attribute value.

Examples:

```yaml
selectors:
  title: "h1"
  image_url: "img.hero::attr(src)"
```

Limitations to be aware of:

* Only `::attr(name)` is supported. There is no `::text` pseudo-syntax; text extraction uses `get_text(strip=True)` automatically.
* The CLI does not currently allow configuring HTML request headers via YAML. HTML requests use default `requests` behavior unless you modify the code.

---

### Normalization and validation semantics

#### Mapping (`mapping.unified_fields`)

Normalization builds unified records using expressions of the form:

* `api.<key>` → read from API result dict (`json_key_map` output)
* `html.<key>` → read from HTML parsed dict (`selectors` output)

Example:

```yaml
mapping:
  unified_fields:
    id: "api.item_id"
    title: "html.title"
    price: "api.price"
```

If the referenced side is missing/disabled or a key is not present, the value becomes `None`.

#### Type conversion (`mapping.field_types`)

Optional `field_types` supports:

* `int`
* `float`

Conversion failures yield `None` (no exception).

#### Validation behavior (current CLI)

For each source record, the CLI treats **all unified field keys** as required.

A required field is considered missing if:

* the value is `None`, or
* the value is `""` (empty string)

Validation results are reported to stdout, but validation does not currently change the process exit code.

---

## Running the collector

### Common commands

Run using the default example config and default output directory:

```bash
python -m hybrid_collector.cli
```

Run with an explicit config path:

```bash
python -m hybrid_collector.cli --config config/sources.example.yml
```

Write outputs to a custom directory:

```bash
python -m hybrid_collector.cli --config config/sources.example.yml --output-dir output
```

Recommended: isolate each run into a timestamped folder.

Linux/macOS:

```bash
ts="$(date +%Y%m%d_%H%M%S)"
python -m hybrid_collector.cli --config config/sources.example.yml --output-dir "output/runs/$ts"
```

Windows (PowerShell):

```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
python -m hybrid_collector.cli --config config\sources.example.yml --output-dir "output\runs\$ts"
```

---

### Dry-run mode

Dry-run executes fetch → parse → normalize → validate, but skips export:

```bash
python -m hybrid_collector.cli --config config/sources.example.yml --dry-run
```

Note: dry-run still makes real HTTP requests. Use `pytest -q` for deterministic, offline verification.

---

### Outputs

When not in dry-run, the CLI writes two files into `--output-dir`:

* `unified_records.csv`
* `unified_records.json`

CSV specifics:

* The header is the union of all keys across all produced records.
* Field order is preserved by first appearance across records (insertion order).

JSON specifics:

* UTF-8 output with `ensure_ascii=false` and `indent=2` for readability.

---

### Exit codes and failure behavior

Current CLI behavior is intentionally simple:

* **Exit code `1`**: configuration load failure (e.g., file not found, YAML invalid, required fields missing).
* **Exit code `0`**: normal completion (even if some sources fail or validation issues exist).

Per-source runtime failures:

* If a source raises an exception during API fetch or HTML fetch/parse, the CLI logs:

  * `[error] Source '<id>' failed: ...`
* That source is skipped and the run continues with remaining sources.
* Outputs contain only the records from sources that completed successfully.

Validation:

* Validation issues are printed as:

  * `[validation] Issues found: ...`
* Validation does not currently fail the run.

Operational recommendation (automation):

* If you require strict failure semantics, treat any `[error]` log line or any `[validation] Issues found` as a pipeline failure in your scheduler/CI wrapper.

---

## Reliability controls

### Timeouts

Defaults (as implemented):

* API requests: `timeout=10.0` seconds
* HTML fetch: `timeout=10.0` seconds

These are not currently configurable via YAML in the CLI path.

### Retries

Defaults (as implemented):

* API requests: `max_retries=3`
* HTML fetch: `max_retries=3`

Retry triggers:

* `requests` network exceptions (e.g., connection errors)
* HTTP **5xx** responses

No retry on:

* HTTP **4xx** responses (treated as fatal for that request)

### No backoff or rate limiting

This project does not implement:

* exponential backoff
* jitter
* per-host throttling
* special handling for 429 responses

Operational guidance:

* Schedule conservatively.
* Keep request volume low.
* Prefer off-peak windows.
* If you need throttling/backoff, implement it externally (scheduler spacing) or extend the code.

---

## Logging and observability

The CLI emits operational messages to stdout/stderr with clear prefixes:

* `[config error] ...` (stderr, exits 1)
* `[error] Source '<id>' failed: ...` (stderr, continues)
* `[validation] Issues found: ...` or `[validation] No issues` (stdout)
* `[dry-run] Skipping export` (stdout)
* `[export] Wrote N records to ...` (stdout)

Capture logs for auditing/debugging:

Linux/macOS:

```bash
python -m hybrid_collector.cli --config config/sources.yml --output-dir output > logs/run.log 2>&1
```

Windows (PowerShell):

```powershell
python -m hybrid_collector.cli --config config\sources.yml --output-dir output *> logs\run.log
```

---

## Scheduling

The recommended operational model is external scheduling of the CLI.

### Cron

Example (daily at 02:30):

```cron
30 2 * * * cd /path/to/repo && . .venv/bin/activate && python -m hybrid_collector.cli --config config/sources.yml --output-dir output >> logs/run.log 2>&1
```

### Windows Task Scheduler

High-level approach:

* Create a task that runs `powershell.exe`
* Activate the venv and execute the CLI
* Redirect output to logs

Example script (conceptual):

```powershell
cd C:\path\to\repo
.\.venv\Scripts\Activate.ps1
python -m hybrid_collector.cli --config config\sources.yml --output-dir output *> logs\run.log
```

### GitHub Actions schedule

Using GitHub Actions as a scheduler can work when:

* targets permit automated access
* tokens are stored in GitHub Secrets
* you keep frequency conservative (no built-in rate limiting)

Prefer low frequency schedules unless you add throttling/backoff.

---

## Operational safety and compliance

Operate responsibly:

* Ensure permission and a valid purpose for collection.
* Respect target terms, robots guidance, and access policies.
* Avoid collecting personal or sensitive data unless required and handled appropriately.
* Keep request volume minimal and scheduling conservative.

See: `docs/SECURITY_AND_LEGAL.md`

---

## Troubleshooting

### Config file not found / invalid YAML

Symptoms:

* `[config error] Config file not found: ...`
* `[config error] Configuration file must contain a list of sources`
* `[config error] ... missing required ...`

Fixes:

* Verify the path passed to `--config`
* Validate YAML syntax
* Ensure top-level YAML is a list (`- id: ...`)

### Missing URL template keys

Symptoms:

* API: `Missing context key '...' for URL formatting`
* HTML: `Missing context key '...' for URL formatting`

Fixes:

* The CLI provides `{external_id}` only.
* Remove other placeholders or extend the CLI context builder in code.

### 401/403 responses

Common causes:

* missing or invalid auth token
* insufficient permission
* blocked default request behavior

Fixes:

* confirm env vars are set correctly
* confirm API headers contain required auth
* validate target access rules
* for HTML targets that require a custom User-Agent or headers, extend the code (CLI does not configure HTML headers via YAML)

### 404 responses

Common causes:

* invalid URL
* malformed URL templating

Fixes:

* verify the final URL, especially when using `{external_id}`
* confirm the base URL/path format

### 429 responses (rate limiting)

Behavior:

* no special handling; likely fails for that source.

Fixes:

* reduce frequency
* add external throttling
* implement backoff/rate-limiting in code if needed

### HTML selector returns `None`

Common causes:

* selector mismatch
* dynamic content not present in raw HTML
* markup structure changed

Fixes:

* adjust selector to a stable element
* use `::attr(...)` when appropriate
* consider a browser automation approach if the content is rendered client-side (out of scope for this template)

### JSON path returns `None`

Common causes:

* wrong path
* array index out of range
* API response changed

Fixes:

* capture and inspect the JSON payload
* update `json_key_map` paths
* confirm list indexing segments (`items.0.id`)

---

## Production hardening ideas

If you need stronger operational controls for demanding targets:

* Add exponential backoff + jitter for retries
* Add per-host rate limiting / politeness delays
* Make timeouts/retries configurable via YAML
* Add configurable User-Agent and proxy support
* Add request-body support for APIs (`json=` / `data=`)
* Introduce optional vs required field schema (do not treat all unified fields as required)
* Add structured logging (JSON logs) and per-source timing metrics
* Add persistence (e.g., SQLite) for incremental runs, deduplication, and audit trails

---

## Related documentation

* `README.md` — overview and quickstart
* `docs/architecture.md` — components and flow
* `docs/testing.md` — deterministic test strategy
* `docs/CONFIG_GUIDE.md` — configuration reference
* `docs/SECURITY_AND_LEGAL.md` — safety, compliance, and usage constraints
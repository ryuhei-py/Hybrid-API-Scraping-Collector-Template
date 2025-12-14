# Architecture

This project is a **config-driven hybrid collector**: it can combine **API responses** and **HTML scraping results** into a single **unified record** per source, then export aggregated results as **CSV** and **JSON**.

The architecture is intentionally small and modular to maximize:
- adaptability to new targets through configuration
- deterministic, offline-capable testing in CI
- clarity of responsibilities across modules

---

## Table of Contents

- [Goals and non-goals](#goals-and-non-goals)
- [System overview](#system-overview)
  - [High-level data flow](#high-level-data-flow)
  - [Component diagram](#component-diagram)
- [Runtime pipeline](#runtime-pipeline)
  - [Per-source execution](#per-source-execution)
  - [Context and URL templating](#context-and-url-templating)
- [Configuration model](#configuration-model)
  - [Top-level YAML shape](#top-level-yaml-shape)
  - [Source schema](#source-schema)
  - [API schema](#api-schema)
  - [HTML schema](#html-schema)
  - [Mapping and typing](#mapping-and-typing)
  - [Environment variable expansion](#environment-variable-expansion)
- [Core modules and responsibilities](#core-modules-and-responsibilities)
- [Error handling and resilience](#error-handling-and-resilience)
  - [Retry policy](#retry-policy)
  - [Failure modes](#failure-modes)
- [Outputs](#outputs)
- [Testing strategy](#testing-strategy)
- [Security and responsible use](#security-and-responsible-use)
- [Extensibility guide](#extensibility-guide)
- [Known limitations](#known-limitations)
- [Related documentation](#related-documentation)

---

## Goals and non-goals

### Goals

- **Config-first execution:** add/modify sources by editing YAML rather than rewriting core logic.
- **Hybrid acquisition:** support API and HTML collection in the same run for a source.
- **Deterministic tests:** CI runs without live network dependency (HTTP is mocked).
- **Separation of concerns:** config → fetch → extract → normalize → validate → export.
- **Practical exports:** CSV/JSON outputs that downstream pipelines can consume.

### Non-goals

- **No always-on service:** this is a run-and-exit CLI.
- **No built-in scheduling:** scheduling is intentionally a stub/example, not runtime behavior.
- **No persistence layer:** no database or incremental state is shipped by default.
- **No concurrency:** sequential execution keeps behavior predictable and easier to audit.
- **No rate limiting/backoff policy enforcement:** hardening ideas exist, but are not implemented by default.

---

## System overview

### High-level data flow

At a high level:

1. Load a YAML config describing a list of sources.
2. For each source:
   - Optionally fetch API data and extract fields.
   - Optionally fetch HTML and extract fields.
   - Normalize extracted values into a unified record (optionally cast types).
   - Validate required fields.
3. Export the aggregated list of records.

### Component diagram

```mermaid
flowchart LR
  A[CLI] --> B[Config Loader]
  B --> C{For each source}
  C -->|API enabled| D[ApiClient]
  C -->|HTML enabled| E[HTML Scraper]
  D --> F[Normalizer]
  E --> F[Normalizer]
  F --> G[Validator]
  G --> H[Exporter]
  H --> I[(CSV / JSON)]
````

---

## Runtime pipeline

### Per-source execution

For each configured `source`:

1. **Context construction**

   * The CLI builds a small `context` dictionary.
   * Current default context includes:

     * `external_id`: derived from `source.id`

2. **API step (optional)**

   * If `api.enabled: true`:

     * Format `api.base_url` using `str.format(**context)`
     * Perform request via `requests.request(method, url, params=..., headers=..., timeout=...)`
     * Extract selected values using dot-path JSON traversal (`json_key_map`)

3. **HTML step (optional)**

   * If `html.enabled: true`:

     * Format `html.url` using `str.format(**context)`
     * Fetch page via `requests.get(url, headers=..., timeout=...)`
     * Parse with BeautifulSoup and extract fields using CSS selectors (supports `::attr(...)`)

4. **Normalization**

   * Apply `mapping.unified_fields` to produce a unified record.
   * Mapping expressions reference either `api.*` or `html.*` namespaces.
   * Apply `mapping.field_types` (optional) to cast values to `int`/`float`.

5. **Validation**

   * Validate required fields for missing/empty values.
   * Current CLI behavior treats **all unified fields** as required.

6. **Export**

   * Unless in dry-run mode, write CSV and JSON outputs.

### Context and URL templating

Both API and HTML URLs support Python string formatting:

* API: `base_url.format(**context)`
* HTML: `url.format(**context)`

If a URL references a placeholder not present in the context, execution fails early with a clear error indicating the missing key.

---

## Configuration model

### Top-level YAML shape

The configuration file is a **YAML list** of source entries (not a dict).

A minimal working example (shape-accurate):

```yaml
- id: "example-source"
  api:
    enabled: true
    base_url: "https://example.com/api/items/{external_id}"
    method: "GET"
    headers:
      Authorization: "Bearer ${API_TOKEN}"
    params:
      limit: 10
    json_key_map:
      title: "data.title"
      price: "data.price"
  html:
    enabled: true
    url: "https://example.com/items/{external_id}"
    selectors:
      image_url: "img.product::attr(src)"
      description: "div.description"
  mapping:
    unified_fields:
      title: "api.title"
      price: "api.price"
      image_url: "html.image_url"
      description: "html.description"
    field_types:
      price: "float"
```

A tested reference is provided in `config/sources.example.yml`.

### Source schema

Each source entry supports:

* **Required**

  * `id` (string)
  * `mapping` (object)
* **Optional**

  * `api` (object)
  * `html` (object)

A source must provide at least one of `api` or `html` as an object. Either can be present and disabled with `enabled: false`.

### API schema

`api` supports:

* `enabled` (bool, default `true`)
* `base_url` (string, required when enabled)
* `method` (string, default `GET`)
* `params` (dict, optional)
* `headers` (dict, optional)
* `json_key_map` (dict, optional)

#### `json_key_map`: JSON path extraction

`json_key_map` describes how to extract fields from a JSON response.

* Keys: output field names (the “API-side extracted field keys”)
* Values: dot-separated paths into the JSON payload

Examples:

* `data.title`
* `items.0.name` (numeric segments can index into lists)

If traversal fails (missing key, wrong type, out-of-range index), the extracted value becomes `null` (not fatal).

### HTML schema

`html` supports:

* `enabled` (bool, default `true`)
* `url` (string, required when enabled)
* `selectors` (dict[str, str], optional)

#### Selector semantics (implemented)

* Selection is via BeautifulSoup CSS selection (`soup.select(...)`).
* Only the **first match** is used.
* Default extraction: `element.get_text(strip=True)`.
* Attribute extraction: `selector::attr(name)`
  Example: `img.product::attr(src)`

If a selector matches nothing, the extracted value becomes `null`.

### Mapping and typing

`mapping` supports:

* `unified_fields` (dict[str, str], required)

  * Values are mapping expressions pointing into extracted namespaces:

    * `api.<field_key>`
    * `html.<field_key>`
* `field_types` (dict[str, str], optional)

  * Supported types: `int`, `float`
  * Conversion failures yield `null` (not an exception)

**Note on mapping expressions:** the normalizer expects expressions with at least one `.` segment (namespace + key). Invalid expressions resolve to `null`.

### Environment variable expansion

All strings in YAML are recursively expanded using environment variables (e.g., `${API_TOKEN}`).

Important operational note:

* The CLI does **not** automatically load `.env`. Environment variables must be set by the runtime environment (or loaded externally).

---

## Core modules and responsibilities

The implementation is deliberately decomposed into small modules:

* `src/hybrid_collector/cli.py`

  * Orchestrates the pipeline: load config → per-source run → normalize → validate → export.
  * Builds the runtime context (`external_id`).
  * Supports dry-run mode (skips file writes).

* `src/hybrid_collector/config.py`

  * Defines config dataclasses:

    * `SourceConfig`, `ApiConfig`, `HtmlConfig`, `MappingConfig`
  * Loads YAML and validates structure/types.
  * Expands environment variables in the loaded config.
  * Intentionally does not validate “semantic correctness” of selectors or mapping beyond structural checks.

* `src/hybrid_collector/api_client.py`

  * Performs API requests via `requests.request(...)`.
  * Extracts fields using dot-path traversal (`extract_json_value`).
  * Raises explicit errors on missing URL context keys and HTTP failures.

* `src/hybrid_collector/scraper.py`

  * Performs HTML fetch via `requests.get(...)`.
  * Parses with BeautifulSoup and extracts fields using selectors.
  * Supports `::attr(...)`; otherwise extracts stripped text.

* `src/hybrid_collector/normalizer.py`

  * Merges API and HTML extracted fields into a unified record using `mapping.unified_fields`.
  * Applies optional type casting via `mapping.field_types`.

* `src/hybrid_collector/validator.py`

  * Validates required fields:

    * missing key, `null`, or empty string are treated as invalid
  * Current CLI treats all unified fields as required.

* `src/hybrid_collector/exporter.py`

  * Exports aggregated records to:

    * `unified_records.csv` (header is union of keys across all records)
    * `unified_records.json` (pretty printed, UTF-8, `ensure_ascii=False`)

* `src/hybrid_collector/scheduler_stub.py`

  * Example helper for cron expressions.
  * Not used by runtime pipeline.

---

## Error handling and resilience

### Retry policy

Both API and HTML fetchers implement a minimal retry policy:

* Retries on:

  * `requests.exceptions.RequestException` (network-level failures)
  * HTTP **5xx** responses
* Fail-fast on:

  * HTTP **4xx** responses (after `raise_for_status()`)
* Backoff:

  * no exponential backoff or jitter; retries are immediate

The defaults are intentionally conservative for predictability in templates. For production usage, consider adding backoff/jitter and rate limiting (see [Extensibility guide](#extensibility-guide)).

### Failure modes

* **Missing context key in URL template**

  * Explicit error indicating which key is missing.

* **HTTP 4xx**

  * Fail-fast; no retry.

* **HTTP 5xx / transient network errors**

  * Retries up to max retries; then raises error.

* **JSON key path misses**

  * Extracted field becomes `null`.

* **Selector misses**

  * Extracted field becomes `null`.

* **Type conversion errors**

  * Field becomes `null`.

* **Validation failures**

  * Missing/empty required fields are reported as validation issues.

---

## Outputs

Default export artifacts (when not dry-run):

* `unified_records.csv`

  * Columns: union of all keys across the record list.
* `unified_records.json`

  * Array of unified records.
  * UTF-8 and human-readable formatting.

---

## Testing strategy

The test suite is designed to be deterministic and CI-friendly:

* Unit tests cover:

  * Config loading and environment expansion
  * JSON path extraction behavior
  * HTML extraction behavior (including `::attr(...)`)
  * Normalization and type casting
  * Validation logic
  * Export formatting
  * CLI dry-run behavior
* Integration test:

  * Runs the pipeline against `config/sources.example.yml`
  * Mocks all HTTP calls so no live network is required

CI runs:

* `ruff check`
* `pytest`

---

## Security and responsible use

This repository is a template and must be used responsibly:

* Follow site Terms of Service and applicable legal requirements.
* Respect robots directives where relevant.
* Avoid collecting sensitive personal data unless you have explicit authorization.
* Keep secrets out of version control; use environment variables.

For detailed guidance, see `docs/SECURITY_AND_LEGAL.md`.

---

## Extensibility guide

Common extensions (kept intentionally out of the default template):

1. **Rate limiting and politeness**

   * add per-host delays, jitter, and maximum request rate
   * implement exponential backoff for retries

2. **Config-driven network controls**

   * configurable timeout, max retries, User-Agent, proxy settings

3. **Optional vs required fields**

   * support required/optional field declarations in config
   * validate only required fields in the CLI

4. **Config semantic validation**

   * validate mapping expressions (`api.*` / `html.*`)
   * validate selector syntax (and reject unsupported patterns early)

5. **Persistence and incremental runs**

   * store records in SQLite/Postgres
   * deduplicate by stable keys
   * incremental “only new/changed” record collection

6. **Concurrency**

   * add limited parallelism with safe throttling and backpressure

7. **Scheduling**

   * integrate with cron/systemd/GitHub Actions
   * connect `scheduler_stub.py` to a real scheduling mechanism

---

## Known limitations

* Sequential execution only (no concurrency).
* No built-in rate limiting or backoff/jitter.
* `.env` is not auto-loaded; environment variables must be managed externally.
* Config validation is structural; selector/mapping semantics are not fully validated.
* CLI treats all unified fields as required (optional fields require enhancement).
* No persistence/state store is included by default.

---

## Related documentation

* `README.md` — product overview and usage
* `docs/CONFIG_GUIDE.md` — configuration guide (ensure it matches the implemented YAML list schema)
* `docs/operations.md` — operational guidance and hardening ideas
* `docs/testing.md` — local + CI testing instructions
* `docs/SECURITY_AND_LEGAL.md` — security, compliance, and responsible use guidance
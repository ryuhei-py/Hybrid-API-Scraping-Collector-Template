# Architecture
This document describes how the template combines API and HTML collection into a unified dataset.

## Goals and non-goals
This section clarifies what the template aims to achieve and what it intentionally excludes.

### Goals
This subsection lists the primary objectives of the template.

- Provide a **config-driven template** that can be quickly adapted to real client projects.
- Combine **multiple heterogeneous sources** (REST APIs + HTML pages) into a single dataset.
- Keep the codebase **small, readable, and testable**, suitable as a portfolio repo.
- Make it easy to:
  - Add or remove sources by editing a **YAML config** instead of code.
  - Extend with new APIs, sites, or exporters with minimal changes.
  - Run the whole pipeline via a **single CLI command**.

### Non-goals
This subsection outlines what is intentionally out of scope.

- This is **not** a full ETL platform or workflow engine.
- It does **not** provide:
  - Built-in scheduling (cron, Airflow, etc.)—only examples.
  - Long-term storage (no database by default).
  - A web UI or dashboard.
- The template is intentionally minimal so it can be customized per project.

## High-level architecture
This section explains the layers and overall orchestration of the system.

### Layers
This subsection introduces the logical layers of the template.

The architecture is organized into five logical layers:

1. **Configuration Layer**
   - Parses YAML configuration (`config/sources.yml`).
   - Models sources as Python dataclasses (API, HTML, mapping).
2. **Collection Layer**
   - **API client**: executes HTTP requests, extracts JSON fields.
   - **HTML scraper**: fetches pages, parses DOM, extracts values using CSS selectors.
3. **Normalization Layer**
   - Combines API and HTML results into a single **unified record**.
   - Applies field mapping and type casting.
4. **Quality Layer**
   - Validates records (e.g. required fields not empty).
   - Produces a list of issues for debugging and QA.
5. **Delivery Layer**
   - Exports unified records to **CSV/JSON** (and optionally Excel).
   - Integrates with the CLI to produce artifacts for clients and downstream tools.

The entire pipeline is orchestrated by a **CLI entrypoint** that ties these layers together.

### Component map
This subsection lists the key modules and supporting directories.

Code lives under `src/hybrid_collector`:

- `config.py` — configuration dataclasses and YAML loader.
- `api_client.py` — API client and JSON extraction.
- `scraper.py` — HTML fetching and parsing.
- `normalizer.py` — unifies API + HTML into normalized records.
- `exporter.py` — CSV/JSON(/Excel) exporters.
- `validator.py` — lightweight record validation.
- `cli.py` — CLI pipeline (read config → collect → normalize → validate → export).
- `scheduler_stub.py` — examples for cron / Task Scheduler integration.

Auxiliary directories:

- `config/` — configuration files (e.g. `sources.example.yml`).
- `sample_output/` — example output (`unified_records.sample.csv`).
- `docs/` — documentation (this file and others).
- `tests/` — unit tests per module.
- `.github/workflows/` — CI configuration stub.

### Data flow
This subsection visualizes how data moves through the layers.

```mermaid
flowchart LR
    A[config/sources.yml] --> B[Configuration Layer<br/>config.py]
    B --> C[API Client<br/>api_client.py]
    B --> D[HTML Scraper<br/>scraper.py]

    C --> E[API Values]
    D --> F[HTML Values]

    E --> G[Normalizer<br/>normalizer.py]
    F --> G

    G --> H[Unified Records]
    H --> I[Validator<br/>validator.py]
    H --> J[Exporter<br/>exporter.py]

    I --> K[Validation Report (logs)]
    J --> L[CSV/JSON/Excel Files]

    subgraph Orchestration
        M[CLI<br/>cli.py]
    end

    A --> M
    M --> C
    M --> D
    M --> G
    M --> I
    M --> J
```

## Components
This section describes each layer and its responsibilities.

### Configuration layer (config.py, config/)
This subsection explains how configuration is modeled and validated.

Responsibilities:

- Define configuration dataclasses, for example:
  - ApiConfig
  - HtmlConfig
  - MappingConfig
  - SourceConfig
- Load YAML from `config/sources.yml` (or another file passed via CLI).
- Resolve environment variables (e.g. `${API_TOKEN}`) for secrets.
- Validate basic structure and raise a configuration error if required fields are missing.

Why a separate config layer?

- New sources (APIs/sites) can be added without touching code.
- The same code can be reused across multiple projects just by swapping `sources.yml`.

### Collection layer
This subsection covers how data is collected from APIs and HTML pages.

#### API client (api_client.py)
This sub-subsection outlines HTTP collection from APIs.

Responsibilities:

- Build and execute HTTP requests based on ApiConfig:
  - URL template (`base_url`) with placeholders (e.g. `{external_id}`).
  - Method (GET, POST, etc.).
  - Query parameters and headers.
- Implement retry logic for transient failures (network errors, 5xx).
- Parse JSON responses and extract specific fields using dot-separated paths (e.g. `data.price.current`).
- Return a flat dictionary of API values, for example:

```python
{
    "external_id": "12345",
    "api_price": 19.99,
    "currency": "USD",
}
```

Design notes:

- The client is intentionally stateless and simple.
- It focuses on HTTP + JSON extraction, not on domain logic.
- Mapping to unified field names is handled later by the normalization layer.

#### HTML scraper (scraper.py)
This sub-subsection outlines HTML collection and parsing.

Responsibilities:

- Fetch HTML pages using HTTP with retry logic similar to the API client.
- Allow URL templates with placeholders (e.g. `https://example.com/products/{external_id}`).
- Parse HTML using BeautifulSoup.
- Extract values using selectors defined in `HtmlConfig.selectors`, supporting:
  - Plain selectors: `span.price` → `element.text`.
  - Attribute selectors: `img.main::attr(src)` → `element['src']`.
- Return a flat dictionary of HTML values, for example:

```python
{
    "title": "Example Product",
    "price": "$19.99",
    "image_url": "https://example.com/img/12345.jpg",
}
```

Design notes:

- The scraper does not try to be a generic crawling framework.
- It only handles URLs explicitly defined in the config, which matches typical Upwork-style project requirements.

### Normalization layer (normalizer.py)
This subsection explains how data is unified into a common schema.

Responsibilities:

- Combine outputs from the API client and the HTML scraper into a single record.
- Use MappingConfig to map fields:
  - `unified_fields` maps target field names to `api.<key>` or `html.<key>`.

Example:

```yaml
mapping:
  unified_fields:
    id: "api.external_id"
    title: "html.title"
    price: "api.api_price"
    currency: "api.currency"
  field_types:
    price: "float"
```

For each unified field:

- Look up the appropriate source dictionary (`api_values` or `html_values`).
- Handle missing dictionaries or keys by returning `None`.
- Apply optional type conversions using `field_types` (e.g. `float`, `int`).

Why normalize?

- Downstream tools (Excel, BI, ML) expect a consistent schema.
- Normalization decouples “how we fetched the data” from “how we present it”.

### Quality layer (validator.py)
This subsection covers validation of normalized records.

Responsibilities:

- Provide simple, extensible validation of unified records.

Typical checks:

- Required fields must not be `None` or an empty string.
- Numeric fields should be convertible to the desired type.

Return a list of validation issues, each including:

- Record index.
- Field name.
- Message describing the problem.

Design notes:

- The validation logic is intentionally lightweight.
- For more complex projects, this module can be extended with:
  - Cross-field consistency checks.
  - Range checks (e.g. price > 0).
  - Business-specific rules.

### Delivery layer (exporter.py)
This subsection describes how results are written out.

Responsibilities:

- Convert a list of unified records into file formats that are easy to share:
  - CSV (UTF-8)
  - JSON (array of objects)
  - Optional Excel (via pandas)
- Derive column order from the union of keys across all records.
- Ensure parent directories exist before writing.

Typical outputs:

- `sample_output/unified_records.csv`
- `sample_output/unified_records.json`

These files can be attached to Upwork deliveries or imported into BI tools.

### Orchestration (cli.py, scheduler_stub.py)
This subsection explains how the pipeline is executed end to end.

#### cli.py
This sub-subsection covers the command-line orchestration layer.

Responsibilities:

- Provide a user-facing entrypoint that runs the entire pipeline:
  - Parse CLI arguments:
    - `--config` (path to YAML).
    - `--output-dir` (where to place CSV/JSON).
    - `--dry-run` (run without writing files).
  - Load sources via `config.py`.
  - For each source:
    - Build a context dict (e.g. `{"external_id": source.id}`).
    - Call API client and HTML scraper.
    - Normalize into a unified record.
    - Run validation over all records.
    - Log or print validation issues.
  - If not `--dry-run`, export to CSV/JSON.

#### scheduler_stub.py
This sub-subsection lists scheduling examples for production use.

Responsibilities:

- Document how to schedule the CLI in production environments.
- Provide example snippets for:
  - Unix cron.
  - Windows Task Scheduler.

The module exists primarily as documentation in code form, not as a runtime dependency.

## Execution lifecycle
This section outlines the typical steps when running the collector.

A typical execution of the collector follows this lifecycle:

1. Start CLI

    ```bash
    python -m hybrid_collector.cli --config config/sources.yml --output-dir sample_output
    ```

2. Configuration
   - `load_sources()` parses the YAML file.
   - Dataclasses are created for each source.
3. Collection
   - For each source:
     - API client fetches JSON and extracts API values.
     - HTML scraper fetches and parses HTML, extracting HTML values.
4. Normalization
   - `normalize_record()` merges API/HTML values according to mapping rules.
   - A list of unified records is constructed.
5. Validation
   - Validation checks are run over all records.
   - Issues are logged or printed to stderr/stdout.
6. Export
   - Records are written to CSV/JSON (and optionally Excel) under `output_dir`.
7. Exit
   - The CLI exits with success or a non-zero code on fatal errors.

## Extensibility
This section describes how to extend the template safely.

The template is designed to be extended in small, focused ways.

### Adding a new source
This subsection covers how to add new API or HTML sources.

- Add a new entry to `config/sources.yml` with:
  - API and/or HTML configuration.
  - Mapping rules for unified fields.
- Optionally extend tests to cover the new configuration shape.
- No changes to core modules are required unless you introduce new patterns.

### Adding a new API pattern
This subsection covers adding specialized API handling.

- If a new API requires special handling (e.g. OAuth, pagination):
  - Add helper functions or methods to `api_client.py`.
  - Keep the configuration model backward-compatible where possible.
  - Extend tests in `tests/` to cover the new behavior.

### Adding a new output format
This subsection covers adding new delivery formats.

- Implement additional exporter functions in `exporter.py` (e.g. Parquet, database writer).
- Optionally add a CLI flag (e.g. `--export-format`) to switch formats.

### Integrating with a database
This subsection explains how to store results in a database.

- Add a new module (e.g. `storage.py`) to insert unified records into a DB.
- Call it from `cli.py` after validation and before/after file export.

## Error handling and observability
This section summarizes error handling and logging practices.

### Error handling
This subsection lists expected error behaviors.

- Configuration errors: surface early with clear messages (missing keys, invalid types).
- HTTP errors:
  - Retries on transient issues (network errors, 5xx).
  - Fail fast on 4xx unless explicitly configured otherwise.
- Parsing errors:
  - JSON parse failures → API error with context.
  - Missing HTML elements → `None` values that can be caught by validation.

### Logging and debugging
This subsection suggests how to observe runs.

- The template can be wired to Python’s logging module (not mandatory).
- Recommended logging points:
  - Start/end of each run.
  - Per-source success/failure.
  - Summary of validation issues.
  - Output file locations.

## Design trade-offs
This section calls out key decisions and their pros/cons.

- No database by default  
  Pros: simple setup, easy to clone and run, fewer dependencies.  
  Cons: no built-in history or time-series analysis.
- Config-driven vs. hard-coded  
  Pros: easier reuse and adaptation to new sites/APIs.  
  Cons: some complexity in configuration files (YAML must be managed carefully).
- Single-process pipeline  
  Pros: straightforward to understand and debug.  
  Cons: for very large source lists, you may want parallelization (e.g. asyncio, multiprocessing), which is left as an exercise.

This balance keeps the repository small but realistic, suitable both as a starting point for production work and as a clear portfolio example.

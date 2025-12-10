# Configuration guide
This document explains how to configure the hybrid API and scraping collector using YAML and environment variables.

## Configuration files overview
This section lists the files that control sources and secrets.

### `.env` and environment variables
Secrets (API keys, tokens, proxies, etc.) should **never** be hard-coded in YAML.

Steps:

1. Copy the example file:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set real values (this file should be ignored by Git).

In YAML, reference them with `${VAR_NAME}`, for example:

```yaml
headers:
  Authorization: "Bearer ${EXAMPLE_API_TOKEN}"
```

The Python code will load `.env` and expand `${...}` placeholders before sending requests.

### YAML configuration files
The core configuration for the collector lives under the `config/` directory.

- `config/sources.example.yml` — example configuration shipped with the template. Use this as the base for your own config.
- `config/sources.yml` — your real configuration. Typically you create it by:

  ```bash
  cp config/sources.example.yml config/sources.yml
  ```

  and then editing `config/sources.yml`.

Recommended: keep `config/sources.yml` out of version control (e.g. via `.gitignore`) if it contains client-specific details.

## Quick start
This section outlines the minimal steps to get a working configuration.

- Create your working config:

  ```bash
  cp config/sources.example.yml config/sources.yml
  ```

- Fill in `.env`:
  - API keys (e.g. `EXAMPLE_API_TOKEN`)
  - Proxy settings (if needed)
  - Any other secrets referenced in YAML
- Edit `config/sources.yml`:
  - Start from the provided example sources
  - Rename each `id` to something meaningful for your project
  - Update API endpoints, HTML URLs, selectors, and mappings
- Run a dry-run or validation command (see `docs/operations.md` for the latest CLI examples).
  - First: run a “config validation” / “dry-run” mode
  - Then: run the normal collection to produce a sample CSV in `sample_output/`

If anything fails, the collector will log which source and which part of the config caused the error.

## Unified record schema
This section explains how raw data is normalized into a consistent schema.

A typical unified record looks like this (conceptually):

```text
id              # Primary key in this dataset (string)
source          # Source ID from config (e.g. "example_api")
source_type     # "api" or "html"
group           # Optional logical group (e.g. "real_estate", "cars")

external_id     # ID from the original site/API
name            # Title / name of the entity
category        # Optional category / type
price           # Numeric price (if applicable)
currency        # ISO currency code (e.g. "USD", "JPY")
url             # Canonical URL for the item
location        # Optional location field (city, state, etc.)
collected_at    # ISO-8601 timestamp when the record was collected

# Any additional fields are allowed as long as they are consistent for your use case
```

The validator module uses a combination of:

- A built-in default schema (core fields above), and/or
- An optional schema section in `config/sources.yml`

to check:

- Required fields are present
- Types are coherent (e.g. price is numeric, `collected_at` looks like a timestamp)
- Values are not obviously invalid (empty IDs, empty URLs, etc.)

You can keep the schema minimal at the beginning and gradually tighten it as you move toward production.

## Top-level YAML structure
This section shows the overall shape of `config/sources.yml`.

```yaml
# Global defaults and behavior (optional)
global:
  timezone: "Asia/Tokyo"
  default_currency: "JPY"
  request_timeout_sec: 10
  max_retries: 3
  retry_backoff_sec: 1.0
  user_agent: "HybridCollector/1.0 (+https://example.com)"

# Optional explicit schema definition for the unified record
schema:
  id:
    type: string
    required: true
  source:
    type: string
    required: true
  source_type:
    type: string
    required: true
  external_id:
    type: string
    required: true
  name:
    type: string
    required: false
  price:
    type: number
    required: false
  currency:
    type: string
    required: false
  url:
    type: string
    required: false
  collected_at:
    type: datetime
    required: true

# List of all configured sources
sources:
  - id: example_api
    enabled: true
    kind: api
    # ...
  - id: example_html
    enabled: true
    kind: html
    # ...
```

Note: the exact keys under `global` and `schema` may evolve with the codebase. The shipped `config/sources.example.yml` is always the canonical reference.

## Source definition (common fields)
This section describes the fields shared by API and HTML sources.

```yaml
sources:
  - id: example_api
    enabled: true
    kind: api                # "api" or "html"
    group: "example_group"   # optional logical group
    tags:                    # optional labels
      - "demo"
      - "public_api"
    notes: "Short human description for this source"
    # next: api/html config + mapping...
```

Field reference:

- `id` (string, required) — unique identifier for this source within the config; used in logs and written into the `source` field of unified records.
- `enabled` (bool, required) — if `false`, the source is ignored without deleting its configuration.
- `kind` (string, required) — `api` for HTTP JSON APIs, `html` for HTML page scraping.
- `group` (string, optional) — logical grouping (“cars”, “housing”, “products”); useful when running subsets of sources or for downstream analytics.
- `tags` (list of strings, optional) — free-form labels you can use for filtering, documentation, or future automation.
- `notes` (string, optional) — human-readable comments about where the source comes from or any special behavior.

After these common fields, the structure diverges depending on `kind`.

## API sources
This section explains how to configure API sources.

### Basic structure
```yaml
- id: example_api
  enabled: true
  kind: api
  group: "demo"

  api:
    base_url: "https://api.example.com/v1/items"
    method: GET           # GET, POST, etc.
    headers:
      Authorization: "Bearer ${EXAMPLE_API_TOKEN}"
      Accept: "application/json"
    params:
      category: "laptops"
      page: "{page}"
      per_page: 50
    body: {}              # Only for POST/PUT/PATCH if needed
    items_path: "data.items"   # Where the list of items lives in the JSON

    pagination:
      strategy: page       # "page" or "none"
      page_param: page
      start: 1
      max_pages: 5         # Safety guard

  mapping:
    id: "id"                    # JSON path relative to each item
    external_id: "id"
    source: "$SOURCE_ID"        # special token
    source_type: "$SOURCE_KIND" # "api"
    name: "title"
    price: "pricing.current"
    currency: "pricing.currency"
    url: "urls.detail"
    collected_at: "$NOW"        # special token
```

Key sections:

- `api.base_url` (string, required) — base endpoint for the API call. Can be a fixed URL or a URL with placeholders you fill via params or other logic.
- `api.method` (string, required) — HTTP method (`GET` default, or `POST`, `PUT`, etc.).
- `api.headers` (mapping, optional) — custom headers to send with each request; values can include `${ENV_VAR}` placeholders.
- `api.params` (mapping, optional) — query parameters appended to `base_url`; you can use `{page}` or other placeholders for simple pagination.
- `api.body` (mapping or object, optional) — used for POST / PUT APIs; often not needed for simple collection.
- `api.items_path` (string, required) — dot-separated path inside the returned JSON where the list of items lives.
- `api.pagination` (mapping, optional) — simple built-in pagination support; if `strategy` is `none` or omitted, only a single request is issued.

### Mapping JSON to the unified schema
This subsection explains how to map API JSON fields to unified fields.

Rules:

- Keys in `mapping` = names in the unified schema (`id`, `source`, `price`, etc.).
- Values = paths inside the JSON item, or special tokens.

Supported patterns (conceptually):

- `simple_field` → top-level key
- `nested.field` → nested objects

Special tokens:

- `$SOURCE_ID` → automatically replaced by this source’s `id`
- `$SOURCE_KIND` → `"api"`
- `$NOW` → current timestamp in ISO-8601 format

Typical example:

```yaml
mapping:
  id: "id"
  external_id: "id"
  source: "$SOURCE_ID"
  source_type: "$SOURCE_KIND"
  name: "title"
  price: "pricing.current"
  currency: "pricing.currency"
  url: "urls.detail"
  collected_at: "$NOW"
```

If a path does not exist, the field becomes `null` unless the validator marks it as required.

## HTML scraping sources
This section explains how to configure HTML sources.

### Basic structure
```yaml
- id: example_html
  enabled: true
  kind: html
  group: "demo"

  html:
    url_template: "https://example.com/laptops?page={page}"
    start_page: 1
    max_pages: 3
    allow_redirects: true

  selectors:
    list: "div.product-card"    # CSS selector for each item container

    fields:
      external_id: "@data-product-id"              # attribute on the item node
      name: ".product-title"                       # text from child node
      price: ".product-price"                      # text
      currency: ".product-currency"                # text
      url: "a.product-link::attr(href)"            # attribute on link

  mapping:
    id: "external_id"
    external_id: "external_id"
    source: "$SOURCE_ID"
    source_type: "$SOURCE_KIND"
    name: "name"
    price: "price"
    currency: "currency"
    url: "url"
    collected_at: "$NOW"
```

Key sections:

- `html.url_template` (string, required) — base URL (often with a `{page}` placeholder) for pagination. Without pagination, you can omit `{page}` and the `start_page` / `max_pages` keys.
- `html.start_page` / `html.max_pages` (integers, optional) — controls the page range. If omitted, a default single page is usually scraped (see the shipped example).
- `selectors.list` (string, required) — CSS selector used to find each “item” container on the page.
- `selectors.fields` (mapping, required) — for each logical field, a selector or attribute instruction. Common patterns:
  - `.product-title` → text content of the first matching element
  - `a.product-link::attr(href)` → value of a specific attribute
  - `@data-id` → attribute on the item node itself (shorthand)

### Mapping HTML to the unified schema
This subsection explains how to map HTML fields to unified fields.

Keys: unified schema fields (`id`, `name`, `price`, etc.)

Values: names from `selectors.fields` or special tokens.

```yaml
mapping:
  id: "external_id"
  external_id: "external_id"
  source: "$SOURCE_ID"
  source_type: "$SOURCE_KIND"  # "html"
  name: "name"
  price: "price"
  currency: "currency"
  url: "url"
  collected_at: "$NOW"
```

If a CSS selector fails to match, the raw field may be `null` and the validator will decide whether that is acceptable.

## Using environment variables in YAML
This section shows how to inject environment-specific values safely.

As mentioned earlier, you can inject secrets and environment-specific values via `${VAR_NAME}`.

Examples:

```yaml
api:
  headers:
    Authorization: "Bearer ${EXAMPLE_API_TOKEN}"
  params:
    api_key: "${PUBLIC_API_KEY}"

html:
  proxy: "${SCRAPING_PROXY_URL}"
```

Guidelines:

- Keep `.env` for secrets and local machine overrides.
- For CI or production, set the same variables at the process or container level.
- Avoid checking `.env` into version control.

## Common patterns and tips
This section provides practical guidance for adapting the template.

### Safely cloning an existing source
When adding a new site that looks similar to an existing one:

- Copy an existing source block.
- Change `id` and `group`.
- Update `api` or `html` settings (endpoint, URL, selectors).
- Run collection in dry-run mode and inspect the sample CSV.

This is the fastest way to onboard new Upwork projects using this template.

### Dealing with fields that only exist in some sources
You have several options:

- Make the field optional in `schema` (or not listed at all).
- Set `mapping` only for sources where it exists; for other sources, leave it unmapped.
- In downstream tools (Excel, BI, etc.), treat missing values as `NULL`.

Avoid forcing every source to provide every field if it does not make sense.

### Tightening validation for production
For portfolio demos, a looser schema is acceptable. For real clients, you may want stricter guarantees:

- Mark more fields as required in `schema`.
- Use the validator to fail fast when required data is missing.
- Add simple range checks (e.g. price must be positive) either in the validator or downstream.

## Where to go next
This section links to related documentation for deeper context.

- See `docs/architecture.md` for a structural view of how configuration flows through the pipeline: config loader → API client / HTML scraper → normalizer → validator → exporter.
- See `docs/operations.md` for CLI commands, example dry-run and production runs, and how to schedule periodic execution.

Configuration is the main surface you touch when adapting this template to real jobs. Once you understand `config/sources.yml`, adding new sites becomes mostly a YAML-only task.

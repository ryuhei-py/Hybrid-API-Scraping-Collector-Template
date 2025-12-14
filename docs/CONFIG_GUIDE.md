# CONFIG_GUIDE

This document defines the **configuration contract implemented by this repository** and explains how to write reliable, testable YAML configs for the Hybrid-API-Scraping-Collector-Template.

The template supports:
- **API collection** (HTTP request + JSON extraction)
- **HTML collection** (HTTP GET + CSS selector extraction)
- **Hybrid collection** (API + HTML merged into unified records)
- **Normalization** (mapping + optional type casting)
- **Validation** (required-field checks)
- **Offline testing** (CI runs without live network access)

---

## Table of Contents

- [Quick reference](#quick-reference)
- [1. File format and loading rules](#1-file-format-and-loading-rules)
- [2. Source schema](#2-source-schema)
- [3. API configuration](#3-api-configuration)
- [4. HTML configuration](#4-html-configuration)
- [5. Mapping and normalization](#5-mapping-and-normalization)
- [6. URL templating via context](#6-url-templating-via-context)
- [7. Validation and failure modes](#7-validation-and-failure-modes)
- [8. Complete examples](#8-complete-examples)
- [9. Practical guidance](#9-practical-guidance)
- [Related documentation](#related-documentation)

---

## Quick reference

### Minimum valid config (YAML list)
```yml
- id: example
  api:
    enabled: false
    base_url: "https://example.invalid"
  html:
    enabled: true
    url: "https://example.com/items/{external_id}"
    selectors:
      title: "h1"
  mapping:
    unified_fields:
      title: "html.title"
````

### Key rules (implemented in code)

* The config file is a **YAML list** (not a top-level `sources:` object).
* Each list item is one **source**.
* A source must define at least one of `api` or `html`.
* If `api.enabled: true`, `api.base_url` is required.
* If `html.enabled: true`, `html.url` is required.
* HTML selector extension supported: **`::attr(name)` only**.
* Mapping expressions must use the prefixes **`api.`** or **`html.`**.

---

## 1. File format and loading rules

### 1.1 YAML root must be a list

The configuration file is a YAML list, where each item describes one source:

```yml
- id: source-a
  api: ...
  html: ...
  mapping: ...
- id: source-b
  api: ...
  mapping: ...
```

### 1.2 Environment variable expansion

All strings in the loaded YAML are expanded using environment variables (recursively). Use this for secrets and environment-specific values:

```yml
headers:
  Authorization: "Bearer ${API_TOKEN}"
```

Notes:

* The CLI does **not** automatically load `.env`. If you use a `.env` file, load it externally (shell) or extend the CLI explicitly.
* Prefer `${VAR}` placeholders over committing secrets.

---

## 2. Source schema

Each list entry follows this structure:

```yml
- id: string                 # required
  api: ApiConfig | null      # optional
  html: HtmlConfig | null    # optional
  mapping: MappingConfig     # required
```

### 2.1 Required fields

* `id`
* `mapping.unified_fields`

### 2.2 Validity rules

A source is considered valid if:

* At least one of `api` or `html` is present, and
* When present and enabled, the required URL field exists:

  * `api.enabled: true` requires `api.base_url`
  * `html.enabled: true` requires `html.url`

---

## 3. API configuration

### 3.1 ApiConfig schema

```yml
api:
  enabled: true                 # optional (default: true)
  base_url: "https://..."       # required if enabled
  method: "GET"                 # optional (default: GET)
  params:                       # optional
    q: "keyword"
  headers:                      # optional
    Authorization: "Bearer ${API_TOKEN}"
  json_key_map:                 # optional (recommended if API is enabled)
    id: "id"
    user_name: "user.name"
    first_tag: "tags.0"
```

### 3.2 JSON extraction (`json_key_map`)

`json_key_map` controls which values are extracted from the JSON response.

* Keys are the names stored in the API extracted value map.
* Values are dot-separated JSON paths:

  * `a.b.c` traverses nested dict keys
  * numeric segments (e.g., `0`) index lists when the current node is a list

Examples:

* `user.name`
* `items.0.id`

If a path does not exist, extraction returns `null` (no exception).

### 3.3 Timeout and retries (API)

The API client behavior is:

* Timeout: **10 seconds**
* Max retries: **3**
* Retries happen on:

  * network exceptions (`RequestException`)
  * HTTP **5xx** responses
* No retries on HTTP **4xx**
* No exponential backoff (retries are immediate)

---

## 4. HTML configuration

### 4.1 HtmlConfig schema

```yml
html:
  enabled: true
  url: "https://example.com/items/{external_id}"
  selectors:
    title: "h1"
    price: ".price"
    image_url: "img::attr(src)"
```

### 4.2 Selector behavior

* Selectors are evaluated using BeautifulSoup CSS selectors (`soup.select(...)`).
* Only the **first matched element** is used.
* If nothing matches, the extracted value is `null`.
* Text extraction uses `get_text(strip=True)`.

### 4.3 Supported selector extension: `::attr(name)`

The scraper supports one selector extension:

* `::attr(name)` extracts an attribute from the first matched element.

Example:

* `img::attr(src)` extracts the `src` attribute.

Important:

* `::text` is **not supported**. Use plain selectors for text (e.g., `h1`).

### 4.4 Timeout and retries (HTML)

The HTML fetcher behavior is:

* Timeout: **10 seconds**
* Max retries: **3**
* Retries happen on:

  * network exceptions (`RequestException`)
  * HTTP **5xx** responses
* No retries on HTTP **4xx**
* No exponential backoff

---

## 5. Mapping and normalization

### 5.1 MappingConfig schema

```yml
mapping:
  unified_fields:
    id: "api.post_id"
    title: "html.title"
    price: "html.price"
  field_types:
    price: "float"
```

### 5.2 Mapping expressions (required format)

Each value in `unified_fields` must reference exactly one source namespace:

* `api.<key>` uses values extracted from the API response
* `html.<key>` uses values extracted from HTML selectors

Examples:

* `api.sku`
* `html.title`

If the mapping expression is malformed or the referenced key is missing, the unified value becomes `null`.

### 5.3 Type casting (`field_types`)

Supported type casts:

* `int`
* `float`

Rules:

* Conversion failures produce `null`.
* Fields not listed in `field_types` remain as-is (typically strings).

---

## 6. URL templating via context

Both `api.base_url` and `html.url` support Python string formatting:

* `"{external_id}"` style placeholders are resolved using a runtime context dict.

### 6.1 Default CLI context

The CLI supplies the following context:

* `external_id = source.id`

So `{external_id}` is always available in CLI runs.

Example:

```yml
html:
  url: "https://example.com/products/{external_id}"
```

### 6.2 Missing placeholders

If a URL includes a placeholder not present in the context:

* API raises `ApiError` (missing context key)
* HTML raises `ScrapeError` (missing context key)

---

## 7. Validation and failure modes

### 7.1 Load-time config validation errors

These fail when the config is loaded:

* Missing `id`
* Missing `mapping` or missing `mapping.unified_fields`
* `mapping.unified_fields` is not a mapping/dict
* Both `api` and `html` are absent
* `api.enabled: true` but `api.base_url` missing
* `html.enabled: true` but `html.url` missing

### 7.2 Runtime failures (collection-time)

Typical runtime errors include:

* Missing URL placeholder (typo or missing context key)
* API returns 4xx (fails without retries)
* HTML returns 4xx (fails without retries)
* Selector matches nothing (value becomes `null`)
* Type casting fails (value becomes `null`)

### 7.3 Record validation in CLI runs (important)

The current CLI validation treats **all keys in `mapping.unified_fields` as required**.
If any unified field value is `null` or empty, the record is flagged as invalid.

If you need optional fields:

* Either exclude them from `unified_fields`, or
* Extend the validation logic to support optional fields explicitly.

---

## 8. Complete examples

### 8.1 API-only source

```yml
- id: jsonplaceholder-post-1
  api:
    enabled: true
    base_url: "https://jsonplaceholder.typicode.com/posts/1"
    json_key_map:
      post_id: "id"
      title: "title"
      user_id: "userId"
  mapping:
    unified_fields:
      id: "api.post_id"
      title: "api.title"
      user_id: "api.user_id"
    field_types:
      user_id: "int"
```

### 8.2 HTML-only source

```yml
- id: example-product
  html:
    enabled: true
    url: "https://example.com/products/{external_id}"
    selectors:
      title: "h1"
      price: ".price"
      image_url: "img::attr(src)"
  mapping:
    unified_fields:
      title: "html.title"
      price: "html.price"
      image_url: "html.image_url"
    field_types:
      price: "float"
```

### 8.3 Hybrid (API + HTML) source

```yml
- id: hybrid-1
  api:
    enabled: true
    base_url: "https://api.example.com/items/{external_id}"
    headers:
      Authorization: "Bearer ${API_TOKEN}"
    json_key_map:
      sku: "sku"
      stock: "inventory.stock"
  html:
    enabled: true
    url: "https://shop.example.com/items/{external_id}"
    selectors:
      title: "h1"
      price: ".price"
  mapping:
    unified_fields:
      sku: "api.sku"
      stock: "api.stock"
      title: "html.title"
      price: "html.price"
    field_types:
      stock: "int"
      price: "float"
```

---

## 9. Practical guidance

### 9.1 Start from the example config

Use `config/sources.example.yml` as your baseline. Add or modify one source at a time to keep changes reviewable and testable.

### 9.2 Keep unified fields intentional

Because CLI validation treats unified fields as required, avoid adding fields that may legitimately be missing for some sources unless you also adjust validation.

### 9.3 Prefer stable selectors and explicit attributes

* Use stable CSS selectors (avoid brittle DOM paths)
* Use `::attr(...)` for URLs and images
* Avoid unsupported selector pseudo-syntax

### 9.4 Secrets handling

* Use `${VAR}` placeholders in YAML
* Set secrets via environment variables in your runtime environment
* Never commit real tokens or credentials

---

## Related documentation

* `README.md` — overview and quickstart
* `docs/architecture.md` — modules and data flow
* `docs/operations.md` — operational practices and hardening ideas
* `docs/testing.md` — offline testing approach and CI checks
* `docs/SECURITY_AND_LEGAL.md` — responsible scraping guidance
# Hybrid-API-Scraping-Collector-Template
This document outlines the purpose, features, and usage of the hybrid API and HTML data collection template.

## Table of contents
This section lists navigation links for quick reference.

- [Overview](#overview)
- [Use cases](#use-cases)
- [Features](#features)
- [Architecture overview](#architecture-overview)
- [Project structure](#project-structure)
- [Quickstart](#quickstart)
- [Configuration](#configuration)
- [CLI usage](#cli-usage)
- [Testing](#testing)
- [Safety & legal](#safety--legal)
- [Related templates](#related-templates)
- [License](#license)

## Overview
This section explains why the template exists and what problems it solves.

Many real-world data projects need to combine multiple sources:

- Public or private **REST APIs** that return structured JSON.
- **HTML pages** that expose additional fields not available via API.
- A **unified dataset** that downstream tools (Excel, BI dashboards, ML pipelines) can easily consume.

This template provides a clean, reusable structure for:

1. Describing data sources in a **single YAML configuration file**.
2. Collecting data from both **API endpoints** and **HTML pages**.
3. **Normalizing** heterogeneous fields into a common schema.
4. **Validating** records for missing or inconsistent fields.
5. Exporting to **CSV/JSON/Excel** for analysis or delivery to clients.

The goal is not to be a full-blown ETL framework, but a **lightweight, production-style template** that you can adapt to many projects with minimal changes.

## Use cases
This section lists situations where the template is a good fit.

- Enriching product data: API provides IDs/prices while HTML pages contain titles, images, or category labels.
- Monitoring content across multiple sources: API for core metadata + HTML for SEO fields or UI-only flags.
- Internal tools that need to pull from partner APIs and public websites into a single master dataset.
- Proof-of-concept ETL jobs where you want to demonstrate **good engineering practices** (tests, configs, docs) without introducing heavy frameworks.

If you need **time-series monitoring and alerts**, see the companion [Rate-Monitor-Template](https://github.com/ryuhei-py/Rate-Monitor-Template) instead.

## Features
This section summarizes the key capabilities of the template.

- **Hybrid data collection**
  - REST API client with JSON path extraction.
  - HTML scraper powered by CSS selectors.

- **Config-driven behavior**
  - All sources and field mappings are defined in `config/sources.yml`.
  - No hard-coded URLs or selectors inside the business logic.

- **Normalization layer**
  - Maps `api.*` and `html.*` fields into a unified record schema.
  - Optional type casting (e.g. `float`, `int`) per field.

- **Validation**
  - Simple pluggable checks to ensure required fields are present.
  - Produces a list of validation issues for quick debugging and QA.

- **Exporters**
  - CSV output (UTF-8) ready for Excel or Google Sheets.
  - JSON output for programmatic consumption.
  - Optional Excel export via `pandas`.

- **Tests and CI-ready layout**
  - `pytest` test suite per module (config, API client, scraper, normalizer, exporter, validator, CLI).
  - `src/` layout suitable for packaging and reuse.

## Architecture overview
This section describes how data flows through the system components.

At a high level, the collector runs the following pipeline:

1. **Configuration**  
   `config/sources.yml` describes each data source: API endpoint details, HTML URL and CSS selectors, and mapping rules to unified fields.
2. **API Client (`api_client.py`)**  
   Executes HTTP requests with retries, extracts values from JSON using dot-separated paths, and returns a flat `dict` of API-level fields.
3. **HTML Scraper (`scraper.py`)**  
   Fetches HTML pages with retry logic, parses content with BeautifulSoup, and extracts text or attributes using CSS selectors.
4. **Normalizer (`normalizer.py`)**  
   Merges `api_values` and `html_values` into a single record and applies field mapping with optional type casting.
5. **Validator (`validator.py`)**  
   Runs lightweight checks (e.g. required fields not empty) and outputs a list of issues for logging or debugging.
6. **Exporter (`exporter.py`)**  
   Writes the final list of records to CSV/JSON/Excel.
7. **CLI (`cli.py`)**  
   Orchestrates the entire pipeline and accepts command-line options for config path, output directory, and dry-run mode.

## Project structure
This section shows the layout of files to help you navigate the repository.

```text
Hybrid-API-Scraping-Collector-Template/
├─ src/
│  └─ hybrid_collector/
│     ├─ __init__.py
│     ├─ config.py          # YAML config loading + dataclasses
│     ├─ api_client.py      # API requests + JSON extraction
│     ├─ scraper.py         # HTML fetching + parsing
│     ├─ normalizer.py      # Merge API/HTML into unified records
│     ├─ exporter.py        # CSV/JSON(/Excel) export
│     ├─ validator.py       # Basic record validation
│     ├─ cli.py             # Command-line orchestrator
│     └─ scheduler_stub.py  # Scheduling examples (cron, Task Scheduler)
│
├─ config/
│  └─ sources.example.yml   # Example configuration for sources
│
├─ docs/
│  ├─ architecture.md
│  ├─ operations.md
│  ├─ testing.md
│  ├─ CONFIG_GUIDE.md
│  └─ SECURITY_AND_LEGAL.md
│
├─ sample_output/
│  └─ unified_records.sample.csv
│
├─ tests/
│  ├─ conftest.py
│  ├─ test_config.py
│  ├─ test_api_client.py
│  ├─ test_scraper.py
│  ├─ test_normalizer.py
│  ├─ test_exporter.py
│  └─ test_validator.py
│
├─ .github/
│  └─ workflows/
│     └─ ci.yml
│
├─ .env.example
├─ .gitignore
├─ LICENSE
├─ pyproject.toml
├─ README.md
└─ requirements.txt
```
Some files may start as minimal stubs and evolve as you adapt the template to a specific project.

## Quickstart
This section explains how to set up and run the project.

### Requirements
Python 3.11+

git

A virtual environment tool (venv, conda, etc.)

### 1. Clone and set up the environment
Run the following commands to clone the repository and create a virtual environment.

```bash
git clone https://github.com/ryuhei-py/Hybrid-API-Scraping-Collector-Template.git
cd Hybrid-API-Scraping-Collector-Template

python -m venv .venv
source .venv/bin/activate        # Windows: .venv/Scripts/activate

pip install -r requirements.txt
```

### 2. Create your configuration file
Copy the example configuration to create your working config.

```bash
cp config/sources.example.yml config/sources.yml
```
Edit config/sources.yml to define your own API endpoints, HTML pages, and field mappings. See docs/CONFIG_GUIDE.md for details.

### 3. Run the collector (dry-run)
Execute the CLI in dry-run mode to validate configuration without writing files.

```bash
python -m hybrid_collector.cli \
  --config config/sources.yml \
  --output-dir sample_output \
  --dry-run
```
Dry-run mode will execute the pipeline but skip writing output files, which is useful while iterating on config.

### 4. Run the collector (with output)
Run the CLI normally to generate output files.

```bash
python -m hybrid_collector.cli \
  --config config/sources.yml \
  --output-dir sample_output
```
By default, the CLI writes:

sample_output/unified_records.csv

sample_output/unified_records.json

(Exact filenames may vary depending on your implementation.)

## Configuration
This section outlines how configuration is organized.

All behavior is driven by `config/sources.yml`.

Each entry in sources typically contains:

id: logical identifier for the source.

api: API configuration

base_url, method, params, headers

json_key_map: JSON paths → field names.

html: HTML configuration

url: page URL template

selectors: CSS selectors per field (supports ::attr(name)).

mapping:

unified_fields: unified field name → "api.<key>" or "html.<key>".

field_types: optional type hints ("float", "int", etc.).

A full, field-by-field explanation is provided in docs/CONFIG_GUIDE.md.

## CLI usage
This section shows how to run the CLI with common options.

Basic usage:

```bash
python -m hybrid_collector.cli \
  --config config/sources.yml \
  --output-dir sample_output \
  [--dry-run]
```
Options:

--config: Path to the YAML configuration file. Default: `config/sources.yml`.

--output-dir: Directory where output files are written. Default: `sample_output`.

--dry-run: If set, runs the pipeline but skips writing files.

You can integrate this command with cron, Windows Task Scheduler, or any other scheduler. See `docs/operations.md` for examples.

## Testing
This section describes how to run tests for this template.

Run all tests:

```bash
pytest
```
Typical test modules:

test_config.py: config loading and validation.

test_api_client.py: request logic, retries, JSON extraction.

test_scraper.py: HTML parsing and selector behavior.

test_normalizer.py: merging of API/HTML data and type casting.

test_exporter.py: CSV/JSON output shape.

test_validator.py: validation rules.

For more details, see `docs/testing.md`.

## Safety & legal
This section highlights legal and ethical considerations.

Hybrid data collection can involve legal and ethical constraints:

APIs: respect the provider’s terms of service, authentication requirements, and rate limits.

HTML scraping: review robots.txt, site policies, and local regulations before scraping.

Personal data: avoid collecting or storing sensitive personal information unless strictly necessary and always follow applicable privacy laws.

This repository is provided as a technical template only. See `docs/SECURITY_AND_LEGAL.md` for more guidance on safe use.

## Related templates
This section lists companion repositories that complement this template.

Product-List-Scraper-Template
Generic product listing scraper with YAML-driven selectors and CSV/Excel output.

Rate-Monitor-Template
Production-style template for scheduled price/rate monitoring with SQLite time-series storage and optional Slack notifications.

Amazon Price Monitor Tool
Full production example that inspired these templates.

## License
This section states the licensing for the project.

This project is licensed under the MIT License.

# Operations
This document describes how to run, schedule, and operate the Hybrid-API-Scraping-Collector-Template in practical environments.

## Operational goals
This section outlines the operational intent of the template.

- **Easy to run locally** for quick experiments and client demos.
- **Config-driven**, so you can adapt behavior by editing YAML instead of code.
- **Schedulable**, so it can run unattended (e.g. once per day).
- **Safe to extend**, with clear places to add new sources, outputs, or validations.

The template does not prescribe heavy deployment models (Kubernetes, Airflow); it offers a clean Python CLI to plug into your environment.

## Environments and prerequisites
This section lists supported environments and system requirements.

### Typical environments
This subsection describes where the template is commonly run.

- **Local development**
  - You develop, configure, and test everything on your own machine.
  - Ideal for building Upwork portfolio projects or proofs of concept.
- **Single server / VM / container**
  - Optionally deploy the same project to a server or container.
  - Schedule the CLI via cron or another scheduler.
  - This is closer to a “production-style” setup.

The code itself is environment-agnostic; you switch environments via different config files and environment variables.

### System requirements
This subsection lists required tools.

- Python **3.11+**
- `git`
- A virtual environment tool (`venv` recommended)
- Network access to the APIs you call and the sites you scrape

## Configuration management
This section covers how to manage YAML configs and secrets.

### Config files
This subsection explains where configuration lives.

All sources are defined in:

```text
config/sources.yml
```

Recommended workflow:

Start from the example:

```bash
cp config/sources.example.yml config/sources.yml
```

Edit `config/sources.yml` to:

- Add or modify API endpoints.
- Add or modify HTML URLs and selectors.
- Define unified field mappings and types.

For multiple environments, you can introduce:

```text
config/sources.dev.yml
config/sources.staging.yml
config/sources.prod.yml
```

Pass the appropriate path via `--config` (see CLI section).

### Environment variables and .env
This subsection explains how to keep secrets out of version control.

Sensitive values (tokens, API keys, secrets) should not be hard-coded in `sources.yml`. Reference them with `${VAR_NAME}` and define them as environment variables.

Example in YAML:

```yaml
api:
  base_url: "https://api.example.com/products/{external_id}"
  headers:
    Authorization: "Bearer ${API_TOKEN}"
```

You can then set them via `.env`:

```text
# .env (never commit this file)
API_TOKEN=your-real-token-here
```

Typical workflow:

```bash
cp .env.example .env
```

Edit `.env` to add your real keys, then load environment variables before running the CLI (for example, with `python-dotenv` or by exporting them in your shell).

Operational rule of thumb: config files define structure and non-sensitive defaults; `.env` and environment variables hold secrets.

## Local development and one-off runs
This section explains how to set up and execute the CLI locally.

### Setup (once per machine)
Run these commands to clone and set up the environment.

```bash
git clone https://github.com/ryuhei-py/Hybrid-API-Scraping-Collector-Template.git
cd Hybrid-API-Scraping-Collector-Template

python -m venv .venv
# Windows: .venv/Scripts/activate
# macOS / Linux: source .venv/bin/activate

pip install -r requirements.txt
```

Then copy baseline configs:

```bash
cp config/sources.example.yml config/sources.yml
cp .env.example .env
```

Adjust `config/sources.yml` and `.env` to your needs.

### Dry-run (no file output)
Run the pipeline without writing files to validate configs.

```bash
python -m hybrid_collector.cli \
  --config config/sources.yml \
  --output-dir sample_output \
  --dry-run
```

Behavior:

- Loads config.
- Calls APIs and HTML pages.
- Normalizes and validates records.
- Prints a summary to the console.
- Does not write CSV/JSON files.

Dry-run is ideal for verifying URLs, selectors, mappings, and validation output before writing files.

### Full run (with output)
Run the pipeline and write outputs.

```bash
python -m hybrid_collector.cli \
  --config config/sources.yml \
  --output-dir sample_output
```

Typical outputs:

- `sample_output/unified_records.csv`
- `sample_output/unified_records.json`

You can open the CSV in Excel or Google Sheets to inspect the unified schema.

## Directory conventions
This section lists important directories for operations.

Key directories during operation:

- `config/` — main configuration file `sources.yml`.
- `sample_output/` — default location for generated CSV/JSON. For production, point `--output-dir` elsewhere.
- `tests/` — unit tests; important for safe changes.
- `src/hybrid_collector/` — implementation modules; in operations, you typically call only the CLI.

A common production pattern:

- Keep the repo under a path like `/opt/hybrid-collector` or `C:/apps/hybrid-collector`.
- Use a dedicated virtual environment in that directory.
- Use a dedicated output directory (`/data/hybrid-collector-output` or similar) instead of `sample_output`.

## Scheduling the collector
This section shows how to run the CLI on a schedule.

You can schedule the CLI with any external scheduler. The pseudo-documentation in `src/hybrid_collector/scheduler_stub.py` mirrors this section.

### Cron (Linux / macOS)
This subsection provides a cron example.

Assuming:

- Repo at `/opt/hybrid-collector`
- Virtualenv at `/opt/hybrid-collector/.venv`
- Config at `/opt/hybrid-collector/config/sources.yml`
- Output at `/data/hybrid-collector-output`

Example cron entry to run every day at 02:00:

```bash
0 2 * * * cd /opt/hybrid-collector && \
  . .venv/bin/activate && \
  python -m hybrid_collector.cli \
    --config config/sources.yml \
    --output-dir /data/hybrid-collector-output \
  >> /var/log/hybrid-collector.log 2>&1
```

Notes:

- `cd` into the project directory before running.
- Activate the virtual environment.
- Redirect stdout/stderr to a log file for later inspection.

### Windows Task Scheduler
This subsection shows a Task Scheduler example.

On Windows:

- Open Task Scheduler.
- Create a Basic Task.
- Configure a trigger (e.g. daily at 02:00).
- Set the action to run `powershell.exe` with arguments similar to:

```powershell
# Example action (Program/script)
C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe

# Example arguments
-NoProfile -ExecutionPolicy Bypass -Command "
  cd 'C:/apps/Hybrid-API-Scraping-Collector-Template';
  & '.\.venv\Scripts\Activate.ps1';
  python -m hybrid_collector.cli `
    --config config/sources.yml `
    --output-dir 'C:/data/hybrid-collector-output'
"
```

Ensure the account running the task has:

- Access to the project directory.
- Permission to write to the output directory.
- Network access to APIs/sites.

## Logs, validation, and monitoring
This section covers operational checks and logging practices.

### Logging and outputs
This subsection explains typical logging behavior.

By default, the CLI:

- Prints a summary of processing to stdout (and stderr on errors).
- Writes CSV/JSON to the configured output directory (when not in `--dry-run`).

Recommended practices:

- Redirect CLI output to a log file in scheduled runs.
- Keep at least: start/end timestamps, number of sources processed, number of records generated, and validation issue counts.

### Validation issues
This subsection explains how to handle validation findings.

The `validator.py` module returns issues for each record that fails basic checks. Operationally, you should:

- Log validation issues clearly (record index, field, message).
- Periodically review them to detect broken selectors, API contract changes, or upstream data quality problems.

### Simple health checks
This subsection lists quick checks for scheduled runs.

In a production-style setup, you might:

- Verify that the CSV file was written and is non-empty.
- Check that the number of records is within an expected range.
- Raise an alert (email/Slack) if no records are produced or validation issues spike suddenly.

## Change management workflow
This section describes a safe workflow for making changes.

When making changes (new sources, new mappings, new logic), a safe workflow is:

1. Update configuration
   - Edit `config/sources.yml`.
   - If introducing new secrets, update `.env` (and never commit it).
2. Run tests

    ```bash
    pytest
    ```

3. Run a local dry-run

    ```bash
    python -m hybrid_collector.cli \
      --config config/sources.yml \
      --output-dir sample_output \
      --dry-run
    ```

4. Inspect logs and validation messages
   - Fix selectors, mappings, or types if necessary.
5. Run a full local run
   - Confirm that CSV/JSON output looks correct.
6. Deploy changes
   - Pull the updated code/config onto the server.
   - Restart or wait for the next scheduled run.

This mirrors typical operational practices in client projects and looks professional in code reviews.

## Troubleshooting
This section lists common issues and remediation steps.

### Configuration errors
This subsection covers problems with YAML or missing keys.

Symptoms:

- CLI exits immediately with a configuration error.
- Traceback mentions missing keys or invalid types.

Actions:

- Check `config/sources.yml` for typos.
- Compare against `config/sources.example.yml`.
- Ensure indentation is correct (YAML is sensitive to this).

### Network / API errors
This subsection covers HTTP or connectivity failures.

Symptoms:

- Timeouts, connection errors, or HTTP 4xx/5xx status codes.
- CLI logs repeated retries or early failure.

Actions:

- Verify API base URL and parameters.
- Check that your API keys are correctly set in `.env` and picked up by the process.
- Make sure you are not exceeding provider rate limits.
- Use `--dry-run` while debugging to avoid unnecessary data writes.

### HTML scraping failures
This subsection addresses selector or DOM issues.

Symptoms:

- Extracted values are `None` or empty for some fields.
- Validation issues show many missing HTML-based fields.

Actions:

- Inspect the target pages in a browser.
- Confirm that CSS selectors in `selectors` still match the DOM.
- Adjust selectors in `config/sources.yml`.
- Run a local dry-run to verify fixes.

### Output / file permission issues
This subsection covers file system problems.

Symptoms:

- CSV/JSON files are not created.
- Errors mentioning “permission denied” or missing directories.

Actions:

- Ensure the `--output-dir` exists or can be created by the process.
- On Windows, check folder permissions for the scheduled task user.
- On Linux, check directory ownership and permission bits.

## Production hardening ideas
This section lists optional enhancements for stricter environments.

The template intentionally stays minimal. For more demanding environments, you may consider:

- Integrating a structured logger (e.g. Python’s logging with JSON output).
- Adding alerting (email/Slack) for hard failures or abnormal validation counts.
- Storing records in a database in addition to CSV/JSON.
- Running in a container with a fixed Python/runtime image.
- Versioning config files and documenting change history.

These are out of scope for the template, but the code is structured to make such extensions straightforward.

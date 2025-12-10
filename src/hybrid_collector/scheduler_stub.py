"""
Document how to schedule the hybrid collector in production.

This module is intentionally simple and used only as documentation.
"""


def cron_example() -> str:
    return (
        "# Run the hybrid collector every day at 02:00\n"
        "0 2 * * * cd /path/to/Hybrid-API-Scraping-Collector-Template && "
        ".venv/bin/python -m hybrid_collector.cli --config config/sources.yml\n"
    )

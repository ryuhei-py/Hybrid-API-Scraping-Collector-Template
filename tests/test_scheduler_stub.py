from hybrid_collector.scheduler_stub import cron_example


def test_cron_example_contains_schedule():
    assert "0 2 * * *" in cron_example()

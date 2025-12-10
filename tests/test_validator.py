from hybrid_collector.validator import ValidationIssue, validate_records


def test_validate_records_missing_fields():
    records = [
        {"id": 1, "name": "Alice"},
        {"id": None, "name": ""},
        {"id": 3},
    ]
    required = ["id", "name"]

    issues = validate_records(records, required)

    assert len(issues) == 3
    assert issues[0] == ValidationIssue(index=1, field="id", message="Missing required value")
    assert issues[1] == ValidationIssue(index=1, field="name", message="Missing required value")
    assert issues[2] == ValidationIssue(index=2, field="name", message="Missing required value")

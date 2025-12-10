from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ValidationIssue:
    index: int
    field: str
    message: str


def validate_records(records: list[dict[str, Any]], required_fields: list[str]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for idx, record in enumerate(records):
        for field in required_fields:
            value = record.get(field)
            if value is None or value == "":
                issues.append(ValidationIssue(index=idx, field=field, message="Missing required value"))
    return issues

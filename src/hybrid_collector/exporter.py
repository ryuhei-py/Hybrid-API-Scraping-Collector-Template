from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import csv
import json

import pandas as pd


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def export_to_csv(records: list[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    _ensure_parent(path)

    # Union of all keys across records preserves insertion order by first appearance.
    fieldnames: list[str] = []
    for record in records:
        for key in record.keys():
            if key not in fieldnames:
                fieldnames.append(key)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def export_to_json(records: list[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    _ensure_parent(path)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


def export_to_excel(records: list[dict[str, Any]], path: str | Path) -> None:
    path = Path(path)
    _ensure_parent(path)
    df = pd.DataFrame(records)
    df.to_excel(path, index=False)

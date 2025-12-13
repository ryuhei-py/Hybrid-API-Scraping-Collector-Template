import csv
import json

from hybrid_collector.exporter import export_to_csv, export_to_json


def test_export_to_csv(tmp_path):
    records = [
        {"id": 1, "name": "Alice"},
        {"id": 2, "name": "Bob", "extra": "yes"},
    ]
    out_path = tmp_path / "out" / "data.csv"

    export_to_csv(records, out_path)

    assert out_path.exists()
    with out_path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    assert rows[0] == ["id", "name", "extra"]
    assert rows[1] == ["1", "Alice", ""]
    assert rows[2] == ["2", "Bob", "yes"]


def test_export_to_json(tmp_path):
    records = [{"id": 1, "name": "Alice"}]
    out_path = tmp_path / "out" / "data.json"

    export_to_json(records, out_path)

    assert out_path.exists()
    content = json.loads(out_path.read_text(encoding="utf-8"))
    assert content == records

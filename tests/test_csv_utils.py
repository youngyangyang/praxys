import os
import tempfile
import csv
import pytest
from sync.csv_utils import read_csv, append_rows, EMPTY_RESULT


def test_read_csv_nonexistent_returns_empty():
    result = read_csv("/nonexistent/path.csv")
    assert result == EMPTY_RESULT


def test_read_csv_reads_existing_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "value"])
        writer.writeheader()
        writer.writerow({"id": "1", "value": "a"})
        path = f.name
    try:
        result = read_csv(path)
        assert len(result) == 1
        assert result[0]["id"] == "1"
    finally:
        os.unlink(path)


def test_append_rows_creates_file_if_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.csv")
        rows = [{"id": "1", "value": "a"}, {"id": "2", "value": "b"}]
        append_rows(path, rows, key_column="id")
        result = read_csv(path)
        assert len(result) == 2


def test_append_rows_deduplicates_by_key():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.csv")
        rows1 = [{"id": "1", "value": "a"}, {"id": "2", "value": "b"}]
        append_rows(path, rows1, key_column="id")
        rows2 = [{"id": "2", "value": "b_updated"}, {"id": "3", "value": "c"}]
        append_rows(path, rows2, key_column="id")
        result = read_csv(path)
        assert len(result) == 3
        values_by_id = {r["id"]: r["value"] for r in result}
        assert values_by_id["2"] == "b_updated"  # newer wins


def test_append_rows_handles_empty_new_rows():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "test.csv")
        rows = [{"id": "1", "value": "a"}]
        append_rows(path, rows, key_column="id")
        append_rows(path, [], key_column="id")
        result = read_csv(path)
        assert len(result) == 1

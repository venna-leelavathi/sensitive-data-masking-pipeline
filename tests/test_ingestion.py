"""Tests for multi-format ingestion and streaming chunk reading."""

import json
import pytest
from pathlib import Path
from src.pipeline.ingestion import DataIngestor


def test_ingest_json_and_checksum(tmp_path: Path):
    file_p = tmp_path / "test.json"
    data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    with open(file_p, "w", encoding="utf-8") as f:
        json.dump(data, f)

    records = DataIngestor.load_records(file_p)
    assert len(records) == 2
    assert records[0]["name"] == "Alice"

    chk = DataIngestor.calculate_file_checksum(file_p)
    assert len(chk) == 64  # SHA-256 hex string


def test_ingest_jsonl_streaming_chunks(tmp_path: Path):
    file_p = tmp_path / "test.jsonl"
    with open(file_p, "w", encoding="utf-8") as f:
        for i in range(25):
            f.write(json.dumps({"idx": i, "value": f"item_{i}"}) + "\n")

    chunks = list(DataIngestor.stream_chunks(file_p, chunk_size=10))
    assert len(chunks) == 3
    assert len(chunks[0]) == 10
    assert len(chunks[1]) == 10
    assert len(chunks[2]) == 5


def test_ingest_csv(tmp_path: Path):
    file_p = tmp_path / "test.csv"
    file_p.write_text("id,val\n1,alpha\n2,\n", encoding="utf-8")

    records = DataIngestor.load_records(file_p)
    assert len(records) == 2
    assert records[0]["val"] == "alpha"
    assert records[1]["val"] is None  # Empty string converted to None


def test_ingest_empty_file(tmp_path: Path):
    file_p = tmp_path / "empty.json"
    file_p.write_text("", encoding="utf-8")
    records = DataIngestor.load_records(file_p)
    assert records == []


def test_ingest_malformed_json_raises_value_error(tmp_path: Path):
    file_p = tmp_path / "bad.json"
    file_p.write_text("{broken json", encoding="utf-8")
    with pytest.raises(ValueError, match="Malformed JSON file"):
        DataIngestor.load_records(file_p)


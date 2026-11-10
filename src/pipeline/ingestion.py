"""Multi-format data ingestion layer supporting JSON, JSON Lines, CSV, and Parquet."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Union
import pandas as pd


class DataIngestor:
    """Ingests data files safely with streaming and error resilience."""

    @staticmethod
    def calculate_file_checksum(file_path: Union[str, Path]) -> str:
        """Compute SHA-256 hash of a file for audit provenance."""
        path = Path(file_path)
        if not path.is_file():
            return "FILE_NOT_FOUND"
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def load_records(cls, file_path: Union[str, Path]) -> List[Dict[str, Any]]:
        """Load all records from a file into memory as list of dicts."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {file_path}")

        # Check for empty file
        if path.stat().st_size == 0:
            return []

        suffix = path.suffix.lower()

        if suffix == ".json":
            return cls._load_json(path)
        elif suffix == ".jsonl":
            return cls._load_jsonl(path)
        elif suffix == ".csv":
            return cls._load_csv(path)
        elif suffix in [".parquet", ".pq"]:
            return cls._load_parquet(path)
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    @classmethod
    def stream_chunks(
        cls, file_path: Union[str, Path], chunk_size: int = 10000
    ) -> Generator[List[Dict[str, Any]], None, None]:
        """Stream records in manageable chunks for scalable 100k+ datasets."""
        path = Path(file_path)
        if not path.exists() or path.stat().st_size == 0:
            return

        suffix = path.suffix.lower()
        if suffix == ".jsonl":
            chunk: List[Dict[str, Any]] = []
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        chunk.append(json.loads(line))
                    except json.JSONDecodeError:
                        chunk.append({"__malformed_raw_line__": line})
                    if len(chunk) >= chunk_size:
                        yield chunk
                        chunk = []
            if chunk:
                yield chunk
        elif suffix == ".csv":
            chunk = []
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    chunk.append(dict(row))
                    if len(chunk) >= chunk_size:
                        yield chunk
                        chunk = []
            if chunk:
                yield chunk
        else:
            # Fall back to loading all and chunking
            all_records = cls.load_records(file_path)
            for i in range(0, len(all_records), chunk_size):
                yield all_records[i : i + chunk_size]

    @staticmethod
    def _load_json(path: Path) -> List[Dict[str, Any]]:
        with open(path, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict):
                    return [data]
                else:
                    return []
            except json.JSONDecodeError as e:
                # Malformed JSON file
                raise ValueError(f"Malformed JSON file '{path.name}': {e}")

    @staticmethod
    def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
        records = []
        with open(path, "r", encoding="utf-8") as f:
            for idx, line in enumerate(f, start=1):
                clean = line.strip()
                if not clean:
                    continue
                try:
                    records.append(json.loads(clean))
                except json.JSONDecodeError:
                    records.append({"__malformed_raw_line__": clean, "__line_number__": idx})
        return records

    @staticmethod
    def _load_csv(path: Path) -> List[Dict[str, Any]]:
        records = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Convert empty strings to None
                cleaned = {k: (v if v != "" else None) for k, v in row.items()}
                records.append(cleaned)
        return records

    @staticmethod
    def _load_parquet(path: Path) -> List[Dict[str, Any]]:
        df = pd.read_parquet(path)
        return df.to_dict(orient="records")


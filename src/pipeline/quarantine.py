"""Explicit quarantine storage and rejection management."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd


@dataclass
class QuarantineRecord:
    quarantine_id: str
    run_id: str
    entity_name: str
    source_file: str
    record_id: str
    error_code: str
    error_message: str
    source_record_raw: str  # JSON-serialized original payload
    rejected_at: str


class QuarantineManager:
    """Collects, persists, and reports quarantined records."""

    def __init__(self, run_id: str):
        self.run_id = run_id
        self.records: List[QuarantineRecord] = []

    def add(
        self,
        entity_name: str,
        source_file: str,
        raw_record: Dict[str, Any],
        error_code: str,
        error_message: str,
        record_id: Optional[str] = None,
    ) -> QuarantineRecord:
        """Quarantine a single record with traceable context."""
        rec_id = str(record_id) if record_id else str(raw_record.get("customer_id") or raw_record.get("transaction_id") or "UNKNOWN")
        qr = QuarantineRecord(
            quarantine_id=f"quar_{uuid.uuid4().hex[:12]}",
            run_id=self.run_id,
            entity_name=entity_name,
            source_file=source_file,
            record_id=rec_id,
            error_code=error_code,
            error_message=error_message,
            source_record_raw=json.dumps(raw_record, default=str),
            rejected_at=datetime.now(timezone.utc).isoformat(),
        )
        self.records.append(qr)
        return qr

    @property
    def count(self) -> int:
        return len(self.records)

    def get_summary(self) -> Dict[str, Any]:
        """Generate breakdown by entity and error code."""
        breakdown_by_error: Dict[str, int] = {}
        breakdown_by_entity: Dict[str, int] = {}
        for r in self.records:
            breakdown_by_error[r.error_code] = breakdown_by_error.get(r.error_code, 0) + 1
            breakdown_by_entity[r.entity_name] = breakdown_by_entity.get(r.entity_name, 0) + 1

        return {
            "total_quarantined": len(self.records),
            "by_error_code": breakdown_by_error,
            "by_entity": breakdown_by_entity,
        }

    def persist(self, quarantine_dir: str | Path) -> Dict[str, Path]:
        """Save quarantined records to JSON Lines and Parquet for auditability."""
        qdir = Path(quarantine_dir)
        qdir.mkdir(parents=True, exist_ok=True)

        if not self.records:
            return {}

        data = [asdict(r) for r in self.records]
        df = pd.DataFrame(data)

        jsonl_path = qdir / f"quarantine_{self.run_id}.jsonl"
        parquet_path = qdir / f"quarantine_{self.run_id}.parquet"

        # Write JSON Lines
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for item in data:
                f.write(json.dumps(item) + "\n")

        # Write Parquet
        df.to_parquet(parquet_path, index=False)

        return {"jsonl": jsonl_path, "parquet": parquet_path}

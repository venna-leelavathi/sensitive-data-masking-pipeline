"""Operational metrics, run ledgers, and audit trail management."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AuditRecord:
    run_id: str
    pipeline_name: str
    pipeline_version: str
    start_time: str
    end_time: str
    duration_seconds: float
    status: str  # SUCCESS, PARTIAL_SUCCESS, FAILED
    total_input_records: int
    total_valid_records: int
    total_quarantined_records: int
    total_published_records: int
    entity_counts: Dict[str, Dict[str, int]]
    quarantine_breakdown: Dict[str, int]
    masking_manifest: Dict[str, Dict[str, str]]
    source_checksums: Dict[str, str]
    target_checksums: Dict[str, str]
    reconciliation_status: str
    failure_reason: Optional[str] = None


class AuditLedger:
    """Manages immutable audit trail and operational run logs."""

    def __init__(self, audit_dir: str | Path, sqlite_db_path: Optional[str | Path] = None):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_db_path = Path(sqlite_db_path) if sqlite_db_path else None
        self.ledger_file = self.audit_dir / "audit_ledger.jsonl"

    def record_run(self, record: AuditRecord) -> Path:
        """Append run summary to the immutable audit ledger and save per-run detail."""
        run_dict = asdict(record)

        # 1. Append to JSON Lines ledger
        with open(self.ledger_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(run_dict) + "\n")

        # 2. Save individual run report
        runs_dir = self.audit_dir / "runs"
        runs_dir.mkdir(exist_ok=True)
        run_file = runs_dir / f"run_{record.run_id}.json"
        with open(run_file, "w", encoding="utf-8") as f:
            json.dump(run_dict, f, indent=2)

        # 3. Log to SQLite if enabled
        if self.sqlite_db_path and self.sqlite_db_path.parent.exists():
            self._record_to_sqlite(record)

        return run_file

    def _record_to_sqlite(self, record: AuditRecord) -> None:
        try:
            conn = sqlite3.connect(self.sqlite_db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pipeline_audit_runs (
                    run_id TEXT PRIMARY KEY,
                    pipeline_name TEXT,
                    pipeline_version TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    duration_seconds REAL,
                    status TEXT,
                    total_input_records INTEGER,
                    total_valid_records INTEGER,
                    total_quarantined_records INTEGER,
                    total_published_records INTEGER,
                    reconciliation_status TEXT,
                    failure_reason TEXT
                )
            """)
            conn.execute("""
                INSERT OR REPLACE INTO pipeline_audit_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.run_id,
                record.pipeline_name,
                record.pipeline_version,
                record.start_time,
                record.end_time,
                record.duration_seconds,
                record.status,
                record.total_input_records,
                record.total_valid_records,
                record.total_quarantined_records,
                record.total_published_records,
                record.reconciliation_status,
                record.failure_reason,
            ))
            conn.commit()
            conn.close()
        except Exception:
            pass

"""End-to-end pipeline execution orchestrator."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pandas as pd

from src.config import AppConfig, MaskingConfig, load_app_config, load_masking_config
from src.masking.engine import MaskingEngine
from src.pipeline.audit import AuditLedger, AuditRecord
from src.pipeline.ingestion import DataIngestor
from src.pipeline.publisher import TargetPublisher
from src.pipeline.quarantine import QuarantineManager
from src.pipeline.validator import DataValidator
from src.reconciliation.reconciler import DataReconciler, ReconciliationResult


class PipelineRunner:
    """Orchestrates end-to-end ingestion, validation, masking, and publishing."""

    def __init__(
        self,
        app_config: Optional[AppConfig] = None,
        masking_config: Optional[MaskingConfig] = None,
        config_path: str | Path = "config/pipeline_config.yaml",
        masking_path: str | Path = "config/masking_rules.yaml",
    ):
        self.app_config = app_config or load_app_config(config_path)
        self.masking_config = masking_config or load_masking_config(masking_path)

    def run(
        self,
        customers_input: Optional[Union[str, Path, List[Dict[str, Any]]]] = None,
        transactions_input: Optional[Union[str, Path, List[Dict[str, Any]]]] = None,
        run_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute pipeline on input data."""
        start_ts = datetime.now(timezone.utc)
        start_clock = time.perf_counter()
        
        assigned_run_id = run_id or f"run_{start_ts.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        quarantine_mgr = QuarantineManager(run_id=assigned_run_id)
        validator = DataValidator(
            quarantine_mgr=quarantine_mgr,
            strict_schema=self.app_config.validation.strict_schema,
            deduplicate_by_key=self.app_config.validation.deduplicate_by_key,
            dedup_strategy=self.app_config.validation.dedup_strategy,
        )
        masking_engine = MaskingEngine(
            masking_config=self.masking_config,
            secret_salt=self.app_config.pipeline.secret_salt,
        )
        publisher = TargetPublisher(
            output_dir=self.app_config.storage.output_dir,
            sqlite_db_path=self.app_config.storage.sqlite_db_path,
        )
        audit_ledger = AuditLedger(
            audit_dir=self.app_config.storage.audit_dir,
            sqlite_db_path=self.app_config.storage.sqlite_db_path,
        )

        source_checksums: Dict[str, str] = {}
        target_checksums: Dict[str, str] = {}

        try:
            # 1. Ingest Customers
            raw_customers, cust_source_name = self._resolve_input(
                customers_input, default_file="customers.json"
            )
            if isinstance(customers_input, (str, Path)):
                source_checksums["customers"] = DataIngestor.calculate_file_checksum(customers_input)

            # 2. Ingest Transactions
            raw_transactions, tx_source_name = self._resolve_input(
                transactions_input, default_file="transactions.json"
            )
            if isinstance(transactions_input, (str, Path)):
                source_checksums["transactions"] = DataIngestor.calculate_file_checksum(transactions_input)

            # 3. Validate Customers
            valid_customers, cust_val_summary = validator.validate_customers(
                raw_records=raw_customers, source_file=cust_source_name
            )
            valid_customer_ids = {r["customer_id"] for r in valid_customers}

            # 4. Validate Transactions (including Foreign Key Referential Integrity)
            valid_transactions, tx_val_summary = validator.validate_transactions(
                raw_records=raw_transactions,
                valid_customer_ids=valid_customer_ids,
                source_file=tx_source_name,
                enforce_referential_integrity=self.app_config.validation.enforce_referential_integrity,
            )

            # 5. Transform Customers (Masking & Minimization)
            cust_df_raw = pd.DataFrame(valid_customers)
            masked_customers_df, cust_manifest = masking_engine.transform_dataframe(
                cust_df_raw, entity_name="customers", run_id=assigned_run_id
            )

            # 6. Transform Transactions (Masking & Minimization)
            tx_df_raw = pd.DataFrame(valid_transactions)
            masked_transactions_df, tx_manifest = masking_engine.transform_dataframe(
                tx_df_raw, entity_name="transactions", run_id=assigned_run_id
            )

            # 7. Publish Targets Idempotently
            cust_pub_res = publisher.publish_customers(
                masked_customers_df, publish_format=self.app_config.storage.publish_format
            )
            tx_pub_res = publisher.publish_transactions(
                masked_transactions_df, publish_format=self.app_config.storage.publish_format
            )

            if "parquet_checksum" in cust_pub_res:
                target_checksums["customers_parquet"] = cust_pub_res["parquet_checksum"]
            if "parquet_checksum" in tx_pub_res:
                target_checksums["transactions_parquet"] = tx_pub_res["parquet_checksum"]

            # 8. Persist Quarantine Records
            quar_artifacts = quarantine_mgr.persist(self.app_config.storage.quarantine_dir)

            # 9. Reconcile
            reconciliation = DataReconciler.reconcile(
                raw_customers=raw_customers,
                raw_transactions=raw_transactions,
                published_customers_df=masked_customers_df,
                published_transactions_df=masked_transactions_df,
                quarantined_records=quarantine_mgr.records,
                valid_customers_count=len(valid_customers),
                valid_transactions_count=len(valid_transactions),
            )

            # 10. Audit Log & Status
            duration = round(time.perf_counter() - start_clock, 4)
            end_ts = datetime.now(timezone.utc)
            status = "SUCCESS" if quarantine_mgr.count == 0 else "PARTIAL_SUCCESS"

            audit_rec = AuditRecord(
                run_id=assigned_run_id,
                pipeline_name=self.app_config.pipeline.name,
                pipeline_version=self.app_config.pipeline.version,
                start_time=start_ts.isoformat(),
                end_time=end_ts.isoformat(),
                duration_seconds=duration,
                status=status,
                total_input_records=len(raw_customers) + len(raw_transactions),
                total_valid_records=len(valid_customers) + len(valid_transactions),
                total_quarantined_records=quarantine_mgr.count,
                total_published_records=len(masked_customers_df) + len(masked_transactions_df),
                entity_counts={
                    "customers": {
                        "input": len(raw_customers),
                        "valid": len(valid_customers),
                        "quarantined": cust_val_summary.quarantined_count,
                        "deduplicated": cust_val_summary.deduplicated_count,
                        "published": len(masked_customers_df),
                    },
                    "transactions": {
                        "input": len(raw_transactions),
                        "valid": len(valid_transactions),
                        "quarantined": tx_val_summary.quarantined_count,
                        "deduplicated": tx_val_summary.deduplicated_count,
                        "published": len(masked_transactions_df),
                    },
                },
                quarantine_breakdown=quarantine_mgr.get_summary()["by_error_code"],
                masking_manifest={"customers": cust_manifest, "transactions": tx_manifest},
                source_checksums=source_checksums,
                target_checksums=target_checksums,
                reconciliation_status="PASSED" if reconciliation.all_passed else "FAILED",
                failure_reason=None,
            )

            audit_file = audit_ledger.record_run(audit_rec)

            return {
                "run_id": assigned_run_id,
                "status": status,
                "duration_seconds": duration,
                "input_total": len(raw_customers) + len(raw_transactions),
                "valid_total": len(valid_customers) + len(valid_transactions),
                "quarantined_total": quarantine_mgr.count,
                "published_total": len(masked_customers_df) + len(masked_transactions_df),
                "reconciliation": reconciliation,
                "audit_file": str(audit_file),
                "published_customers_count": len(masked_customers_df),
                "published_transactions_count": len(masked_transactions_df),
            }

        except Exception as e:
            duration = round(time.perf_counter() - start_clock, 4)
            end_ts = datetime.now(timezone.utc)
            failed_audit = AuditRecord(
                run_id=assigned_run_id,
                pipeline_name=self.app_config.pipeline.name,
                pipeline_version=self.app_config.pipeline.version,
                start_time=start_ts.isoformat(),
                end_time=end_ts.isoformat(),
                duration_seconds=duration,
                status="FAILED",
                total_input_records=0,
                total_valid_records=0,
                total_quarantined_records=quarantine_mgr.count,
                total_published_records=0,
                entity_counts={},
                quarantine_breakdown=quarantine_mgr.get_summary()["by_error_code"],
                masking_manifest={},
                source_checksums=source_checksums,
                target_checksums={},
                reconciliation_status="FAILED",
                failure_reason=str(e),
            )
            audit_ledger.record_run(failed_audit)
            raise e

    def _resolve_input(
        self, input_val: Optional[Union[str, Path, List[Dict[str, Any]]]], default_file: str
    ) -> Tuple[List[Dict[str, Any]], str]:
        if input_val is None:
            default_path = self.app_config.storage.input_dir / default_file
            if default_path.exists():
                return DataIngestor.load_records(default_path), str(default_path.name)
            return [], default_file
        elif isinstance(input_val, (str, Path)):
            path = Path(input_val)
            if not path.exists():
                return [], str(path.name)
            return DataIngestor.load_records(path), str(path.name)
        elif isinstance(input_val, list):
            return input_val, "in_memory_records"
        else:
            return [], "unknown_input"

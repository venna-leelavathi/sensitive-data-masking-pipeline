"""Data validation engine handling schema, business rules, duplicates, and referential integrity."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import ValidationError

from src.pipeline.schema import CustomerInputSchema, TransactionInputSchema
from src.pipeline.quarantine import QuarantineManager


@dataclass
class ValidationSummary:
    entity_name: str
    total_input: int = 0
    valid_count: int = 0
    quarantined_count: int = 0
    deduplicated_count: int = 0
    error_counts: Dict[str, int] = field(default_factory=dict)


class DataValidator:
    """Validates records against schema, business rules, uniqueness, and referential integrity."""

    def __init__(
        self,
        quarantine_mgr: QuarantineManager,
        strict_schema: bool = True,
        deduplicate_by_key: bool = True,
        dedup_strategy: str = "latest_timestamp",
    ):
        self.quarantine_mgr = quarantine_mgr
        self.strict_schema = strict_schema
        self.deduplicate_by_key = deduplicate_by_key
        self.dedup_strategy = dedup_strategy

    def validate_customers(
        self, raw_records: List[Dict[str, Any]], source_file: str = "customers"
    ) -> Tuple[List[Dict[str, Any]], ValidationSummary]:
        """Validate customer records."""
        summary = ValidationSummary(entity_name="customers", total_input=len(raw_records))
        stage1_valid: List[Dict[str, Any]] = []

        for record in raw_records:
            if not isinstance(record, dict):
                self.quarantine_mgr.add(
                    entity_name="customers",
                    source_file=source_file,
                    raw_record={"raw": str(record)},
                    error_code="MALFORMED_INPUT",
                    error_message="Record is not a valid JSON object/dictionary",
                )
                summary.quarantined_count += 1
                summary.error_counts["MALFORMED_INPUT"] = summary.error_counts.get("MALFORMED_INPUT", 0) + 1
                continue

            try:
                validated = CustomerInputSchema.model_validate(record)
                stage1_valid.append(validated.model_dump())
            except ValidationError as e:
                err_code, err_msg = self._classify_validation_error(e)
                self.quarantine_mgr.add(
                    entity_name="customers",
                    source_file=source_file,
                    raw_record=record,
                    error_code=err_code,
                    error_message=err_msg,
                    record_id=record.get("customer_id"),
                )
                summary.quarantined_count += 1
                summary.error_counts[err_code] = summary.error_counts.get(err_code, 0) + 1

        # Deduplication step
        final_valid, dedup_count = self._deduplicate(
            stage1_valid,
            key_field="customer_id",
            timestamp_field="updated_at",
            fallback_ts_field="registration_timestamp",
            entity_name="customers",
            source_file=source_file,
        )
        summary.deduplicated_count = dedup_count
        summary.valid_count = len(final_valid)

        return final_valid, summary

    def validate_transactions(
        self,
        raw_records: List[Dict[str, Any]],
        valid_customer_ids: Set[str],
        source_file: str = "transactions",
        enforce_referential_integrity: bool = True,
    ) -> Tuple[List[Dict[str, Any]], ValidationSummary]:
        """Validate transaction records, including foreign key referential integrity."""
        summary = ValidationSummary(entity_name="transactions", total_input=len(raw_records))
        stage1_valid: List[Dict[str, Any]] = []

        for record in raw_records:
            if not isinstance(record, dict):
                self.quarantine_mgr.add(
                    entity_name="transactions",
                    source_file=source_file,
                    raw_record={"raw": str(record)},
                    error_code="MALFORMED_INPUT",
                    error_message="Record is not a valid JSON object/dictionary",
                )
                summary.quarantined_count += 1
                summary.error_counts["MALFORMED_INPUT"] = summary.error_counts.get("MALFORMED_INPUT", 0) + 1
                continue

            try:
                validated = TransactionInputSchema.model_validate(record)
                data = validated.model_dump()

                # Referential Integrity check
                if enforce_referential_integrity:
                    cust_id = data["customer_id"]
                    if cust_id not in valid_customer_ids:
                        self.quarantine_mgr.add(
                            entity_name="transactions",
                            source_file=source_file,
                            raw_record=record,
                            error_code="INVALID_FOREIGN_KEY",
                            error_message=f"Referenced customer_id '{cust_id}' does not exist in valid customer dataset",
                            record_id=data["transaction_id"],
                        )
                        summary.quarantined_count += 1
                        summary.error_counts["INVALID_FOREIGN_KEY"] = summary.error_counts.get("INVALID_FOREIGN_KEY", 0) + 1
                        continue

                stage1_valid.append(data)
            except ValidationError as e:
                err_code, err_msg = self._classify_validation_error(e)
                self.quarantine_mgr.add(
                    entity_name="transactions",
                    source_file=source_file,
                    raw_record=record,
                    error_code=err_code,
                    error_message=err_msg,
                    record_id=record.get("transaction_id"),
                )
                summary.quarantined_count += 1
                summary.error_counts[err_code] = summary.error_counts.get(err_code, 0) + 1

        # Deduplication step
        final_valid, dedup_count = self._deduplicate(
            stage1_valid,
            key_field="transaction_id",
            timestamp_field="updated_at",
            fallback_ts_field="transaction_timestamp",
            entity_name="transactions",
            source_file=source_file,
        )
        summary.deduplicated_count = dedup_count
        summary.valid_count = len(final_valid)

        return final_valid, summary

    def _deduplicate(
        self,
        records: List[Dict[str, Any]],
        key_field: str,
        timestamp_field: str,
        fallback_ts_field: str,
        entity_name: str,
        source_file: str,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Handles duplicate primary keys according to configured policy."""
        if not self.deduplicate_by_key:
            return records, 0

        seen: Dict[str, Dict[str, Any]] = {}
        duplicates_count = 0

        for r in records:
            key = r[key_field]
            if key not in seen:
                seen[key] = r
            else:
                duplicates_count += 1
                if self.dedup_strategy == "reject_all_duplicates":
                    # Quarantine duplicate
                    self.quarantine_mgr.add(
                        entity_name=entity_name,
                        source_file=source_file,
                        raw_record=r,
                        error_code="DUPLICATE_KEY",
                        error_message=f"Duplicate primary key '{key}' encountered",
                        record_id=key,
                    )
                else:
                    # Latest timestamp wins
                    existing_ts = seen[key].get(timestamp_field) or seen[key].get(fallback_ts_field) or ""
                    current_ts = r.get(timestamp_field) or r.get(fallback_ts_field) or ""
                    if current_ts >= existing_ts:
                        # Replace with the fresher record
                        seen[key] = r

        return list(seen.values()), duplicates_count

    def _classify_validation_error(self, e: ValidationError) -> Tuple[str, str]:
        """Classify Pydantic validation error into standard error taxonomy."""
        errors = e.errors()
        first = errors[0] if errors else {}
        err_type = first.get("type", "")
        loc = ".".join(str(x) for x in first.get("loc", []))
        msg = first.get("msg", "Validation failed")

        if "extra_forbidden" in err_type:
            return "UNEXPECTED_COLUMN", f"Schema violation: unexpected field '{loc}'"
        elif "missing" in err_type:
            return "MISSING_REQUIRED_FIELD", f"Missing mandatory field '{loc}'"
        elif any(t in err_type for t in ["int", "float", "bool", "string_type", "type_error"]):
            return "INVALID_DATA_TYPE", f"Type coercion failure on field '{loc}': {msg}"
        else:
            return "BUSINESS_RULE_VIOLATION", f"Business rule constraint failed on '{loc}': {msg}"

"""Tests for validation, schema integrity, deduplication, and quarantine routing."""

import pytest
from src.pipeline.quarantine import QuarantineManager
from src.pipeline.validator import DataValidator


def test_validator_rejects_missing_required_fields():
    quar_mgr = QuarantineManager(run_id="test_run")
    validator = DataValidator(quarantine_mgr=quar_mgr)

    invalid_cust = {
        "customer_id": "CUST-001",
        # "email" is missing
        "full_name": "Test User",
        "phone_number": "555-1234",
        "ssn_or_tax_id": "123-45-6789",
        "date_of_birth": "1990-01-01",
        "street_address": "123 St",
        "city": "City",
        "state": "ST",
        "postal_code": "12345",
        "country": "US",
        "registration_timestamp": "2026-01-01T00:00:00+00:00",
        "risk_score": 0.5,
    }

    valid_records, summary = validator.validate_customers([invalid_cust])
    assert len(valid_records) == 0
    assert summary.quarantined_count == 1
    assert "MISSING_REQUIRED_FIELD" in summary.error_counts
    assert quar_mgr.count == 1
    assert quar_mgr.records[0].error_code == "MISSING_REQUIRED_FIELD"


def test_validator_rejects_unexpected_columns_in_strict_mode():
    quar_mgr = QuarantineManager(run_id="test_run")
    validator = DataValidator(quarantine_mgr=quar_mgr, strict_schema=True)

    cust = {
        "customer_id": "CUST-002",
        "full_name": "Test User",
        "email": "user@example.com",
        "phone_number": "555-123-4567",
        "ssn_or_tax_id": "123-45-6789",
        "date_of_birth": "1990-01-01",
        "street_address": "123 St",
        "city": "City",
        "state": "ST",
        "postal_code": "12345",
        "country": "US",
        "registration_timestamp": "2026-01-01T00:00:00+00:00",
        "risk_score": 0.5,
        "unauthorized_extra_field": "injected_data",
    }

    valid_records, summary = validator.validate_customers([cust])
    assert len(valid_records) == 0
    assert summary.quarantined_count == 1
    assert "UNEXPECTED_COLUMN" in summary.error_counts


def test_validator_deduplication_latest_timestamp_wins():
    quar_mgr = QuarantineManager(run_id="test_run")
    validator = DataValidator(quarantine_mgr=quar_mgr, deduplicate_by_key=True, dedup_strategy="latest_timestamp")

    rec1 = {
        "customer_id": "CUST-DUP-01",
        "full_name": "Original Name",
        "email": "orig@example.com",
        "phone_number": "555-111-2222",
        "ssn_or_tax_id": "123-45-6789",
        "date_of_birth": "1990-01-01",
        "street_address": "123 St",
        "city": "Old City",
        "state": "ST",
        "postal_code": "12345",
        "country": "US",
        "registration_timestamp": "2026-01-01T00:00:00+00:00",
        "risk_score": 0.5,
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    rec2 = rec1.copy()
    rec2["city"] = "New Fresher City"
    rec2["updated_at"] = "2026-02-01T00:00:00+00:00"

    valid_records, summary = validator.validate_customers([rec1, rec2])
    assert len(valid_records) == 1
    assert summary.deduplicated_count == 1
    assert valid_records[0]["city"] == "New Fresher City"


def test_referential_integrity_quarantines_orphan_transactions():
    quar_mgr = QuarantineManager(run_id="test_run")
    validator = DataValidator(quarantine_mgr=quar_mgr)

    known_cust_ids = {"CUST-KNOWN-01"}

    orphan_tx = {
        "transaction_id": "TXN-ORPHAN-01",
        "customer_id": "CUST-UNKNOWN-99",  # Does not exist
        "transaction_timestamp": "2026-03-01T10:00:00+00:00",
        "amount": 150.00,
        "currency": "USD",
        "card_number": "4111111111111234",
        "ip_address": "192.168.1.100",
        "merchant_category": "Retail",
        "status": "SETTLED",
    }

    valid_tx, summary = validator.validate_transactions(
        raw_records=[orphan_tx],
        valid_customer_ids=known_cust_ids,
        enforce_referential_integrity=True,
    )
    assert len(valid_tx) == 0
    assert summary.quarantined_count == 1
    assert "INVALID_FOREIGN_KEY" in summary.error_counts
    assert quar_mgr.records[0].error_code == "INVALID_FOREIGN_KEY"


def test_business_rules_negative_amount_and_invalid_currency():
    quar_mgr = QuarantineManager(run_id="test_run")
    validator = DataValidator(quarantine_mgr=quar_mgr)

    bad_tx_neg = {
        "transaction_id": "TXN-NEG",
        "customer_id": "CUST-01",
        "transaction_timestamp": "2026-03-01T10:00:00+00:00",
        "amount": -50.0,  # Negative amount rejected
        "currency": "USD",
        "card_number": "4111111111111234",
        "ip_address": "192.168.1.100",
        "merchant_category": "Retail",
        "status": "SETTLED",
    }

    bad_tx_curr = {
        "transaction_id": "TXN-CURR",
        "customer_id": "CUST-01",
        "transaction_timestamp": "2026-03-01T10:00:00+00:00",
        "amount": 50.0,
        "currency": "UNKNOWN_CURR",  # Unsupported currency
        "card_number": "4111111111111234",
        "ip_address": "192.168.1.100",
        "merchant_category": "Retail",
        "status": "SETTLED",
    }

    valid_tx, summary = validator.validate_transactions(
        raw_records=[bad_tx_neg, bad_tx_curr],
        valid_customer_ids={"CUST-01"},
    )
    assert len(valid_tx) == 0
    assert summary.quarantined_count == 2


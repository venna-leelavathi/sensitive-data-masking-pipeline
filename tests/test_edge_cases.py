"""Tests for domain-specific edge cases, boundary values, and negative scenarios."""

import pytest
from src.pipeline.quarantine import QuarantineManager
from src.pipeline.validator import DataValidator
from src.pipeline.runner import PipelineRunner
from src.pipeline.ingestion import DataIngestor


def test_edge_case_leap_year_dob(test_app_config, test_masking_config):
    quar_mgr = QuarantineManager(run_id="test_leap")
    validator = DataValidator(quarantine_mgr=quar_mgr)

    leap_cust = {
        "customer_id": "CUST-LEAP-01",
        "full_name": "Leap Year Baby",
        "email": "leap@example.com",
        "phone_number": "555-222-3333",
        "ssn_or_tax_id": "123-45-6789",
        "date_of_birth": "2000-02-29",  # Valid leap day
        "street_address": "29 Leap Rd",
        "city": "Leap City",
        "state": "CA",
        "postal_code": "90210",
        "country": "US",
        "registration_timestamp": "2026-01-01T00:00:00+00:00",
        "risk_score": 0.2,
    }

    valid_records, summary = validator.validate_customers([leap_cust])
    assert len(valid_records) == 1
    assert summary.quarantined_count == 0


def test_edge_case_extreme_transaction_amounts(test_app_config, test_masking_config):
    runner = PipelineRunner(app_config=test_app_config, masking_config=test_masking_config)

    cust = [{
        "customer_id": "CUST-EXT-01",
        "full_name": "Extreme Spender",
        "email": "spend@example.com",
        "phone_number": "555-999-8888",
        "ssn_or_tax_id": "999-88-7777",
        "date_of_birth": "1980-05-12",
        "street_address": "1 High Roller St",
        "city": "Las Vegas",
        "state": "NV",
        "postal_code": "89109",
        "country": "US",
        "registration_timestamp": "2026-01-01T00:00:00+00:00",
        "risk_score": 0.95,
    }]

    txs = [
        {
            "transaction_id": "TXN-MICRO-01",
            "customer_id": "CUST-EXT-01",
            "transaction_timestamp": "2026-02-01T12:00:00+00:00",
            "amount": 0.01,  # Minimum boundary
            "currency": "USD",
            "card_number": "4111111111111234",
            "ip_address": "10.0.0.1",
            "merchant_category": "Tech",
            "status": "SETTLED",
        },
        {
            "transaction_id": "TXN-MACRO-01",
            "customer_id": "CUST-EXT-01",
            "transaction_timestamp": "2026-02-02T12:00:00+00:00",
            "amount": 999999.99,  # High value boundary
            "currency": "USD",
            "card_number": "4111111111111234",
            "ip_address": "10.0.0.1",
            "merchant_category": "Retail",
            "status": "SETTLED",
        },
    ]

    res = runner.run(customers_input=cust, transactions_input=txs)
    assert res["status"] == "SUCCESS"
    assert res["published_transactions_count"] == 2


def test_edge_case_unicode_international_names(test_app_config, test_masking_config):
    quar_mgr = QuarantineManager(run_id="test_unicode")
    validator = DataValidator(quarantine_mgr=quar_mgr)

    unicode_cust = {
        "customer_id": "CUST-UNI-01",
        "full_name": "Renée Müller-D'Souza",
        "email": "renee@example.com",
        "phone_number": "555-333-4444",
        "ssn_or_tax_id": "123-45-6789",
        "date_of_birth": "1988-11-23",
        "street_address": "45 Boulevard Saint-Germain",
        "city": "Montréal",
        "state": "QC",
        "postal_code": "10001",
        "country": "US",
        "registration_timestamp": "2026-01-01T00:00:00+00:00",
        "risk_score": 0.45,
    }

    valid_records, summary = validator.validate_customers([unicode_cust])
    assert len(valid_records) == 1
    assert summary.quarantined_count == 0


def test_edge_case_malformed_input_non_dict(test_app_config, test_masking_config):
    quar_mgr = QuarantineManager(run_id="test_malformed")
    validator = DataValidator(quarantine_mgr=quar_mgr)

    malformed_items = ["NOT_A_DICT", 12345, None]
    valid_records, summary = validator.validate_customers(malformed_items)
    assert len(valid_records) == 0
    assert summary.quarantined_count == 3
    assert quar_mgr.records[0].error_code == "MALFORMED_INPUT"


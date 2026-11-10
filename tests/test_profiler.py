"""Tests for sensitive data detection, entropy calculation, and profiling."""

import pandas as pd
from src.profiler.detector import SensitiveDataProfiler, calculate_entropy
from src.profiler.report import generate_profile_report_markdown


def test_entropy_calculation():
    # Empty string should yield 0 entropy
    assert calculate_entropy("") == 0.0
    # Single character has 0 entropy
    assert calculate_entropy("aaaa") == 0.0
    # High diversity string has higher entropy
    ent = calculate_entropy("abcdefghijklmnop")
    assert ent > 3.0


def test_sensitive_profiling_detection():
    data = {
        "customer_id": ["CUST-001", "CUST-002", "CUST-003"],
        "email": ["alice@example.com", "bob@corp.org", "charlie@web.io"],
        "phone_number": ["+1-555-123-4567", "555-987-6543", "+1-212-555-0199"],
        "ssn_or_tax_id": ["123-45-6789", "987-65-4321", "111-22-3333"],
        "card_number": ["4111111111111111", "5500000000000004", "378282246310005"],
        "ip_address": ["192.168.1.1", "10.0.0.5", "172.16.254.1"],
        "city": ["New York", "Chicago", "Seattle"],
    }
    df = pd.DataFrame(data)
    profiler = SensitiveDataProfiler(confidence_threshold=0.60)
    result = profiler.profile_dataframe(df, dataset_name="test_dataset")

    assert result.record_count == 3
    assert result.column_profiles["email"].is_sensitive
    assert result.column_profiles["email"].detected_category == "PII_EMAIL"
    assert result.column_profiles["phone_number"].detected_category == "PII_PHONE"
    assert result.column_profiles["ssn_or_tax_id"].detected_category == "PII_SSN"
    assert result.column_profiles["ssn_or_tax_id"].recommended_strategy == "drop"
    assert result.column_profiles["card_number"].detected_category == "PCI_CREDIT_CARD"
    assert result.column_profiles["ip_address"].detected_category == "PII_IP_ADDRESS"
    assert not result.column_profiles["city"].is_sensitive


def test_markdown_report_generation():
    data = {"email": ["alice@example.com"], "amount": [100.50]}
    df = pd.DataFrame(data)
    profiler = SensitiveDataProfiler(confidence_threshold=0.60)
    result = profiler.profile_dataframe(df, dataset_name="test_report")
    md = generate_profile_report_markdown(result)
    assert "# Sensitive Data Profiling Report: `test_report`" in md
    assert "PII_EMAIL" in md


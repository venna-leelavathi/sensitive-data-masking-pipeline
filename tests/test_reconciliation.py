"""Tests for reconciliation engine, conservation math, and leakage assertions."""

import pandas as pd
from src.reconciliation.reconciler import DataReconciler
from src.pipeline.quarantine import QuarantineRecord


def test_reconciliation_detects_unauthorized_pii_leak():
    raw_c = [{"customer_id": "C1", "ssn_or_tax_id": "000-00-0000"}]
    raw_t = []

    # Leaked SSN in published dataframe
    bad_published_c = pd.DataFrame([{
        "customer_token": "tok_123",
        "ssn_or_tax_id": "000-00-0000",  # LEAK!
    }])
    published_t = pd.DataFrame()

    res = DataReconciler.reconcile(
        raw_customers=raw_c,
        raw_transactions=raw_t,
        published_customers_df=bad_published_c,
        published_transactions_df=published_t,
        quarantined_records=[],
        valid_customers_count=1,
        valid_transactions_count=0,
    )

    assert not res.all_passed
    assert res.failed_checks >= 1
    # Check that Data Minimization check failed
    min_check = next(c for c in res.checks if c.check_name == "Data Minimization Verification")
    assert not min_check.passed


def test_reconciliation_detects_referential_orphan():
    raw_c = [{"customer_id": "C1"}]
    raw_t = [{"transaction_id": "T1", "customer_id": "C999", "amount": 10.0}]

    pub_c = pd.DataFrame([{"customer_token": "tok_C1"}])
    pub_t = pd.DataFrame([{
        "transaction_id": "T1",
        "customer_token": "tok_ORPHAN",  # Does not exist in pub_c
        "amount": 10.0,
    }])

    res = DataReconciler.reconcile(
        raw_customers=raw_c,
        raw_transactions=raw_t,
        published_customers_df=pub_c,
        published_transactions_df=pub_t,
        quarantined_records=[],
        valid_customers_count=1,
        valid_transactions_count=1,
    )

    assert not res.all_passed
    orphan_check = next(c for c in res.checks if c.check_name == "Target Referential Integrity Invariant")
    assert not orphan_check.passed


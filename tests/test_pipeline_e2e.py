"""End-to-end pipeline execution tests including idempotency, empty batches, and audit ledgers."""

import sqlite3
import pandas as pd
from pathlib import Path
from src.pipeline.runner import PipelineRunner


def test_happy_path_e2e(test_app_config, test_masking_config, sample_clean_data):
    custs, txs = sample_clean_data
    runner = PipelineRunner(app_config=test_app_config, masking_config=test_masking_config)

    res = runner.run(customers_input=custs, transactions_input=txs)
    assert res["status"] == "SUCCESS"
    assert res["quarantined_total"] == 0
    assert res["reconciliation"].all_passed

    # Verify published Parquet files exist
    cust_pq = test_app_config.storage.output_dir / "analytical_customers.parquet"
    tx_pq = test_app_config.storage.output_dir / "analytical_transactions.parquet"
    assert cust_pq.exists()
    assert tx_pq.exists()

    df_c = pd.read_parquet(cust_pq)
    df_t = pd.read_parquet(tx_pq)
    unique_cust_ids = {c["customer_id"] for c in custs}
    unique_tx_ids = {t["transaction_id"] for t in txs}
    assert len(df_c) == len(unique_cust_ids)
    assert len(df_t) == len(unique_tx_ids)

    # Verify no raw PII in output
    assert "ssn_or_tax_id" not in df_c.columns
    assert "street_address" not in df_c.columns
    assert "card_number" not in df_t.columns


def test_empty_batch_handling(test_app_config, test_masking_config):
    runner = PipelineRunner(app_config=test_app_config, masking_config=test_masking_config)
    res = runner.run(customers_input=[], transactions_input=[])
    assert res["input_total"] == 0
    assert res["published_total"] == 0
    assert res["reconciliation"].all_passed


def test_idempotent_reruns(test_app_config, test_masking_config, sample_clean_data):
    custs, txs = sample_clean_data
    runner = PipelineRunner(app_config=test_app_config, masking_config=test_masking_config)

    # First run
    res1 = runner.run(customers_input=custs, transactions_input=txs)
    initial_pub_c = res1["published_customers_count"]
    initial_pub_t = res1["published_transactions_count"]

    # Second run with exact same data
    res2 = runner.run(customers_input=custs, transactions_input=txs)

    # Parquet record counts must remain identical (zero duplicate inflation)
    df_c = pd.read_parquet(test_app_config.storage.output_dir / "analytical_customers.parquet")
    df_t = pd.read_parquet(test_app_config.storage.output_dir / "analytical_transactions.parquet")
    assert len(df_c) == initial_pub_c
    assert len(df_t) == initial_pub_t

    # SQLite record counts must also remain identical
    conn = sqlite3.connect(test_app_config.storage.sqlite_db_path)
    cur = conn.cursor()
    c_count = cur.execute("SELECT count(*) FROM analytical_customers").fetchone()[0]
    t_count = cur.execute("SELECT count(*) FROM analytical_transactions").fetchone()[0]
    conn.close()
    assert c_count == initial_pub_c
    assert t_count == initial_pub_t


def test_audit_ledger_persisted(test_app_config, test_masking_config, sample_clean_data):
    custs, txs = sample_clean_data
    runner = PipelineRunner(app_config=test_app_config, masking_config=test_masking_config)
    res = runner.run(customers_input=custs, transactions_input=txs)

    audit_file = Path(res["audit_file"])
    assert audit_file.exists()

    ledger_file = test_app_config.storage.audit_dir / "audit_ledger.jsonl"
    assert ledger_file.exists()
    assert ledger_file.stat().st_size > 0

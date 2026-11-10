"""Pytest fixtures and shared configuration."""

import pytest
from pathlib import Path
from src.config import AppConfig, MaskingConfig, load_app_config, load_masking_config
from src.generator.synthetic_data import SyntheticDataGenerator, GenerationSpec


@pytest.fixture
def test_app_config(tmp_path: Path) -> AppConfig:
    cfg = load_app_config()
    cfg.storage.input_dir = tmp_path / "input"
    cfg.storage.output_dir = tmp_path / "output"
    cfg.storage.quarantine_dir = tmp_path / "quarantine"
    cfg.storage.audit_dir = tmp_path / "audit"
    cfg.storage.sqlite_db_path = tmp_path / "output" / "test_store.db"
    return cfg


@pytest.fixture
def test_masking_config() -> MaskingConfig:
    return load_masking_config()


@pytest.fixture
def sample_clean_data():
    gen = SyntheticDataGenerator(seed=123)
    spec = GenerationSpec(num_customers=20, num_transactions=60, anomaly_rate=0.0, seed=123)
    custs, txs, labels = gen.generate(spec)
    return custs, txs


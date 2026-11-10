"""Configuration loader and schema validator using Pydantic."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from pydantic import BaseModel, Field


class PipelineSettings(BaseModel):
    name: str = "sensitive_data_masking_pipeline"
    version: str = "1.0.0"
    batch_size: int = 10000
    secret_salt: str = "antigravity-secure-salt-2026-v1"


class StorageSettings(BaseModel):
    input_dir: Path = Path("data/input")
    output_dir: Path = Path("data/output")
    quarantine_dir: Path = Path("data/quarantine")
    audit_dir: Path = Path("data/audit")
    sqlite_db_path: Path = Path("data/output/analytical_store.db")
    publish_format: str = "parquet"  # parquet, csv, sqlite, all


class ValidationSettings(BaseModel):
    strict_schema: bool = True
    allow_extra_columns: bool = False
    deduplicate_by_key: bool = True
    dedup_strategy: str = "latest_timestamp"  # latest_timestamp, reject_all_duplicates
    enforce_referential_integrity: bool = True


class ProfilerSettings(BaseModel):
    sample_size: int = 1000
    confidence_threshold: float = 0.70
    auto_generate_rules: bool = True


class AppConfig(BaseModel):
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    validation: ValidationSettings = Field(default_factory=ValidationSettings)
    profiler: ProfilerSettings = Field(default_factory=ProfilerSettings)


class MaskingRule(BaseModel):
    strategy: str
    target_column: Optional[str] = None
    description: Optional[str] = None
    extra_derived: Optional[List[Dict[str, str]]] = None


class MaskingConfig(BaseModel):
    customers: Dict[str, MaskingRule] = Field(default_factory=dict)
    transactions: Dict[str, MaskingRule] = Field(default_factory=dict)


def load_yaml(file_path: str | Path) -> Dict[str, Any]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {file_path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_app_config(config_path: str | Path = "config/pipeline_config.yaml") -> AppConfig:
    data = load_yaml(config_path)
    return AppConfig.model_validate(data)


def load_masking_config(config_path: str | Path = "config/masking_rules.yaml") -> MaskingConfig:
    data = load_yaml(config_path)
    customers_rules = {k: MaskingRule.model_validate(v) for k, v in data.get("customers", {}).items()}
    transactions_rules = {k: MaskingRule.model_validate(v) for k, v in data.get("transactions", {}).items()}
    return MaskingConfig(customers=customers_rules, transactions=transactions_rules)

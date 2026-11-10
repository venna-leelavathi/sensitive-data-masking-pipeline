"""Idempotent publisher writing sanitized analytical datasets to Parquet, CSV, and SQLite."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from src.pipeline.ingestion import DataIngestor


class TargetPublisher:
    """Publishes analytical datasets idempotently to multiple storage formats."""

    def __init__(self, output_dir: str | Path, sqlite_db_path: Optional[str | Path] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_db_path = Path(sqlite_db_path) if sqlite_db_path else self.output_dir / "analytical_store.db"
        self.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)

    def publish_customers(
        self,
        df: pd.DataFrame,
        publish_format: str = "parquet",
        mode: str = "upsert",
    ) -> Dict[str, str]:
        """Publish sanitized customers dataset idempotently."""
        primary_key = "customer_token"
        return self._publish_dataset(
            df=df,
            table_name="analytical_customers",
            primary_key=primary_key,
            publish_format=publish_format,
            mode=mode,
        )

    def publish_transactions(
        self,
        df: pd.DataFrame,
        publish_format: str = "parquet",
        mode: str = "upsert",
    ) -> Dict[str, str]:
        """Publish sanitized transactions dataset idempotently."""
        primary_key = "transaction_id"
        return self._publish_dataset(
            df=df,
            table_name="analytical_transactions",
            primary_key=primary_key,
            publish_format=publish_format,
            mode=mode,
        )

    def _publish_dataset(
        self,
        df: pd.DataFrame,
        table_name: str,
        primary_key: str,
        publish_format: str,
        mode: str = "upsert",
    ) -> Dict[str, str]:
        if df.empty:
            return {"status": "EMPTY_DATASET", "published_records": "0"}

        artifacts: Dict[str, str] = {}
        target_parquet = self.output_dir / f"{table_name}.parquet"
        target_csv = self.output_dir / f"{table_name}.csv"

        # Idempotent merge logic for files
        merged_df = df.copy()
        if target_parquet.exists() and mode == "upsert" and primary_key in df.columns:
            try:
                existing_df = pd.read_parquet(target_parquet)
                if primary_key in existing_df.columns:
                    # Combine existing and new, keeping new rows on key collision (idempotent upsert)
                    combined = pd.concat([existing_df, df], ignore_index=True)
                    merged_df = combined.drop_duplicates(subset=[primary_key], keep="last")
            except Exception:
                merged_df = df.copy()

        # Write Parquet
        if publish_format in ["parquet", "all"]:
            merged_df.to_parquet(target_parquet, index=False)
            artifacts["parquet_file"] = str(target_parquet)
            artifacts["parquet_checksum"] = DataIngestor.calculate_file_checksum(target_parquet)

        # Write CSV
        if publish_format in ["csv", "all"]:
            merged_df.to_csv(target_csv, index=False)
            artifacts["csv_file"] = str(target_csv)
            artifacts["csv_checksum"] = DataIngestor.calculate_file_checksum(target_csv)

        # Write SQLite Relational Store
        if publish_format in ["sqlite", "all"] or self.sqlite_db_path:
            self._upsert_sqlite(merged_df, table_name, primary_key)
            artifacts["sqlite_db"] = str(self.sqlite_db_path)

        artifacts["published_records"] = str(len(merged_df))
        return artifacts

    def _upsert_sqlite(self, df: pd.DataFrame, table_name: str, primary_key: str) -> None:
        """Execute SQLite UPSERT ensuring idempotent safe reruns."""
        conn = sqlite3.connect(self.sqlite_db_path)
        try:
            # Create table with PRIMARY KEY constraint if not exists
            cols = list(df.columns)
            # Map pandas types to SQLite types
            col_defs = []
            for col in cols:
                dtype = str(df[col].dtype)
                if "int" in dtype:
                    sql_type = "INTEGER"
                elif "float" in dtype:
                    sql_type = "REAL"
                else:
                    sql_type = "TEXT"
                
                if col == primary_key:
                    sql_type += " PRIMARY KEY"
                col_defs.append(f'"{col}" {sql_type}')

            create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(col_defs)});'
            conn.execute(create_sql)

            # Insert or replace
            placeholders = ", ".join(["?"] * len(cols))
            col_names = ", ".join([f'"{c}"' for c in cols])
            insert_sql = f'INSERT OR REPLACE INTO "{table_name}" ({col_names}) VALUES ({placeholders})'

            # Convert NaN to None for clean SQLite NULLs
            records_tuples = [
                tuple(None if pd.isna(val) else val for val in row)
                for row in df.itertuples(index=False, name=None)
            ]
            conn.executemany(insert_sql, records_tuples)
            conn.commit()
        finally:
            conn.close()


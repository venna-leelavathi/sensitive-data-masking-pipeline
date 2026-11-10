"""Config-driven masking and minimization execution engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
import pandas as pd
from src.config import MaskingConfig, MaskingRule
from src.masking import strategies


class MaskingEngine:
    """Executes masking rules and minimization transforms on records/DataFrames."""

    def __init__(self, masking_config: MaskingConfig, secret_salt: str = "antigravity-secure-salt-2026-v1"):
        self.config = masking_config
        self.salt = secret_salt
        self._strategy_map = {
            "hmac_token": lambda v, row=None: strategies.hmac_token(v, salt=self.salt),
            "sha256_hash": lambda v, row=None: strategies.sha256_hash(v, salt=self.salt),
            "partial_mask_email": lambda v, row=None: strategies.partial_mask_email(v),
            "partial_mask_phone": lambda v, row=None: strategies.partial_mask_phone(v),
            "partial_mask_card": lambda v, row=None: strategies.partial_mask_card(v),
            "partial_mask_name": lambda v, row=None: strategies.partial_mask_name(v),
            "mask_ip_subnet": lambda v, row=None: strategies.mask_ip_subnet(v),
            "generalize_dob_to_age_group": lambda v, row=None: strategies.generalize_dob_to_age_group(v),
            "truncate_postal_code": lambda v, row=None: strategies.truncate_postal_code(v),
            "derive_risk_tier": lambda v, row=None: strategies.derive_risk_tier(v),
            "redact_full": lambda v, row=None: strategies.redact_full(v),
            "pass_through": lambda v, row=None: v,
        }

    def transform_dataframe(
        self, df: pd.DataFrame, entity_name: str, run_id: Optional[str] = None
    ) -> tuple[pd.DataFrame, Dict[str, str]]:
        """Apply masking and minimization rules to an entire DataFrame.
        
        Returns:
            Tuple of (Transformed DataFrame, Dict of column -> applied strategy manifest).
        """
        if df.empty:
            return df.copy(), {}

        rules: Dict[str, MaskingRule] = getattr(self.config, entity_name, {})
        if not rules:
            return df.copy(), {}

        result_df = pd.DataFrame(index=df.index)
        manifest: Dict[str, str] = {}

        # 1. Apply primary rules
        for src_col, rule in rules.items():
            if src_col not in df.columns:
                continue

            strat = rule.strategy
            manifest[src_col] = strat

            if strat == "drop":
                # Data minimization: omitted from target
                continue

            target_col = rule.target_column or src_col
            handler = self._strategy_map.get(strat, lambda v, row=None: v)
            result_df[target_col] = df[src_col].apply(lambda val: handler(val))

            # 2. Check for extra derived columns
            if rule.extra_derived:
                for derivation in rule.extra_derived:
                    der_target = derivation.get("target_column")
                    der_strat = derivation.get("strategy")
                    if not der_target or not der_strat:
                        continue
                    manifest[f"{src_col}->{der_target}"] = der_strat

                    if der_strat == "extract_year_month":
                        result_df[der_target] = df[src_col].apply(strategies.extract_year_month)
                    elif der_strat == "normalize_usd":
                        # Requires currency column if available
                        curr_col = df["currency"] if "currency" in df.columns else pd.Series("USD", index=df.index)
                        result_df[der_target] = [
                            strategies.normalize_usd(amt, curr)
                            for amt, curr in zip(df[src_col], curr_col)
                        ]

        # 3. Add pipeline audit metadata
        if run_id:
            result_df["_pipeline_run_id"] = run_id
            result_df["_processed_at"] = pd.Timestamp.now(tz="UTC").isoformat()

        return result_df, manifest

"""Sensitive field detection and data profiling engine."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import pandas as pd


@dataclass
class PatternDefinition:
    category: str
    pattern: re.Pattern
    recommended_strategy: str
    column_keywords: List[str]


PATTERNS: List[PatternDefinition] = [
    PatternDefinition(
        category="PII_SSN",
        pattern=re.compile(r"^(?:\d{3}-\d{2}-\d{4}|\d{9})$"),
        recommended_strategy="drop",
        column_keywords=["ssn", "tax_id", "national_id", "social_security"],
    ),
    PatternDefinition(
        category="PII_EMAIL",
        pattern=re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
        recommended_strategy="partial_mask_email",
        column_keywords=["email", "mail", "contact_email"],
    ),
    PatternDefinition(
        category="PII_PHONE",
        pattern=re.compile(r"^\+?1?[-.\s]?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}$"),
        recommended_strategy="partial_mask_phone",
        column_keywords=["phone", "mobile", "cell", "tel", "contact_phone"],
    ),
    PatternDefinition(
        category="PCI_CREDIT_CARD",
        pattern=re.compile(r"^(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}|(?:2131|1800|35\d{3})\d{11}|(?:\d{4}[-\s]?){3}\d{4})$"),
        recommended_strategy="partial_mask_card",
        column_keywords=["card", "credit_card", "pan", "account_number", "debit_card"],
    ),
    PatternDefinition(
        category="PII_IP_ADDRESS",
        pattern=re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"),
        recommended_strategy="mask_ip_subnet",
        column_keywords=["ip", "ip_address", "client_ip", "remote_addr"],
    ),
    PatternDefinition(
        category="PII_DOB",
        pattern=re.compile(r"^(?:19|20)\d{2}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])$"),
        recommended_strategy="generalize_dob_to_age_group",
        column_keywords=["dob", "birth", "birth_date", "date_of_birth"],
    ),
    PatternDefinition(
        category="PII_POSTAL_CODE",
        pattern=re.compile(r"^\d{5}(?:-\d{4})?$"),
        recommended_strategy="truncate_postal_code",
        column_keywords=["zip", "postal", "postal_code", "zipcode"],
    ),
    PatternDefinition(
        category="PII_NAME",
        pattern=re.compile(r"^[A-Z][a-zA-Z'.-]+(?:\s+[A-Z][a-zA-Z'.-]+)+$"),
        recommended_strategy="partial_mask_name",
        column_keywords=["name", "full_name", "first_name", "last_name", "customer_name"],
    ),
    PatternDefinition(
        category="PII_ADDRESS",
        pattern=re.compile(r"^\d+\s+[A-Za-z0-9\s.,#-]+(?:St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Ln|Lane|Dr|Drive|Way|Ct|Court)\.?$", re.IGNORECASE),
        recommended_strategy="drop",
        column_keywords=["address", "street", "street_address", "residence"],
    ),
]


def calculate_entropy(text: str) -> float:
    """Calculate Shannon entropy of a string."""
    if not text:
        return 0.0
    counts = Counter(text)
    total = len(text)
    return -sum((c / total) * math.log2(c / total) for c in counts.values())


@dataclass
class ColumnProfile:
    column_name: str
    total_records: int
    non_null_records: int
    null_percentage: float
    unique_count: int
    inferred_type: str
    detected_category: str
    confidence: float
    sample_values: List[str]
    sample_entropy: float
    recommended_strategy: str
    is_sensitive: bool


@dataclass
class ProfileResult:
    dataset_name: str
    record_count: int
    column_profiles: Dict[str, ColumnProfile] = field(default_factory=dict)
    sensitive_columns_count: int = 0


class SensitiveDataProfiler:
    """Profiles datasets to detect and classify sensitive personal data."""

    def __init__(self, confidence_threshold: float = 0.60):
        self.confidence_threshold = confidence_threshold

    def profile_dataframe(self, df: pd.DataFrame, dataset_name: str = "dataset") -> ProfileResult:
        result = ProfileResult(dataset_name=dataset_name, record_count=len(df))
        sensitive_count = 0

        for col in df.columns:
            profile = self.profile_column(df[col], col)
            result.column_profiles[col] = profile
            if profile.is_sensitive:
                sensitive_count += 1

        result.sensitive_columns_count = sensitive_count
        return result

    def profile_column(self, series: pd.Series, column_name: str) -> ColumnProfile:
        total = len(series)
        non_null_series = series.dropna()
        non_null_count = len(non_null_series)
        null_pct = round(((total - non_null_count) / total * 100), 2) if total > 0 else 0.0
        unique_cnt = int(series.nunique())
        inferred_type = str(series.dtype)

        # Convert sample values to string for pattern profiling
        sample_size = min(1000, non_null_count)
        samples = non_null_series.sample(n=sample_size, random_state=42).astype(str).tolist() if sample_size > 0 else []
        display_samples = samples[:3]

        # Calculate average entropy
        avg_entropy = round(sum(calculate_entropy(s) for s in samples) / len(samples), 3) if samples else 0.0

        best_category = "NON_SENSITIVE"
        best_confidence = 0.0
        best_strategy = "pass_through"

        col_lower = column_name.lower()

        for pat in PATTERNS:
            name_match_score = 0.0
            for kw in pat.column_keywords:
                if kw == col_lower:
                    name_match_score = 0.50
                    break
                elif kw in col_lower:
                    name_match_score = 0.35
                    break

            data_match_ratio = 0.0
            if samples:
                matches = sum(1 for s in samples if pat.pattern.match(s.strip()))
                data_match_ratio = matches / len(samples)

            # Combined confidence score
            if data_match_ratio > 0.0:
                confidence = (data_match_ratio * 0.7) + (name_match_score * 0.6)
            elif name_match_score >= 0.35 and ("id" in col_lower or "name" in col_lower or "dob" in col_lower or "ssn" in col_lower):
                confidence = name_match_score
            else:
                confidence = 0.0

            confidence = min(round(confidence, 3), 1.0)

            if confidence > best_confidence:
                best_confidence = confidence
                best_category = pat.category
                best_strategy = pat.recommended_strategy

        # Special case: check customer_id / account identifier
        if "id" in col_lower and ("customer" in col_lower or "user" in col_lower or "client" in col_lower):
            if best_confidence < 0.6:
                best_category = "IDENTIFIER_KEY"
                best_confidence = 0.85
                best_strategy = "hmac_token"

        is_sensitive = best_confidence >= self.confidence_threshold and best_category != "NON_SENSITIVE"

        if not is_sensitive:
            best_category = "NON_SENSITIVE"
            best_strategy = "pass_through"

        return ColumnProfile(
            column_name=column_name,
            total_records=total,
            non_null_records=non_null_count,
            null_percentage=null_pct,
            unique_count=unique_cnt,
            inferred_type=inferred_type,
            detected_category=best_category,
            confidence=best_confidence,
            sample_values=display_samples,
            sample_entropy=avg_entropy,
            recommended_strategy=best_strategy,
            is_sensitive=is_sensitive,
        )


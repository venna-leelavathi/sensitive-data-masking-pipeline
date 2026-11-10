"""Sensitive data profiling report generators (Markdown & JSON)."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Dict, Any
from src.profiler.detector import ProfileResult


def generate_profile_report_markdown(result: ProfileResult) -> str:
    """Generate GitHub-flavored Markdown profiling report."""
    md = [
        f"# Sensitive Data Profiling Report: `{result.dataset_name}`",
        "",
        f"- **Total Records Analyzed**: {result.record_count:,}",
        f"- **Total Columns**: {len(result.column_profiles)}",
        f"- **Sensitive Columns Detected**: {result.sensitive_columns_count}",
        "",
        "| Column Name | Inferred Type | Null % | Detected Category | Confidence | Recommended Masking Strategy |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for col, profile in result.column_profiles.items():
        sens_badge = "🚨 " if profile.is_sensitive else "✅ "
        cat_display = f"{sens_badge}{profile.detected_category}"
        md.append(
            f"| `{col}` | `{profile.inferred_type}` | {profile.null_percentage}% | {cat_display} | {profile.confidence:.2f} | `{profile.recommended_strategy}` |"
        )

    md.append("")
    md.append("## Detailed Field Breakdown")
    md.append("")
    for col, profile in result.column_profiles.items():
        if profile.is_sensitive:
            md.append(f"### Field: `{col}`")
            md.append(f"- **Classification**: `{profile.detected_category}` (Confidence: {profile.confidence:.1%})")
            md.append(f"- **Distinct Values**: {profile.unique_count:,}")
            md.append(f"- **Shannon Entropy**: {profile.sample_entropy}")
            md.append(f"- **Recommended Strategy**: `{profile.recommended_strategy}`")
            md.append("")

    return "\n".join(md)


def export_profile_report_json(result: ProfileResult, output_path: str | Path) -> None:
    """Export profile result as JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "dataset_name": result.dataset_name,
        "record_count": result.record_count,
        "sensitive_columns_count": result.sensitive_columns_count,
        "columns": {col: asdict(prof) for col, prof in result.column_profiles.items()},
    }
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

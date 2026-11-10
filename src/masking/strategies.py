"""Individual masking, pseudonymization, and minimization strategies."""

from __future__ import annotations

import hashlib
import hmac
import re
from datetime import datetime
from functools import lru_cache
from typing import Any, Optional


@lru_cache(maxsize=200000)
def _cached_hmac_inner(val_str: str, salt: str) -> str:
    """Memoized HMAC computation for dramatic speedup on repeated join keys."""
    val_bytes = val_str.encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    h = hmac.new(salt_bytes, val_bytes, hashlib.sha256).hexdigest()
    return f"tok_{h[:16]}"


def hmac_token(value: Any, salt: str = "antigravity-secure-salt-2026-v1") -> Optional[str]:
    """Deterministic keyed HMAC-SHA256 token preserving analytical joins."""
    if value is None or str(value).strip() == "":
        return None
    val_str = str(value).strip()
    return _cached_hmac_inner(val_str, salt)


def sha256_hash(value: Any, salt: str = "antigravity-secure-salt-2026-v1") -> Optional[str]:
    """Deterministic salted SHA-256 hash."""
    if value is None or str(value).strip() == "":
        return None
    salted = f"{salt}:{str(value).strip()}".encode("utf-8")
    return hashlib.sha256(salted).hexdigest()


def partial_mask_email(value: Any) -> Optional[str]:
    """Retain first character of username and the domain (e.g., j***e@domain.com)."""
    if value is None or str(value).strip() == "":
        return None
    val_str = str(value).strip()
    if "@" not in val_str:
        return "[INVALID_EMAIL]"
    parts = val_str.split("@", 1)
    user, domain = parts[0], parts[1]
    if len(user) <= 1:
        masked_user = f"{user}***"
    elif len(user) == 2:
        masked_user = f"{user[0]}***{user[1]}"
    else:
        masked_user = f"{user[0]}***{user[-1]}"
    return f"{masked_user}@{domain}"


def partial_mask_phone(value: Any) -> Optional[str]:
    """Retain last 4 digits only (e.g., ***-***-1234)."""
    if value is None or str(value).strip() == "":
        return None
    val_str = str(value).strip()
    digits = re.sub(r"\D", "", val_str)
    if len(digits) < 4:
        return "***-***-****"
    last4 = digits[-4:]
    return f"***-***-{last4}"


def partial_mask_card(value: Any) -> Optional[str]:
    """Retain last 4 digits only with PCI-DSS 16-char format (e.g. ****-****-****-1234)."""
    if value is None or str(value).strip() == "":
        return None
    val_str = str(value).strip()
    digits = re.sub(r"\D", "", val_str)
    if len(digits) < 4:
        return "****************"
    last4 = digits[-4:]
    return f"****-****-****-{last4}"


def partial_mask_name(value: Any) -> Optional[str]:
    """Retain first letter of each word (e.g. Johnathan Doe -> J*** D**)."""
    if value is None or str(value).strip() == "":
        return None
    words = str(value).strip().split()
    masked_words = []
    for w in words:
        if len(w) <= 1:
            masked_words.append(w)
        else:
            masked_words.append(f"{w[0]}" + "*" * min(3, len(w) - 1))
    return " ".join(masked_words)


def mask_ip_subnet(value: Any) -> Optional[str]:
    """Mask host part of IPv4 to /24 CIDR (e.g., 192.168.1.42 -> 192.168.1.0/24)."""
    if value is None or str(value).strip() == "":
        return None
    val_str = str(value).strip()
    octets = val_str.split(".")
    if len(octets) == 4 and all(o.isdigit() and 0 <= int(o) <= 255 for o in octets):
        return f"{octets[0]}.{octets[1]}.{octets[2]}.0/24"
    return "0.0.0.0/24"


def generalize_dob_to_age_group(value: Any, reference_year: int = 2026) -> Optional[str]:
    """Convert exact date of birth (YYYY-MM-DD) to age bracket."""
    if value is None or str(value).strip() == "":
        return None
    val_str = str(value).strip()
    try:
        dt = datetime.strptime(val_str[:10], "%Y-%m-%d")
        age = reference_year - dt.year
        if age < 18:
            return "<18"
        elif 18 <= age <= 24:
            return "18-24"
        elif 25 <= age <= 34:
            return "25-34"
        elif 35 <= age <= 49:
            return "35-49"
        elif 50 <= age <= 64:
            return "50-64"
        else:
            return "65+"
    except Exception:
        return "UNKNOWN"


def truncate_postal_code(value: Any) -> Optional[str]:
    """Truncate postal code to 3 digits (HIPAA Safe Harbor standard, e.g. 94107 -> 94100)."""
    if value is None or str(value).strip() == "":
        return None
    digits = re.sub(r"\D", "", str(value).strip())
    if len(digits) >= 3:
        return f"{digits[:3]}00"
    return "00000"


def derive_risk_tier(value: Any) -> str:
    """Classify numerical risk score into tiers."""
    try:
        val = float(value)
        if val < 0.33:
            return "LOW"
        elif val < 0.66:
            return "MEDIUM"
        else:
            return "HIGH"
    except (ValueError, TypeError):
        return "UNKNOWN"


FX_RATES_TO_USD = {
    "USD": 1.00,
    "EUR": 1.08,
    "GBP": 1.28,
    "CAD": 0.74,
    "JPY": 0.0065,
    "AUD": 0.65,
}


def normalize_usd(amount: Any, currency: Any = "USD") -> float:
    """Normalize monetary amount to USD using deterministic reference rates."""
    try:
        amt = float(amount)
        curr = str(currency).upper().strip() if currency else "USD"
        rate = FX_RATES_TO_USD.get(curr, 1.00)
        return round(amt * rate, 2)
    except (ValueError, TypeError):
        return 0.0


def extract_year_month(timestamp_val: Any) -> str:
    """Extract YYYY-MM cohort partition from timestamp."""
    if timestamp_val is None or str(timestamp_val).strip() == "":
        return "UNKNOWN"
    val_str = str(timestamp_val).strip()
    try:
        return val_str[:7]
    except Exception:
        return "UNKNOWN"


def redact_full(value: Any) -> str:
    """Full redaction constant."""
    return "[REDACTED]"

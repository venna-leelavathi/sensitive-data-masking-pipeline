"""Tests for individual masking algorithms and engine transformation."""

import pandas as pd
from src.masking import strategies
from src.masking.engine import MaskingEngine
from src.config import load_masking_config


def test_hmac_token_determinism_and_salting():
    salt1 = "salt-A"
    salt2 = "salt-B"
    val = "CUST-0001"

    # Determinism with same salt
    tok1 = strategies.hmac_token(val, salt=salt1)
    tok2 = strategies.hmac_token(val, salt=salt1)
    assert tok1 == tok2
    assert tok1.startswith("tok_")

    # Different salt produces different token
    tok_diff = strategies.hmac_token(val, salt=salt2)
    assert tok1 != tok_diff

    # Null handling
    assert strategies.hmac_token(None) is None
    assert strategies.hmac_token("") is None


def test_partial_masking_strategies():
    # Email
    assert strategies.partial_mask_email("john.doe@example.com") == "j***e@example.com"
    assert strategies.partial_mask_email("a@b.com") == "a***@b.com"
    assert strategies.partial_mask_email(None) is None

    # Phone
    assert strategies.partial_mask_phone("+1-555-123-4567") == "***-***-4567"
    assert strategies.partial_mask_phone("1234567890") == "***-***-7890"

    # Credit Card
    masked_card = strategies.partial_mask_card("4111111111111234")
    assert masked_card == "****-****-****-1234"

    # Name
    assert strategies.partial_mask_name("Johnathan Doe") == "J*** D**"
    assert strategies.partial_mask_name("Alice") == "A***"

    # IP Subnet
    assert strategies.mask_ip_subnet("192.168.1.55") == "192.168.1.0/24"
    assert strategies.mask_ip_subnet("10.0.50.200") == "10.0.50.0/24"


def test_generalization_and_bucketing():
    # DOB to Age Group
    assert strategies.generalize_dob_to_age_group("2000-05-15", reference_year=2026) == "25-34"
    assert strategies.generalize_dob_to_age_group("1950-01-01", reference_year=2026) == "65+"
    assert strategies.generalize_dob_to_age_group("2015-08-20", reference_year=2026) == "<18"

    # Postal Code truncation
    assert strategies.truncate_postal_code("94107") == "94100"
    assert strategies.truncate_postal_code("10001-1234") == "10000"

    # Risk Tier
    assert strategies.derive_risk_tier(0.15) == "LOW"
    assert strategies.derive_risk_tier(0.50) == "MEDIUM"
    assert strategies.derive_risk_tier(0.85) == "HIGH"


def test_currency_normalization():
    assert strategies.normalize_usd(100.0, "USD") == 100.0
    assert strategies.normalize_usd(100.0, "EUR") == 108.0
    assert strategies.normalize_usd(100.0, "GBP") == 128.0


def test_masking_engine_drops_unminimized_columns():
    cfg = load_masking_config()
    engine = MaskingEngine(masking_config=cfg, secret_salt="test-salt")

    raw_df = pd.DataFrame([{
        "customer_id": "CUST-001",
        "full_name": "Jane Doe",
        "email": "jane@example.com",
        "phone_number": "555-123-4567",
        "ssn_or_tax_id": "123-45-6789",
        "date_of_birth": "1995-04-12",
        "street_address": "123 Main St",
        "city": "Boston",
        "state": "MA",
        "postal_code": "02108",
        "country": "US",
        "registration_timestamp": "2026-01-01T00:00:00+00:00",
        "risk_score": 0.25,
    }])

    transformed_df, manifest = engine.transform_dataframe(raw_df, entity_name="customers")

    # Minimized columns MUST NOT appear in transformed output
    assert "ssn_or_tax_id" not in transformed_df.columns
    assert "street_address" not in transformed_df.columns
    # Check transformed target columns
    assert "customer_token" in transformed_df.columns
    assert "masked_name" in transformed_df.columns
    assert "masked_email" in transformed_df.columns
    assert "age_group" in transformed_df.columns
    assert "postal_code_3" in transformed_df.columns
    assert "risk_tier" in transformed_df.columns
    assert transformed_df["risk_tier"].iloc[0] == "LOW"

"""Pydantic schemas and type validators for source entities."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
SSN_REGEX = re.compile(r"^(?:\d{3}-\d{2}-\d{4}|\d{9})$")
IP_REGEX = re.compile(r"^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$")
ALLOWED_CURRENCIES = {"USD", "EUR", "GBP", "CAD", "JPY", "AUD"}
ALLOWED_STATUSES = {"SETTLED", "PENDING", "DECLINED", "REFUNDED"}


def parse_iso_datetime(value: str) -> datetime:
    """Parse ISO-8601 timestamp string safely."""
    val = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(val)


class CustomerInputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")  # Catch unexpected schema changes

    customer_id: str = Field(..., min_length=1)
    full_name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=3)
    phone_number: str = Field(..., min_length=7)
    ssn_or_tax_id: str = Field(..., min_length=9)
    date_of_birth: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    street_address: str = Field(..., min_length=3)
    city: str = Field(..., min_length=1)
    state: str = Field(..., min_length=2)
    postal_code: str = Field(..., min_length=3)
    country: str = Field(..., min_length=2)
    registration_timestamp: str
    risk_score: float = Field(..., ge=0.0, le=1.0)
    updated_at: Optional[str] = None

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("customer_id cannot be blank")
        return v.strip()

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        clean = v.strip()
        if not EMAIL_REGEX.match(clean):
            raise ValueError(f"Invalid email format: {v}")
        return clean

    @field_validator("ssn_or_tax_id")
    @classmethod
    def validate_ssn(cls, v: str) -> str:
        clean = v.strip()
        if not SSN_REGEX.match(clean):
            raise ValueError(f"Invalid SSN format: {v}")
        return clean

    @field_validator("date_of_birth")
    @classmethod
    def validate_dob(cls, v: str) -> str:
        try:
            dt = datetime.strptime(v, "%Y-%m-%d")
            if dt.year < 1900 or dt > datetime.now():
                raise ValueError(f"date_of_birth out of realistic range: {v}")
        except ValueError as e:
            raise ValueError(f"Invalid date_of_birth: {e}")
        return v

    @field_validator("registration_timestamp")
    @classmethod
    def validate_reg_time(cls, v: str) -> str:
        try:
            parse_iso_datetime(v)
        except Exception as e:
            raise ValueError(f"Invalid ISO-8601 registration_timestamp: {e}")
        return v


class TransactionInputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")  # Catch unexpected schema changes

    transaction_id: str = Field(..., min_length=1)
    customer_id: str = Field(..., min_length=1)
    transaction_timestamp: str
    amount: float = Field(..., gt=0.0)
    currency: str = Field(..., min_length=3, max_length=3)
    card_number: str = Field(..., min_length=12)
    ip_address: str
    merchant_category: str = Field(..., min_length=1)
    status: str
    updated_at: Optional[str] = None

    @field_validator("transaction_id")
    @classmethod
    def validate_transaction_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("transaction_id cannot be blank")
        return v.strip()

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        c = v.upper().strip()
        if c not in ALLOWED_CURRENCIES:
            raise ValueError(f"Unsupported currency: {v}. Must be one of {ALLOWED_CURRENCIES}")
        return c

    @field_validator("ip_address")
    @classmethod
    def validate_ip(cls, v: str) -> str:
        clean = v.strip()
        if not IP_REGEX.match(clean):
            raise ValueError(f"Invalid IPv4 address format: {v}")
        return clean

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        s = v.upper().strip()
        if s not in ALLOWED_STATUSES:
            raise ValueError(f"Unsupported status: {v}. Must be one of {ALLOWED_STATUSES}")
        return s

    @field_validator("transaction_timestamp")
    @classmethod
    def validate_tx_time(cls, v: str) -> str:
        try:
            parse_iso_datetime(v)
        except Exception as e:
            raise ValueError(f"Invalid ISO-8601 transaction_timestamp: {e}")
        return v


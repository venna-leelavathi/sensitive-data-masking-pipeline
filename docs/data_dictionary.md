# Data Dictionary: Sensitive Data Masking & Minimization Pipeline

This document defines the schemas, data types, keys, nullability, referential relationships, and privacy transformations for all datasets in the pipeline.

---

## 1. Source Entity: `customers`

**Grain**: 1 row per customer registration profile  
**Primary Key**: `customer_id`  
**Description**: Raw ingestion feed containing personally identifiable information (PII) of registered customers.

| Column Name | Data Type | Nullable | Uniqueness | Sensitivity Classification | Description & Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `customer_id` | String | No | Primary Key | `IDENTIFIER_KEY` | Format: `CUST-XXXXXX`. Deterministic unique key. |
| `full_name` | String | No | No | `PII_DIRECT` | Customer legal name. |
| `email` | String | No | No | `PII_DIRECT` | Valid RFC-5322 email regex. |
| `phone_number` | String | No | No | `PII_DIRECT` | Contact phone number. |
| `ssn_or_tax_id` | String | No | No | `PII_DIRECT_GOV` | US Social Security Number (`XXX-XX-XXXX`). |
| `date_of_birth` | String | No | No | `PII_QUASI_IDENTIFIER` | ISO-8601 Date (`YYYY-MM-DD`). Real year between 1900 and present. |
| `street_address` | String | No | No | `PII_DIRECT` | Street address. |
| `city` | String | No | No | `NON_SENSITIVE` | City name. |
| `state` | String | No | No | `NON_SENSITIVE` | State abbreviation (e.g., `CA`, `NY`). |
| `postal_code` | String | No | No | `PII_QUASI_IDENTIFIER` | 5-digit US ZIP code (`XXXXX` or `XXXXX-XXXX`). |
| `country` | String | No | No | `NON_SENSITIVE` | Country code (e.g., `US`). |
| `registration_timestamp`| String | No | No | `BUSINESS_ATTRIBUTE` | ISO-8601 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`). |
| `risk_score` | Float | No | No | `BUSINESS_ATTRIBUTE` | Float between `0.0` and `1.0`. |
| `updated_at` | String | Yes | No | `LINEAGE_METADATA` | ISO-8601 UTC timestamp used for latest-timestamp deduplication. |

---

## 2. Source Entity: `transactions`

**Grain**: 1 row per financial transaction  
**Primary Key**: `transaction_id`  
**Foreign Key**: `customer_id` references `customers.customer_id`  
**Description**: Transaction events emitted by payment terminals or web checkout.

| Column Name | Data Type | Nullable | Uniqueness | Sensitivity Classification | Description & Validation Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `transaction_id` | String | No | Primary Key | `IDENTIFIER_KEY` | Format: `TXN-XXXXXXX`. Unique transaction ID. |
| `customer_id` | String | No | Foreign Key | `IDENTIFIER_KEY` | Must match a valid `customers.customer_id`. |
| `transaction_timestamp` | String | No | No | `BUSINESS_ATTRIBUTE` | ISO-8601 UTC event timestamp. |
| `amount` | Float | No | No | `BUSINESS_ATTRIBUTE` | Transaction amount in transaction currency (`amount > 0.0`). |
| `currency` | String | No | No | `BUSINESS_ATTRIBUTE` | ISO-4217 Currency Code (`USD`, `EUR`, `GBP`, `CAD`, `JPY`, `AUD`). |
| `card_number` | String | No | No | `PCI_CREDIT_CARD` | 13–19 digit payment card primary account number (PAN). |
| `ip_address` | String | No | No | `PII_QUASI_IDENTIFIER` | IPv4 address of checkout client. |
| `merchant_category` | String | No | No | `BUSINESS_ATTRIBUTE` | Industry category (Retail, Groceries, Travel, Tech, Healthcare). |
| `status` | String | No | No | `BUSINESS_ATTRIBUTE` | `SETTLED`, `PENDING`, `DECLINED`, `REFUNDED`. |
| `updated_at` | String | Yes | No | `LINEAGE_METADATA` | ISO-8601 UTC timestamp for deduplication. |

---

## 3. Target Published Entity: `analytical_customers`

**Grain**: 1 row per unique customer  
**Primary Key**: `customer_token`  
**Storage Formats**: Parquet (`analytical_customers.parquet`) & SQLite (`analytical_store.db`)  
**Minimization Rule**: Raw SSN and raw street address are completely **DROPPED** (GDPR/HIPAA compliance).

| Column Name | Data Type | Source Field | Transformation / Masking Strategy | Purpose / Compliance |
| :--- | :--- | :--- | :--- | :--- |
| `customer_token` | String | `customer_id` | Keyed HMAC-SHA256 (`tok_<16-hex>`) | Pseudonymized join key across datasets without exposing identity. |
| `masked_name` | String | `full_name` | First initial + asterisks (`J*** D**`) | Anonymized identifier for cohort analysis. |
| `masked_email` | String | `email` | `j***e@domain.com` | Preserves domain for domain analytics while hiding mailbox. |
| `masked_phone` | String | `phone_number`| `***-***-1234` | Retains last 4 digits only. |
| `age_group` | String | `date_of_birth` | Generalized bracket (`<18`, `18-24`, `25-34`, `35-49`, `50-64`, `65+`) | HIPAA Safe Harbor & GDPR demographic minimization. |
| `city` | String | `city` | Pass-through | Regional reporting. |
| `state` | String | `state` | Pass-through | State-level reporting. |
| `postal_code_3` | String | `postal_code` | Truncated to 3 digits (`94100`) | HIPAA Safe Harbor k-anonymity standard. |
| `country` | String | `country` | Pass-through | Country code. |
| `registration_timestamp` | String | `registration_timestamp` | Pass-through | Customer cohort analysis. |
| `risk_tier` | String | `risk_score` | Derived tier: `LOW`, `MEDIUM`, `HIGH` | Categorical risk modeling without exposing exact raw float score. |
| `_pipeline_run_id` | String | Pipeline | Execution UUID | Data lineage and audit provenance. |
| `_processed_at` | String | System | ISO-8601 UTC timestamp | Audit timestamp. |

---

## 4. Target Published Entity: `analytical_transactions`

**Grain**: 1 row per financial transaction  
**Primary Key**: `transaction_id`  
**Foreign Key**: `customer_token` references `analytical_customers.customer_token`  
**Storage Formats**: Parquet (`analytical_transactions.parquet`) & SQLite (`analytical_store.db`)  
**Minimization Rule**: Full credit card number and granular IP host bits are removed.

| Column Name | Data Type | Source Field | Transformation / Masking Strategy | Purpose / Compliance |
| :--- | :--- | :--- | :--- | :--- |
| `transaction_id` | String | `transaction_id` | Pass-through | Unique transaction event identifier. |
| `customer_token` | String | `customer_id` | Keyed HMAC-SHA256 (`tok_<16-hex>`) | Pseudonymized foreign key joining to `analytical_customers`. |
| `transaction_timestamp` | String | `transaction_timestamp` | Pass-through | Event timestamp. |
| `transaction_year_month` | String | `transaction_timestamp` | Derived `YYYY-MM` string | Partition key and cohort temporal grouping. |
| `amount` | Float | `amount` | Pass-through | Transaction face value. |
| `amount_usd` | Float | `amount`, `currency` | Deterministic FX normalization | Standardized USD aggregate comparison. |
| `currency` | String | `currency` | Pass-through | ISO currency code. |
| `masked_card_last4` | String | `card_number` | `****-****-****-1234` | PCI-DSS compliance: PAN truncation. |
| `ip_subnet` | String | `ip_address` | CIDR `/24` masking (`192.168.1.0/24`) | Subnet geolocation without tracking individual user IP endpoints. |
| `merchant_category` | String | `merchant_category` | Pass-through | Merchant analytics. |
| `status` | String | `status` | Pass-through | Transaction status. |
| `_pipeline_run_id` | String | Pipeline | Execution UUID | Provenance & lineage. |
| `_processed_at` | String | System | ISO-8601 UTC timestamp | Audit timestamp. |

---

## 5. Quarantine Entity: `pipeline_quarantine`

**Grain**: 1 row per rejected record  
**Storage Formats**: JSON Lines (`quarantine_<run_id>.jsonl`) and Parquet (`quarantine_<run_id>.parquet`)

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `quarantine_id` | String | Unique identifier (`quar_<hex>`). |
| `run_id` | String | Pipeline execution identifier. |
| `entity_name` | String | Source entity (`customers` or `transactions`). |
| `source_file` | String | Originating file name or stream identifier. |
| `record_id` | String | Identified record primary key or `UNKNOWN`. |
| `error_code` | String | Standard taxonomy: `SCHEMA_VIOLATION`, `MISSING_REQUIRED_FIELD`, `DUPLICATE_KEY`, `INVALID_FOREIGN_KEY`, `INVALID_DATA_TYPE`, `BUSINESS_RULE_VIOLATION`, `UNEXPECTED_COLUMN`, `MALFORMED_INPUT`. |
| `error_message` | String | Human-readable root cause explanation. |
| `source_record_raw` | String | Exact JSON serialization of the offending raw record for replayability. |
| `rejected_at` | String | ISO-8601 UTC timestamp of quarantine action. |

---

## 6. Audit Ledger Entity: `pipeline_audit_runs`

**Grain**: 1 row per pipeline execution run  
**Storage Formats**: SQLite (`pipeline_audit_runs`), JSON Lines (`audit_ledger.jsonl`), and individual JSON files (`runs/run_<run_id>.json`)

| Column Name | Data Type | Description |
| :--- | :--- | :--- |
| `run_id` | String | Primary Key. Deterministic execution ID. |
| `pipeline_name` | String | Pipeline module name. |
| `pipeline_version` | String | Semantic version of code pipeline. |
| `start_time` | String | ISO-8601 UTC execution start timestamp. |
| `end_time` | String | ISO-8601 UTC execution completion timestamp. |
| `duration_seconds` | Float | Total wall-clock execution time. |
| `status` | String | `SUCCESS`, `PARTIAL_SUCCESS`, `FAILED`. |
| `total_input_records` | Integer | Total records ingested across all source entities. |
| `total_valid_records` | Integer | Total records successfully validated. |
| `total_quarantined_records` | Integer | Total records quarantined. |
| `total_published_records` | Integer | Total records written to target store. |
| `reconciliation_status` | String | `PASSED` or `FAILED`. |
| `failure_reason` | String (Nullable) | Unhandled exception message if run failed. |


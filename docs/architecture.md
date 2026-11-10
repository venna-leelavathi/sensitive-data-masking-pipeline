# Architecture & Data Flow Design

## 1. System Overview

The **Sensitive Data Masking and Analytical Minimization Pipeline** is designed to profile arbitrary synthetic incoming datasets, identify direct and quasi-identifiers, apply cryptographically secure masking and tokenization, and publish a minimized analytical dataset with complete auditability, zero data leakage, and idempotent rerun guarantees.

```
+--------------------------------------------------------------------------------------------------------+
|                                  DATA ENGINEERING PIPELINE ARCHITECTURE                                |
+--------------------------------------------------------------------------------------------------------+

 [Source Feeds]             [Ingestion & Profiling]            [Validation Layer]             [Target Storage]
 +---------------+          +----------------------+          +-------------------+          +------------------+
 | Customers     | -------->| DataIngestor         | -------->| Pydantic Schema   | -------->| MaskingEngine    |
 | (JSON/CSV)    |          | (Multi-format,       |          | - Missing fields  |          | (HMAC-SHA256,    |
 +---------------+          |  streaming chunks)   |          | - Type checking   |          |  Redaction,      |
                            +----------------------+          | - Business rules  |          |  Generalization, |
 [Source Feeds]             +----------------------+          | - Deduplication   |          |  Minimization)   |
 +---------------+          | SensitiveProfiler    |          +---------+---------+          +--------+---------+
 | Transactions  | -------->| (Regex, Entropy,     |                    |                             |
 | (JSON/CSV)    |          |  PII/PCI Catalog)    |                    | Rejects                     |
 +---------------+          +----------------------+                    v                             v
                                                              +-------------------+          +------------------+
                                                              | QuarantineStore   |          | TargetPublisher  |
                                                              | (JSONL & Parquet  |          | (Parquet, CSV,   |
                                                              |  Traceability)    |          |  SQLite UPSERT)  |
                                                              +-------------------+          +--------+---------+
                                                                                                      |
                                                              [Reconciliation & Audit]                v
                                                              +-------------------------------------------------+
                                                              | DataReconciler: Conservation, PK & FK Assertions|
                                                              | AuditLedger: Run Metrics, Checksums, Provenance |
                                                              +-------------------------------------------------+
```

---

## 2. Pipeline Execution Flow

```mermaid
flowchart TD
    A["Raw Input Data (JSON / JSONL / CSV / Parquet)"] --> B["DataIngestor: Compute Checksums & Load Batches"]
    B --> C["SensitiveDataProfiler: Automated PII/PCI Scan & Report"]
    B --> D["DataValidator: Schema & Business Rules Engine"]
    
    subgraph Validation ["Data Quality & Validation Gates"]
        D --> D1{"Format Valid?"}
        D1 -- No --> Q1["Quarantine: MALFORMED_INPUT"]
        D1 -- Yes --> D2{"Pydantic Types & Required Fields?"}
        D2 -- No --> Q2["Quarantine: MISSING_FIELD / INVALID_TYPE / UNEXPECTED_COLUMN"]
        D2 -- Yes --> D3{"Primary Key Collision?"}
        D3 -- Yes --> D4["Deduplicate: Latest Timestamp Wins"]
        D3 -- No --> D5{"Referential Integrity Check"}
        D4 --> D5
        D5 -- Orphan Transaction --> Q3["Quarantine: INVALID_FOREIGN_KEY"]
        D5 -- Valid Foreign Key --> V["Stage Valid Clean Records"]
    end

    V --> M["MaskingEngine: Config-Driven Masking & Minimization"]
    
    subgraph Privacy ["Privacy Engineering & Minimization"]
        M --> M1["Pseudonymize: HMAC-SHA256 Token (tok_<16-hex>)"]
        M --> M2["Drop Direct Identifiers: Raw SSN, Street Address"]
        M --> M3["Generalize: DOB to Age Groups (<18, 18-24, 25-34, ...)"]
        M --> M4["Truncate: 3-Digit ZIP Prefix (HIPAA Safe Harbor)"]
        M --> M5["PCI Truncate: Credit Card to Last 4 Digits"]
        M --> M6["Mask IP: Subnet CIDR /24"]
        M --> M7["Derive Analytical Cohorts: YYYY-MM, USD Normalized Amount"]
    end

    M1 & M2 & M3 & M4 & M5 & M6 & M7 --> P["TargetPublisher: Idempotent Publish"]
    
    subgraph Publishing ["Storage & Serving Layer"]
        P --> P1["Parquet Columnar Files (Optimized for OLAP Analytics)"]
        P --> P2["CSV Minimal Analytical Exports"]
        P --> P3["SQLite Relational Analytical Store (UPSERT by Primary Key)"]
    end

    P1 & P2 & P3 --> R["DataReconciler: Mathematical Balance Assertions"]
    Q1 & Q2 & Q3 --> S["Quarantine Manager: Persist to Disk"]
    R & S --> AL["AuditLedger: Log Run ID, Row Counts, Duration & Checksums"]
```

---

## 3. Entity-Relationship Model

```mermaid
erDiagram
    analytical_customers ||--o{ analytical_transactions : "customer_token"
    customers ||--o{ pipeline_quarantine : "quarantine_id"
    transactions ||--o{ pipeline_quarantine : "quarantine_id"
    pipeline_audit_runs ||--o{ pipeline_quarantine : "run_id"

    analytical_customers {
        string customer_token PK "Deterministic HMAC-SHA256 Token"
        string masked_name "J*** D**"
        string masked_email "j***e@domain.com"
        string masked_phone "***-***-1234"
        string age_group "25-34 (Generalized from DOB)"
        string city "City"
        string state "State"
        string postal_code_3 "3-digit ZIP (HIPAA Safe Harbor)"
        string country "US"
        string registration_timestamp "ISO-8601 UTC"
        string risk_tier "LOW | MEDIUM | HIGH"
        string _pipeline_run_id "Lineage Run ID"
        string _processed_at "ISO-8601 UTC"
    }

    analytical_transactions {
        string transaction_id PK "Unique Transaction ID"
        string customer_token FK "References analytical_customers.customer_token"
        string transaction_timestamp "ISO-8601 UTC"
        string transaction_year_month "YYYY-MM Cohort"
        float amount "Transaction Face Value"
        float amount_usd "Normalized USD"
        string currency "ISO-4217"
        string masked_card_last4 "****-****-****-1234"
        string ip_subnet "192.168.1.0/24"
        string merchant_category "Category"
        string status "SETTLED | PENDING | DECLINED | REFUNDED"
        string _pipeline_run_id "Lineage Run ID"
        string _processed_at "ISO-8601 UTC"
    }

    pipeline_quarantine {
        string quarantine_id PK "Unique rejection ID"
        string run_id FK "Pipeline Run ID"
        string entity_name "customers | transactions"
        string source_file "Source batch file"
        string record_id "Customer/Transaction ID"
        string error_code "Taxonomy code"
        string error_message "Root cause details"
        string source_record_raw "Original payload JSON"
        string rejected_at "ISO-8601 UTC"
    }

    pipeline_audit_runs {
        string run_id PK "Pipeline Run ID"
        string pipeline_name "Module Name"
        string pipeline_version "SemVer"
        string start_time "ISO-8601 UTC"
        string end_time "ISO-8601 UTC"
        float duration_seconds "Wall clock time"
        string status "SUCCESS | PARTIAL_SUCCESS | FAILED"
        int total_input_records "Input count"
        int total_valid_records "Valid count"
        int total_quarantined_records "Quarantine count"
        int total_published_records "Published count"
        string reconciliation_status "PASSED | FAILED"
        string failure_reason "Error trace if failed"
    }
```

---

## 4. Privacy Engineering Principles

1. **GDPR Article 25 (Data Protection by Design and by Default)**:
   - Direct identifiers like SSN and full street addresses are systematically dropped from analytical tables rather than simply obfuscated.
   - Pseudonymized tokens (`customer_token`) use a secret cryptographic salt, preventing dictionary attacks while allowing analytical joins.
2. **HIPAA Safe Harbor Standard (45 CFR § 164.514(b)(2))**:
   - Dates of birth are bucketed into generalized demographic age categories (`<18`, `18-24`, `25-34`, `35-49`, `50-64`, `65+`), preventing re-identification via voter records.
   - ZIP codes are truncated to 3 digits (`postal_code_3`), satisfying the Safe Harbor geographic threshold.
3. **PCI-DSS Requirement 3.4**:
   - Primary Account Numbers (PANs) are strictly masked; only the last 4 digits are retained in target stores. Raw card numbers are never written to downstream analytical tables or logs.
4. **Zero Plaintext Leak Invariant**:
   - Automated reconciliation checks guarantee that zero raw direct identifiers are present in published target schemas. If any forbidden column is detected, the reconciliation assertion fails immediately.

---

## 5. Idempotency & Safe Reruns

- **Deduplication Strategy**: When duplicate primary keys are encountered, the pipeline uses deterministic tie-breaking based on `updated_at` (or transaction timestamp). The fresher record is preserved.
- **Atomic UPSERT**: Publishing to SQLite uses `INSERT OR REPLACE INTO` keyed by primary keys (`customer_token` and `transaction_id`).
- **Parquet Idempotent Overwrite / Merge**: Target Parquet files undergo an idempotent merge: new batches overwrite older records with identical primary keys, guaranteeing that rerunning the exact same input batch produces identical record counts without phantom duplicate rows.

# Sensitive Data Profiling Report: `customers`

- **Total Records Analyzed**: 101
- **Total Columns**: 15
- **Sensitive Columns Detected**: 7

| Column Name | Inferred Type | Null % | Detected Category | Confidence | Recommended Masking Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `customer_id` | `str` | 0.0% | 🚨 IDENTIFIER_KEY | 0.85 | `hmac_token` |
| `full_name` | `str` | 0.0% | 🚨 PII_NAME | 0.90 | `partial_mask_name` |
| `email` | `str` | 0.99% | 🚨 PII_EMAIL | 1.00 | `partial_mask_email` |
| `phone_number` | `str` | 0.0% | 🚨 PII_PHONE | 0.91 | `partial_mask_phone` |
| `ssn_or_tax_id` | `str` | 0.0% | 🚨 PII_SSN | 0.91 | `drop` |
| `date_of_birth` | `str` | 0.0% | 🚨 PII_DOB | 0.91 | `generalize_dob_to_age_group` |
| `street_address` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.24 | `pass_through` |
| `city` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.36 | `pass_through` |
| `state` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `postal_code` | `str` | 0.0% | 🚨 PII_POSTAL_CODE | 0.91 | `truncate_postal_code` |
| `country` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `registration_timestamp` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `risk_score` | `float64` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `updated_at` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `unauthorized_injected_column` | `str` | 98.02% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |

## Detailed Field Breakdown

### Field: `customer_id`
- **Classification**: `IDENTIFIER_KEY` (Confidence: 85.0%)
- **Distinct Values**: 100
- **Shannon Entropy**: 2.651
- **Recommended Strategy**: `hmac_token`

### Field: `full_name`
- **Classification**: `PII_NAME` (Confidence: 90.3%)
- **Distinct Values**: 100
- **Shannon Entropy**: 3.328
- **Recommended Strategy**: `partial_mask_name`

### Field: `email`
- **Classification**: `PII_EMAIL` (Confidence: 100.0%)
- **Distinct Values**: 99
- **Shannon Entropy**: 3.74
- **Recommended Strategy**: `partial_mask_email`

### Field: `phone_number`
- **Classification**: `PII_PHONE` (Confidence: 91.0%)
- **Distinct Values**: 100
- **Shannon Entropy**: 2.994
- **Recommended Strategy**: `partial_mask_phone`

### Field: `ssn_or_tax_id`
- **Classification**: `PII_SSN` (Confidence: 91.0%)
- **Distinct Values**: 100
- **Shannon Entropy**: 2.704
- **Recommended Strategy**: `drop`

### Field: `date_of_birth`
- **Classification**: `PII_DOB` (Confidence: 91.0%)
- **Distinct Values**: 100
- **Shannon Entropy**: 2.586
- **Recommended Strategy**: `generalize_dob_to_age_group`

### Field: `postal_code`
- **Classification**: `PII_POSTAL_CODE` (Confidence: 91.0%)
- **Distinct Values**: 99
- **Shannon Entropy**: 1.949
- **Recommended Strategy**: `truncate_postal_code`

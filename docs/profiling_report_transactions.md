# Sensitive Data Profiling Report: `transactions`

- **Total Records Analyzed**: 501
- **Total Columns**: 11
- **Sensitive Columns Detected**: 3

| Column Name | Inferred Type | Null % | Detected Category | Confidence | Recommended Masking Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `transaction_id` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `customer_id` | `str` | 0.0% | 🚨 IDENTIFIER_KEY | 0.85 | `hmac_token` |
| `transaction_timestamp` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `amount` | `object` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `currency` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `card_number` | `str` | 0.0% | 🚨 PCI_CREDIT_CARD | 0.77 | `partial_mask_card` |
| `ip_address` | `str` | 0.0% | 🚨 PII_IP_ADDRESS | 0.91 | `mask_ip_subnet` |
| `merchant_category` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `status` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `updated_at` | `str` | 0.0% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |
| `injection_probe` | `object` | 98.6% | ✅ NON_SENSITIVE | 0.00 | `pass_through` |

## Detailed Field Breakdown

### Field: `customer_id`
- **Classification**: `IDENTIFIER_KEY` (Confidence: 85.0%)
- **Distinct Values**: 98
- **Shannon Entropy**: 2.655
- **Recommended Strategy**: `hmac_token`

### Field: `card_number`
- **Classification**: `PCI_CREDIT_CARD` (Confidence: 76.9%)
- **Distinct Values**: 500
- **Shannon Entropy**: 2.824
- **Recommended Strategy**: `partial_mask_card`

### Field: `ip_address`
- **Classification**: `PII_IP_ADDRESS` (Confidence: 91.0%)
- **Distinct Values**: 500
- **Shannon Entropy**: 2.675
- **Recommended Strategy**: `mask_ip_subnet`

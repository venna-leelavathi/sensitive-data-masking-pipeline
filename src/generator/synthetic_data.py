"""Reproducible synthetic data generator with controlled anomaly injection."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from faker import Faker


@dataclass
class GenerationSpec:
    num_customers: int = 100
    num_transactions: int = 500
    anomaly_rate: float = 0.05  # 5% anomalous records
    seed: int = 42


class SyntheticDataGenerator:
    """Generates synthetic datasets with deterministic seeds and labeled anomalies."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.faker = Faker()
        Faker.seed(seed)
        random.seed(seed)

    def generate(
        self, spec: GenerationSpec
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
        """Generate customer and transaction datasets along with separate ground-truth labels.
        
        Returns:
            Tuple of (customers_list, transactions_list, ground_truth_labels_dict).
        """
        self.faker.seed_instance(spec.seed)
        random.seed(spec.seed)

        customers: List[Dict[str, Any]] = []
        transactions: List[Dict[str, Any]] = []
        labels: Dict[str, Any] = {
            "metadata": {
                "seed": spec.seed,
                "num_customers": spec.num_customers,
                "num_transactions": spec.num_transactions,
                "anomaly_rate": spec.anomaly_rate,
            },
            "customers": {"valid_ids": [], "anomalous": {}},
            "transactions": {"valid_ids": [], "anomalous": {}},
        }

        base_date = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # 1. Generate Customers
        for i in range(1, spec.num_customers + 1):
            cust_id = f"CUST-{i:06d}"
            reg_date = base_date + timedelta(days=random.randint(0, 180), seconds=random.randint(0, 86400))
            birth_year = random.randint(1950, 2005)
            birth_month = random.randint(1, 12)
            birth_day = min(random.randint(1, 28), 28)
            dob_str = f"{birth_year:04d}-{birth_month:02d}-{birth_day:02d}"

            # Special boundary case for customer #5: Leap year date of birth
            if i == 5:
                dob_str = "2000-02-29"

            # Special boundary case for customer #6: Non-ASCII international name
            name_val = self.faker.name()
            if i == 6:
                name_val = "Renée Müller-D'Souza"

            # Special boundary cases for risk_score
            risk_val = round(random.uniform(0.05, 0.95), 3)
            if i == 7:
                risk_val = 0.0  # Exact lower bound
            elif i == 8:
                risk_val = 1.0  # Exact upper bound

            cust_record = {
                "customer_id": cust_id,
                "full_name": name_val,
                "email": f"{cust_id.lower()}@{self.faker.free_email_domain()}",
                "phone_number": f"+1-{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}",
                "ssn_or_tax_id": f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}",
                "date_of_birth": dob_str,
                "street_address": self.faker.street_address(),
                "city": self.faker.city(),
                "state": self.faker.state_abbr(),
                "postal_code": f"{random.randint(10000, 99999)}",
                "country": "US",
                "registration_timestamp": reg_date.isoformat(),
                "risk_score": risk_val,
                "updated_at": reg_date.isoformat(),
            }

            # Inject controlled anomalies
            is_anomaly = random.random() < spec.anomaly_rate
            if is_anomaly:
                anomaly_type = random.choice([
                    "MISSING_REQUIRED_FIELD",
                    "INVALID_DATA_TYPE",
                    "UNEXPECTED_COLUMN",
                    "BUSINESS_RULE_VIOLATION",
                ])

                if anomaly_type == "MISSING_REQUIRED_FIELD":
                    cust_record["email"] = None
                    labels["customers"]["anomalous"][cust_id] = {
                        "expected_error": "MISSING_REQUIRED_FIELD",
                        "field": "email",
                    }
                elif anomaly_type == "INVALID_DATA_TYPE":
                    cust_record["risk_score"] = "NOT_A_FLOAT"
                    labels["customers"]["anomalous"][cust_id] = {
                        "expected_error": "INVALID_DATA_TYPE",
                        "field": "risk_score",
                    }
                elif anomaly_type == "UNEXPECTED_COLUMN":
                    cust_record["unauthorized_injected_column"] = "MALICIOUS_PAYLOAD"
                    labels["customers"]["anomalous"][cust_id] = {
                        "expected_error": "UNEXPECTED_COLUMN",
                        "field": "unauthorized_injected_column",
                    }
                elif anomaly_type == "BUSINESS_RULE_VIOLATION":
                    cust_record["email"] = "not-an-email-at-all"
                    labels["customers"]["anomalous"][cust_id] = {
                        "expected_error": "BUSINESS_RULE_VIOLATION",
                        "field": "email",
                    }
            else:
                labels["customers"]["valid_ids"].append(cust_id)

            customers.append(cust_record)

        # Inject duplicate customer record
        if spec.num_customers >= 10:
            dup_target = customers[2].copy()
            # Updated version of customer 3 (fresher updated_at)
            dup_target["updated_at"] = (base_date + timedelta(days=200)).isoformat()
            dup_target["city"] = "Updated City"
            customers.append(dup_target)
            labels["customers"]["anomalous"]["CUST-000003_duplicate"] = {
                "expected_error": "DUPLICATE_KEY_SUPERSEDED",
                "target_key": dup_target["customer_id"],
            }

        # Valid customer pool for referential integrity
        valid_cust_ids = labels["customers"]["valid_ids"]
        if not valid_cust_ids:
            valid_cust_ids = [c["customer_id"] for c in customers[:5]]

        # 2. Generate Transactions
        currencies = ["USD", "EUR", "GBP", "CAD"]
        categories = ["Retail", "Groceries", "Travel", "Tech", "Healthcare", "Entertainment"]
        statuses = ["SETTLED", "PENDING", "DECLINED", "REFUNDED"]

        for j in range(1, spec.num_transactions + 1):
            tx_id = f"TXN-{j:07d}"
            parent_cust = random.choice(valid_cust_ids)
            tx_time = base_date + timedelta(days=random.randint(1, 250), seconds=random.randint(0, 86400))
            
            # Boundary case for transaction #1: micro-transaction ($0.01)
            amt = round(random.uniform(5.0, 1500.0), 2)
            if j == 1:
                amt = 0.01
            elif j == 2:
                amt = 99999.99  # Large transaction

            # Edge case: out-of-order transaction timestamp for j=10
            if j == 10:
                tx_time = base_date - timedelta(days=10)  # Late arriving

            tx_record = {
                "transaction_id": tx_id,
                "customer_id": parent_cust,
                "transaction_timestamp": tx_time.isoformat(),
                "amount": amt,
                "currency": random.choice(currencies),
                "card_number": self.faker.credit_card_number(),
                "ip_address": self.faker.ipv4(),
                "merchant_category": random.choice(categories),
                "status": random.choice(statuses),
                "updated_at": tx_time.isoformat(),
            }

            # Inject controlled anomalies
            is_tx_anomaly = random.random() < spec.anomaly_rate
            if is_tx_anomaly:
                tx_anomaly_type = random.choice([
                    "INVALID_FOREIGN_KEY",
                    "BUSINESS_RULE_VIOLATION",
                    "INVALID_DATA_TYPE",
                    "UNEXPECTED_COLUMN",
                ])

                if tx_anomaly_type == "INVALID_FOREIGN_KEY":
                    tx_record["customer_id"] = "CUST-999999"  # Non-existent customer
                    labels["transactions"]["anomalous"][tx_id] = {
                        "expected_error": "INVALID_FOREIGN_KEY",
                        "field": "customer_id",
                    }
                elif tx_anomaly_type == "BUSINESS_RULE_VIOLATION":
                    tx_record["amount"] = -250.00  # Negative transaction amount
                    labels["transactions"]["anomalous"][tx_id] = {
                        "expected_error": "BUSINESS_RULE_VIOLATION",
                        "field": "amount",
                    }
                elif tx_anomaly_type == "INVALID_DATA_TYPE":
                    tx_record["amount"] = "INVALID_NUMBER"
                    labels["transactions"]["anomalous"][tx_id] = {
                        "expected_error": "INVALID_DATA_TYPE",
                        "field": "amount",
                    }
                elif tx_anomaly_type == "UNEXPECTED_COLUMN":
                    tx_record["injection_probe"] = True
                    labels["transactions"]["anomalous"][tx_id] = {
                        "expected_error": "UNEXPECTED_COLUMN",
                        "field": "injection_probe",
                    }
            else:
                labels["transactions"]["valid_ids"].append(tx_id)

            transactions.append(tx_record)

        # Inject duplicate transaction record
        if spec.num_transactions >= 10:
            dup_tx = transactions[4].copy()
            dup_tx["updated_at"] = (base_date + timedelta(days=300)).isoformat()
            transactions.append(dup_tx)
            labels["transactions"]["anomalous"]["TXN-0000005_duplicate"] = {
                "expected_error": "DUPLICATE_KEY_SUPERSEDED",
                "target_key": dup_tx["transaction_id"],
            }

        return customers, transactions, labels

    def save_to_disk(
        self,
        customers: List[Dict[str, Any]],
        transactions: List[Dict[str, Any]],
        labels: Dict[str, Any],
        output_dir: str | Path = "data/input",
        labels_dir: str | Path = "data/sample_labeled",
        format_type: str = "json",
    ) -> Dict[str, Path]:
        """Save synthetic datasets and separate ground-truth labels."""
        out_p = Path(output_dir)
        lbl_p = Path(labels_dir)
        out_p.mkdir(parents=True, exist_ok=True)
        lbl_p.mkdir(parents=True, exist_ok=True)

        cust_file = out_p / f"customers.{format_type}"
        tx_file = out_p / f"transactions.{format_type}"
        lbl_file = lbl_p / "ground_truth_labels.json"

        if format_type == "json":
            with open(cust_file, "w", encoding="utf-8") as f:
                json.dump(customers, f, indent=2)
            with open(tx_file, "w", encoding="utf-8") as f:
                json.dump(transactions, f, indent=2)
        elif format_type == "jsonl":
            with open(cust_file, "w", encoding="utf-8") as f:
                for r in customers:
                    f.write(json.dumps(r) + "\n")
            with open(tx_file, "w", encoding="utf-8") as f:
                for r in transactions:
                    f.write(json.dumps(r) + "\n")

        with open(lbl_file, "w", encoding="utf-8") as f:
            json.dump(labels, f, indent=2)

        return {"customers": cust_file, "transactions": tx_file, "labels": lbl_file}

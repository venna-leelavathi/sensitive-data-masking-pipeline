"""Command-line interface for the Sensitive Data Masking Pipeline."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
import pandas as pd

from src.config import load_app_config, load_masking_config
from src.generator.synthetic_data import SyntheticDataGenerator, GenerationSpec
from src.pipeline.ingestion import DataIngestor
from src.pipeline.runner import PipelineRunner
from src.profiler.detector import SensitiveDataProfiler
from src.profiler.report import generate_profile_report_markdown, export_profile_report_json


def cmd_generate(args: argparse.Namespace) -> None:
    print(f"[*] Generating synthetic dataset (seed={args.seed})...")
    generator = SyntheticDataGenerator(seed=args.seed)
    spec = GenerationSpec(
        num_customers=args.customers,
        num_transactions=args.transactions,
        anomaly_rate=args.anomaly_rate,
        seed=args.seed,
    )
    custs, txs, labels = generator.generate(spec)
    files = generator.save_to_disk(
        customers=custs,
        transactions=txs,
        labels=labels,
        output_dir=args.output_dir,
        labels_dir=args.labels_dir,
        format_type=args.format,
    )
    print(f"[+] Successfully generated:")
    print(f"    - Customers: {len(custs):,} records -> {files['customers']}")
    print(f"    - Transactions: {len(txs):,} records -> {files['transactions']}")
    print(f"    - Ground Truth Labels -> {files['labels']}")


def cmd_profile(args: argparse.Namespace) -> None:
    print(f"[*] Profiling dataset: {args.input_file}")
    records = DataIngestor.load_records(args.input_file)
    if not records:
        print("[-] Input dataset is empty.")
        return

    df = pd.DataFrame(records)
    profiler = SensitiveDataProfiler(confidence_threshold=args.threshold)
    result = profiler.profile_dataframe(df, dataset_name=args.dataset_name)

    print(f"[+] Analysis Complete:")
    print(f"    - Total records: {result.record_count:,}")
    print(f"    - Sensitive columns detected: {result.sensitive_columns_count} / {len(result.column_profiles)}")

    for col, prof in result.column_profiles.items():
        if prof.is_sensitive:
            print(f"      * {col}: {prof.detected_category} ({prof.confidence:.1%}) -> {prof.recommended_strategy}")

    if args.markdown_out:
        md = generate_profile_report_markdown(result)
        out_p = Path(args.markdown_out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"[+] Markdown report written to {args.markdown_out}")

    if args.json_out:
        export_profile_report_json(result, args.json_out)
        print(f"[+] JSON report written to {args.json_out}")


def cmd_run(args: argparse.Namespace) -> None:
    print(f"[*] Starting Data Masking & Minimization Pipeline...")
    app_cfg = load_app_config(args.config)
    mask_cfg = load_masking_config(args.masking)

    runner = PipelineRunner(app_config=app_cfg, masking_config=mask_cfg)
    result = runner.run(
        customers_input=args.customers,
        transactions_input=args.transactions,
        run_id=args.run_id,
    )

    print("\n" + "=" * 60)
    print(f"PIPELINE EXECUTION SUMMARY: {result['run_id']}")
    print("=" * 60)
    print(f"Status:               {result['status']}")
    print(f"Duration:             {result['duration_seconds']}s")
    print(f"Total Input Records:  {result['input_total']:,}")
    print(f"Valid Processed:      {result['valid_total']:,}")
    print(f"Quarantined Records:  {result['quarantined_total']:,}")
    print(f"Published Customers:  {result['published_customers_count']:,}")
    print(f"Published Txns:       {result['published_transactions_count']:,}")
    print(f"Audit Trail Saved:    {result['audit_file']}")
    print("-" * 60)
    recon = result["reconciliation"]
    print(f"Reconciliation:       {'ALL PASSED (PASSED)' if recon.all_passed else 'FAILURES DETECTED'}")
    for c in recon.checks:
        mark = "[PASS]" if c.passed else "[FAIL]"
        print(f"  {mark} {c.check_name}: Expected={c.expected}, Actual={c.actual}")
    print("=" * 60 + "\n")


def cmd_benchmark(args: argparse.Namespace) -> None:
    """Benchmark performance across volume scales (1k, 10k, 50k, 100k)."""
    print(f"[*] Running Pipeline Performance Benchmark across scales...")
    scales = [1000, 10000, 50000]
    if args.large:
        scales.append(100000)

    print("\n| Scale (Records) | Generation (s) | Ingestion & Val (s) | Masking & Pub (s) | Total Time (s) | Throughput (rec/s) |")
    print("| :--- | :--- | :--- | :--- | :--- | :--- |")

    app_cfg = load_app_config()
    mask_cfg = load_masking_config()

    for count in scales:
        cust_cnt = max(100, count // 10)
        tx_cnt = count
        gen = SyntheticDataGenerator(seed=42)
        spec = GenerationSpec(num_customers=cust_cnt, num_transactions=tx_cnt, anomaly_rate=0.01)

        t0 = time.perf_counter()
        custs, txs, _ = gen.generate(spec)
        t_gen = round(time.perf_counter() - t0, 3)

        t1 = time.perf_counter()
        runner = PipelineRunner(app_config=app_cfg, masking_config=mask_cfg)
        res = runner.run(customers_input=custs, transactions_input=txs)
        t_pipeline = round(time.perf_counter() - t1, 3)

        total_rec = len(custs) + len(txs)
        rec_per_sec = int(total_rec / t_pipeline) if t_pipeline > 0 else 0

        print(f"| {total_rec:,} | {t_gen:.2f}s | (in pipeline) | (in pipeline) | {t_pipeline:.2f}s | {rec_per_sec:,} |")

    print("\n[+] Benchmark finished.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sensitive Data Masking and Analytical Minimization Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate
    gen_p = subparsers.add_parser("generate", help="Generate synthetic datasets")
    gen_p.add_argument("--customers", type=int, default=100, help="Number of customer records")
    gen_p.add_argument("--transactions", type=int, default=500, help="Number of transaction records")
    gen_p.add_argument("--anomaly-rate", type=float, default=0.05, help="Anomaly injection rate")
    gen_p.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    gen_p.add_argument("--format", choices=["json", "jsonl"], default="json", help="Output format")
    gen_p.add_argument("--output-dir", default="data/input", help="Directory for raw input files")
    gen_p.add_argument("--labels-dir", default="data/sample_labeled", help="Directory for labels")

    # profile
    prof_p = subparsers.add_parser("profile", help="Profile a dataset for sensitive fields")
    prof_p.add_argument("--input-file", required=True, help="Input data file path")
    prof_p.add_argument("--dataset-name", default="dataset", help="Name of dataset")
    prof_p.add_argument("--threshold", type=float, default=0.60, help="Confidence threshold")
    prof_p.add_argument("--markdown-out", help="Output path for Markdown report")
    prof_p.add_argument("--json-out", help="Output path for JSON report")

    # run
    run_p = subparsers.add_parser("run", help="Run the pipeline")
    run_p.add_argument("--config", default="config/pipeline_config.yaml", help="App config path")
    run_p.add_argument("--masking", default="config/masking_rules.yaml", help="Masking rules config path")
    run_p.add_argument("--customers", default="data/input/customers.json", help="Customers input file")
    run_p.add_argument("--transactions", default="data/input/transactions.json", help="Transactions input file")
    run_p.add_argument("--run-id", help="Explicit run ID (optional)")

    # benchmark
    bm_p = subparsers.add_parser("benchmark", help="Run performance benchmarks")
    bm_p.add_argument("--large", action="store_true", help="Include 100,000 record test")

    args = parser.parse_args()
    if args.command == "generate":
        cmd_generate(args)
    elif args.command == "profile":
        cmd_profile(args)
    elif args.command == "run":
        cmd_run(args)
    elif args.command == "benchmark":
        cmd_benchmark(args)


if __name__ == "__main__":
    main()

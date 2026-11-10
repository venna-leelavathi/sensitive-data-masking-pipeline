"""Tests for CLI entry points and argument parsing."""

import sys
from pathlib import Path
from src.cli import main


def test_cli_generate_and_run(tmp_path: Path, monkeypatch):
    out_dir = tmp_path / "input"
    lbl_dir = tmp_path / "labels"

    # Test CLI generate
    gen_args = [
        "src.cli",
        "generate",
        "--customers", "10",
        "--transactions", "25",
        "--output-dir", str(out_dir),
        "--labels-dir", str(lbl_dir),
        "--seed", "99",
    ]
    monkeypatch.setattr(sys, "argv", gen_args)
    main()

    assert (out_dir / "customers.json").exists()
    assert (out_dir / "transactions.json").exists()

    # Test CLI profile
    prof_md = tmp_path / "prof.md"
    prof_args = [
        "src.cli",
        "profile",
        "--input-file", str(out_dir / "customers.json"),
        "--dataset-name", "cust_cli",
        "--markdown-out", str(prof_md),
    ]
    monkeypatch.setattr(sys, "argv", prof_args)
    main()

    assert prof_md.exists()

    # Test CLI run
    run_args = [
        "src.cli",
        "run",
        "--customers", str(out_dir / "customers.json"),
        "--transactions", str(out_dir / "transactions.json"),
    ]
    monkeypatch.setattr(sys, "argv", run_args)
    main()


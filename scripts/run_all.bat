@echo off
setlocal enabledelayedexpansion

echo =====================================================================
echo  SENSITIVE DATA MASKING ^& ANALYTICAL MINIMIZATION PIPELINE
echo  End-to-End Execution Script
echo =====================================================================

set PYTHON_EXE=.venv\Scripts\python.exe
if not exist "%PYTHON_EXE%" (
    echo [!] Virtual environment not found at .venv. Using system python...
    set PYTHON_EXE=python
)

echo.
echo [1/5] Running Automated Test Suite with Coverage...
%PYTHON_EXE% -m pytest -v --cov=src
if %ERRORLEVEL% neq 0 (
    echo [X] Tests failed. Aborting.
    exit /b %ERRORLEVEL%
)

echo.
echo [2/5] Generating Reproducible Synthetic Dataset (seed=42)...
%PYTHON_EXE% -m src.cli generate --customers 100 --transactions 500 --seed 42

echo.
echo [3/5] Profiling Synthetic Datasets for Sensitive Fields (PII/PCI)...
%PYTHON_EXE% -m src.cli profile --input-file data/input/customers.json --dataset-name customers --markdown-out docs/profiling_report_customers.md --json-out data/audit/profiling_customers.json
%PYTHON_EXE% -m src.cli profile --input-file data/input/transactions.json --dataset-name transactions --markdown-out docs/profiling_report_transactions.md --json-out data/audit/profiling_transactions.json

echo.
echo [4/5] Executing Privacy Masking, Validation, and Publishing Pipeline...
%PYTHON_EXE% -m src.cli run

echo.
echo [5/5] Running Performance Benchmark across Volume Scales...
%PYTHON_EXE% -m src.cli benchmark

echo.
echo =====================================================================
echo  PIPELINE EXECUTION COMPLETE!
echo  Published Datasets: data/output/
echo  Quarantine Logs:    data/quarantine/
echo  Audit Trail:        data/audit/
echo  Documentation:      docs/
echo =====================================================================


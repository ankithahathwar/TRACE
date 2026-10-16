# TRACE Benchmark Directory Index & Reproduction Runbook

**Location**: `benchmark_final/`  
**Frozen Commit**: `1ddb2ba1052956b4fbbd3f6a2fbb5df4df5cfab0`  
**Branch**: `security/remediation-and-scan-quality`

---

## Directory Organization

- **`benchmark_final.md`**: Authoritative comprehensive benchmark audit report, repeated measurement distributions, competitor comparisons, and evidence-bounded scorecard.
- **`ground_truth_manifest.json`**: Ground-truth case-level inventory of all 27 verifiable endpoints across local testbeds (`testbed_hardcore`, `test-repository`, `labs/vending-api`).
- **`scripts/`**:
  - `repro_benchmarks.py`: Single-run empirical measurement script across all scopes and targets.
  - `run_repeated_benchmarks.py`: Repeated benchmark suite (1 warm-up + 5 measured runs) measuring wall time, CPU time, memory (`psutil` RSS and `tracemalloc`), and executing Bandit and Semgrep comparisons.
- **`raw/`**:
  - `trace_repeated_benchmarks.json`: Complete statistical distributions (min, max, median, mean, stddev, IQR) for in-process and CLI executions.
  - `comparison_tools_benchmarks.json`: Pinned versions, run times, and finding counts for Bandit and Semgrep.
  - `bandit_testbed_hardcore.json`: Raw Bandit SARIF/JSON finding output on `testbed_hardcore`.
  - `semgrep_testbed_hardcore.json`: Raw Semgrep JSON output on `testbed_hardcore`.
  - `semgrep_testrepo.json`: Raw Semgrep JSON output on `test-repository`.
- **`logs/`**:
  - `cli_testbed_hardcore.log`: Standard output and standard error from TRACE CLI execution.
  - `cli_test_repository.log`: Standard output and standard error from TRACE CLI execution.
  - `cli_root_fixtures.log`: CLI log for fixtures profile.
  - `cli_root_app.log`: CLI log for application profile.
  - `cli_root_full.log`: CLI log for full profile.
  - `bandit_testbed_hardcore.log`: Execution log for Bandit.
  - `semgrep_testbed_hardcore.log`: Execution log for Semgrep.
  - `semgrep_testrepo.log`: Execution log for Semgrep.
- **`environment/`**:
  - `system_env.json`: Full hardware and software environment specification.
  - `pip_freeze.json`: Complete list of installed Python dependencies.
- **`evidence/`**:
  - `empirical_scan_benchmarks.json`: Preserved initial scan measurements.
  - `package_footprint.json`: Packaging and LFS pointer byte calculations.
  - `test_suite_record.json`: Main and Laya test suite results (126 passed, 1 skipped).
  - `git_state.json`: Git commit and status records.

---

## How to Reproduce All Measurements

### 1. Execute Test Suite
```powershell
$env:PYTHONPATH='src'
python -m pytest tests/ -q --ignore=tests/test_laya_training.py
python -m pytest tests/test_laya_training.py::test_laya_training_corpus_generation tests/test_laya_training.py::test_run_intelligence_benchmark -q
```
*Expected Result*: 126 passed, 1 skipped in ~142 seconds total.

### 2. Execute Repeated TRACE Benchmarks & Comparison Tools
```powershell
$env:PYTHONPATH='src'
python benchmark_final/scripts/run_repeated_benchmarks.py
```
*Expected Result*: 1 warm-up + 5 measured runs for in-process engine and CLI across 5 target scopes, plus 5 runs each of Bandit and Semgrep.

### 3. Verify Packaging Footprint
```powershell
npm pack --dry-run
```
*Expected Result*: 219.1 kB tarball, 904.6 kB unpacked, 134 files.

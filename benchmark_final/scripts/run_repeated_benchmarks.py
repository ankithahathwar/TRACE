"""Repeated performance benchmark runner for TRACE and comparison tools.

Performs 1 warm-up + 5 measured runs for both in-process engine and full CLI subprocess.
Calculates statistical distributions (min, max, median, mean, stddev, IQR) and records
memory (RSS and tracemalloc peak), CPU time, and stage breakdowns.
Executes Bandit and Semgrep comparison runs on identical local targets.
"""

import sys
import os
import time
import json
import math
import subprocess
import tracemalloc
from pathlib import Path
import psutil

# Ensure stdout flushes immediately
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE_ROOT / "src"))

from trace_engine.ingest.repository import RepositoryScanner
from trace_engine.scan_scope import resolve_scope, scoped_scanner
from trace_engine.parsing.parser import CodeParser
from trace_engine.framework import get_adapters
from trace_engine.apm.builder import APMBuilder
from trace_engine.security.hypotheses import HypothesisEngine
from trace_engine.findings.correlate import EvidenceCorrelator


def compute_stats(values):
    """Compute summary statistics for a list of float values."""
    if not values:
        return {}
    n = len(values)
    sorted_v = sorted(values)
    v_min = sorted_v[0]
    v_max = sorted_v[-1]
    v_mean = sum(sorted_v) / n
    variance = sum((x - v_mean) ** 2 for x in sorted_v) / (n - 1) if n > 1 else 0.0
    v_stddev = math.sqrt(variance)

    # Median and quartiles
    def percentile(p):
        k = (n - 1) * p
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_v[int(k)]
        d0 = sorted_v[int(f)] * (c - k)
        d1 = sorted_v[int(c)] * (k - f)
        return d0 + d1

    v_median = percentile(0.5)
    v_q1 = percentile(0.25)
    v_q3 = percentile(0.75)
    v_iqr = v_q3 - v_q1

    return {
        "runs": [round(x, 4) for x in values],
        "count": n,
        "min": round(v_min, 4),
        "max": round(v_max, 4),
        "mean": round(v_mean, 4),
        "median": round(v_median, 4),
        "stddev": round(v_stddev, 4),
        "iqr": round(v_iqr, 4),
        "q1": round(v_q1, 4),
        "q3": round(v_q3, 4),
    }


def run_single_in_process(target_path: Path, scope_name: str):
    """Run one pass of the in-process pipeline with detailed instrumentation."""
    process = psutil.Process()
    tracemalloc.start()
    rss_before = process.memory_info().rss
    t_start_wall = time.perf_counter()
    t_start_cpu = time.process_time()

    # 1. Ingestion
    t0 = time.perf_counter()
    scanner, scope_result = scoped_scanner(target_path, scope_name)
    source_files = scanner.scan()
    t_ingest = time.perf_counter() - t0

    # 2. AST parsing & route extraction
    t1 = time.perf_counter()
    parser = CodeParser()
    adapters = get_adapters()
    endpoints = []
    parsed_files = []
    for sf in source_files:
        content = Path(sf.absolute_path).read_text(encoding="utf-8", errors="replace")
        pf = parser.parse(sf.path, content, sf.language, absolute_path=sf.absolute_path)
        parsed_files.append(pf)
        for adapter in adapters:
            if adapter.can_handle(pf):
                eps = adapter.extract_endpoints(pf, content)
                endpoints.extend(eps)
    t_parse = time.perf_counter() - t1

    # 3. APM graph synthesis
    t2 = time.perf_counter()
    builder = APMBuilder(project_name=target_path.name)
    apm = builder.build(target_path, source_files, parsed_files, endpoints)
    t_apm = time.perf_counter() - t2

    # 4. Hypothesis evaluation
    t3 = time.perf_counter()
    hyp_engine = HypothesisEngine()
    hypotheses = hyp_engine.derive_hypotheses(apm, endpoints)
    t_hyp = time.perf_counter() - t3

    # 5. Evidence correlation
    t4 = time.perf_counter()
    correlator = EvidenceCorrelator()
    findings = [f for h in hypotheses for f in [correlator.correlate(h, None, apm)] if f]
    t_corr = time.perf_counter() - t4

    # Bounded paths
    bounded_paths = 0
    for ep in endpoints:
        if ep.id in apm.graph:
            paths = apm.find_paths_from_endpoint(ep.id, max_depth=3)
            bounded_paths += len(paths)

    total_wall_ms = (time.perf_counter() - t_start_wall) * 1000.0
    total_cpu_ms = (time.process_time() - t_start_cpu) * 1000.0
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    rss_after = process.memory_info().rss

    return {
        "files_count": len(source_files),
        "endpoints_count": len(endpoints),
        "nodes_count": apm.graph.number_of_nodes(),
        "edges_count": apm.graph.number_of_edges(),
        "hypotheses_count": len(hypotheses),
        "findings_count": len(findings),
        "bounded_paths_depth3": bounded_paths,
        "wall_time_ms": total_wall_ms,
        "cpu_time_ms": total_cpu_ms,
        "ingest_ms": t_ingest * 1000.0,
        "parse_ms": t_parse * 1000.0,
        "apm_ms": t_apm * 1000.0,
        "hyp_ms": t_hyp * 1000.0,
        "corr_ms": t_corr * 1000.0,
        "tracemalloc_peak_kb": peak_mem / 1024.0,
        "rss_delta_kb": max(0, rss_after - rss_before) / 1024.0,
        "rss_current_mb": rss_after / (1024.0 * 1024.0),
    }


def run_single_cli(target_str: str, scope_str: str):
    """Run one invocation of the CLI scan subprocess in pure offline static mode."""
    cmd = [
        sys.executable,
        "-m",
        "trace_engine.cli",
        "scan",
        target_str,
        "--scope",
        scope_str,
        "--target",
        "http://offline.internal",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    t0_wall = time.perf_counter()
    res = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), capture_output=True, text=True, env=env)
    wall_ms = (time.perf_counter() - t0_wall) * 1000.0

    return {
        "returncode": res.returncode,
        "wall_time_ms": wall_ms,
        "stdout": res.stdout,
        "stderr": res.stderr,
    }


def run_target_suite(target_path: Path, scope_name: str, target_label: str):
    print(f"\n[{target_label}] Starting in-process warm-up + 5 measured runs...")
    # 1 warm-up
    _ = run_single_in_process(target_path, scope_name)

    in_process_runs = []
    for i in range(1, 6):
        res = run_single_in_process(target_path, scope_name)
        in_process_runs.append(res)
        print(f"  In-process run {i}/5: {res['wall_time_ms']:.2f} ms wall, {res['cpu_time_ms']:.2f} ms cpu")

    target_str = str(target_path.relative_to(WORKSPACE_ROOT)) if target_path != WORKSPACE_ROOT else "."
    print(f"[{target_label}] Starting CLI warm-up + 5 measured runs...")
    # 1 warm-up CLI
    _ = run_single_cli(target_str, scope_name)

    cli_runs = []
    last_stdout = ""
    last_stderr = ""
    for i in range(1, 6):
        res = run_single_cli(target_str, scope_name)
        cli_runs.append(res["wall_time_ms"])
        last_stdout = res["stdout"]
        last_stderr = res["stderr"]
        print(f"  CLI run {i}/5: {res['wall_time_ms']:.2f} ms (exit {res['returncode']})")

    # Save log
    log_dir = WORKSPACE_ROOT / "benchmark_final" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"cli_{target_label}.log"
    log_file.write_text(f"STDOUT:\n{last_stdout}\n\nSTDERR:\n{last_stderr}", encoding="utf-8")

    sample = in_process_runs[0]
    return {
        "target": target_str,
        "scope": scope_name,
        "counts": {
            "files": sample["files_count"],
            "endpoints": sample["endpoints_count"],
            "nodes": sample["nodes_count"],
            "edges": sample["edges_count"],
            "hypotheses": sample["hypotheses_count"],
            "findings": sample["findings_count"],
            "bounded_paths_depth3": sample["bounded_paths_depth3"],
        },
        "in_process_wall_time_ms": compute_stats([r["wall_time_ms"] for r in in_process_runs]),
        "in_process_cpu_time_ms": compute_stats([r["cpu_time_ms"] for r in in_process_runs]),
        "stages_ms": {
            "ingest": compute_stats([r["ingest_ms"] for r in in_process_runs]),
            "parse": compute_stats([r["parse_ms"] for r in in_process_runs]),
            "apm": compute_stats([r["apm_ms"] for r in in_process_runs]),
            "hypotheses": compute_stats([r["hyp_ms"] for r in in_process_runs]),
            "correlation": compute_stats([r["corr_ms"] for r in in_process_runs]),
        },
        "memory": {
            "tracemalloc_peak_kb": compute_stats([r["tracemalloc_peak_kb"] for r in in_process_runs]),
            "rss_current_mb": compute_stats([r["rss_current_mb"] for r in in_process_runs]),
        },
        "cli_wall_time_ms": compute_stats(cli_runs),
    }


def run_comparison_tools():
    tools_venv = WORKSPACE_ROOT / ".venv"
    bandit_exe = tools_venv / "Scripts" / "bandit.exe"
    semgrep_exe = tools_venv / "Scripts" / "semgrep.exe"

    raw_dir = WORKSPACE_ROOT / "benchmark_final" / "raw"
    log_dir = WORKSPACE_ROOT / "benchmark_final" / "logs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    results = {}

    # 1. Bandit on testbed_hardcore
    if bandit_exe.exists():
        print("\n[Bandit] Running 1 warm-up + 5 measured runs on testbed_hardcore...")
        # Warmup
        subprocess.run([str(bandit_exe), "-r", "testbed_hardcore", "-f", "json"], capture_output=True, text=True)
        bandit_times = []
        last_json = ""
        for i in range(1, 6):
            t0 = time.perf_counter()
            r = subprocess.run([str(bandit_exe), "-r", "testbed_hardcore", "-f", "json"], capture_output=True, text=True)
            dt = (time.perf_counter() - t0) * 1000.0
            bandit_times.append(dt)
            last_json = r.stdout
            print(f"  Bandit run {i}/5: {dt:.2f} ms")
        (raw_dir / "bandit_testbed_hardcore.json").write_text(last_json, encoding="utf-8")
        (log_dir / "bandit_testbed_hardcore.log").write_text(f"Exit: {r.returncode}\n{r.stderr}", encoding="utf-8")
        parsed = json.loads(last_json) if last_json else {}
        results["bandit_testbed_hardcore"] = {
            "version": "1.9.4",
            "findings_count": len(parsed.get("results", [])),
            "files_scanned": parsed.get("metrics", {}).get("_totals", {}).get("loc", 0),
            "wall_time_ms": compute_stats(bandit_times),
            "findings": [
                {
                    "test_id": x.get("test_id"),
                    "issue_severity": x.get("issue_severity"),
                    "filename": x.get("filename"),
                    "line": x.get("line_number"),
                    "issue_text": x.get("issue_text"),
                }
                for x in parsed.get("results", [])
            ],
        }

    # 2. Semgrep on testbed_hardcore
    if semgrep_exe.exists():
        print("\n[Semgrep] Running 1 warm-up + 5 measured runs on testbed_hardcore...")
        # Warmup
        subprocess.run([str(semgrep_exe), "scan", "--config", "auto", "--json", "testbed_hardcore"], capture_output=True, text=True)
        semgrep_times = []
        last_json = ""
        for i in range(1, 6):
            t0 = time.perf_counter()
            r = subprocess.run([str(semgrep_exe), "scan", "--config", "auto", "--json", "testbed_hardcore"], capture_output=True, text=True)
            dt = (time.perf_counter() - t0) * 1000.0
            semgrep_times.append(dt)
            last_json = r.stdout
            print(f"  Semgrep run {i}/5: {dt:.2f} ms")
        (raw_dir / "semgrep_testbed_hardcore.json").write_text(last_json, encoding="utf-8")
        (log_dir / "semgrep_testbed_hardcore.log").write_text(f"Exit: {r.returncode}\n{r.stderr}", encoding="utf-8")
        parsed = json.loads(last_json) if last_json else {}
        results["semgrep_testbed_hardcore"] = {
            "version": "1.181.0",
            "findings_count": len(parsed.get("results", [])),
            "wall_time_ms": compute_stats(semgrep_times),
            "findings": [
                {
                    "check_id": x.get("check_id"),
                    "severity": x.get("extra", {}).get("severity"),
                    "path": x.get("path"),
                    "line": x.get("start", {}).get("line"),
                    "message": x.get("extra", {}).get("message"),
                }
                for x in parsed.get("results", [])
            ],
        }

        # 3. Semgrep on test-repository
        print("\n[Semgrep] Running 1 warm-up + 5 measured runs on test-repository...")
        subprocess.run([str(semgrep_exe), "scan", "--config", "auto", "--json", "test-repository"], capture_output=True, text=True)
        semgrep_testrepo_times = []
        last_json_repo = ""
        for i in range(1, 6):
            t0 = time.perf_counter()
            r = subprocess.run([str(semgrep_exe), "scan", "--config", "auto", "--json", "test-repository"], capture_output=True, text=True)
            dt = (time.perf_counter() - t0) * 1000.0
            semgrep_testrepo_times.append(dt)
            last_json_repo = r.stdout
            print(f"  Semgrep test-repo run {i}/5: {dt:.2f} ms")
        (raw_dir / "semgrep_testrepo.json").write_text(last_json_repo, encoding="utf-8")
        (log_dir / "semgrep_testrepo.log").write_text(f"Exit: {r.returncode}\n{r.stderr}", encoding="utf-8")
        parsed_repo = json.loads(last_json_repo) if last_json_repo else {}
        results["semgrep_test_repository"] = {
            "version": "1.181.0",
            "findings_count": len(parsed_repo.get("results", [])),
            "wall_time_ms": compute_stats(semgrep_testrepo_times),
        }

    return results


def main():
    raw_dir = WORKSPACE_ROOT / "benchmark_final" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    benchmark_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "targets": {},
    }

    # Target 1: testbed_hardcore
    tb_path = WORKSPACE_ROOT / "testbed_hardcore"
    if tb_path.exists():
        benchmark_data["targets"]["testbed_hardcore"] = run_target_suite(tb_path, "full", "testbed_hardcore")

    # Target 2: test-repository
    tr_path = WORKSPACE_ROOT / "test-repository"
    if tr_path.exists():
        benchmark_data["targets"]["test_repository"] = run_target_suite(tr_path, "full", "test_repository")

    # Target 3: Repo root with fixtures profile
    benchmark_data["targets"]["root_fixtures"] = run_target_suite(WORKSPACE_ROOT, "fixtures", "root_fixtures")

    # Target 4: Repo root with app profile
    benchmark_data["targets"]["root_app"] = run_target_suite(WORKSPACE_ROOT, "app", "root_app")

    # Target 5: Repo root with full profile
    benchmark_data["targets"]["root_full"] = run_target_suite(WORKSPACE_ROOT, "full", "root_full")

    # Save TRACE repeated benchmarks
    out_file = raw_dir / "trace_repeated_benchmarks.json"
    out_file.write_text(json.dumps(benchmark_data, indent=2), encoding="utf-8")
    print(f"\nTRACE repeated benchmark data saved to {out_file}")

    # Run comparison tools
    comp_results = run_comparison_tools()
    comp_file = raw_dir / "comparison_tools_benchmarks.json"
    comp_file.write_text(json.dumps(comp_results, indent=2), encoding="utf-8")
    print(f"Comparison tools benchmark data saved to {comp_file}")


if __name__ == "__main__":
    main()

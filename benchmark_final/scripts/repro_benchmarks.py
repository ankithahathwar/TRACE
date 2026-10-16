"""Comprehensive benchmark reproduction script for TRACE.

Measures scanner performance, graph construction, endpoint discovery,
hypotheses derivation, and findings across available targets and scopes.
Outputs raw results to benchmark_final/evidence/.
"""

import sys
import os
import time
import json
import platform
import subprocess
from pathlib import Path

# Add src to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WORKSPACE_ROOT / "src"))

from trace_engine.ingest.repository import RepositoryScanner
from trace_engine.scan_scope import resolve_scope, scoped_scanner
from trace_engine.parsing.parser import CodeParser
from trace_engine.framework import get_adapters
from trace_engine.apm.builder import APMBuilder
from trace_engine.security.hypotheses import HypothesisEngine
from trace_engine.findings.correlate import EvidenceCorrelator


def get_env_metadata():
    import torch
    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": sys.version,
        "torch_version": torch.__version__,
        "torch_cuda_available": torch.cuda.is_available(),
        "workspace_root": str(WORKSPACE_ROOT),
    }


def measure_target_scan(target_path: Path, scope_name: str = "full"):
    start_wall = time.perf_counter()

    # Ingestion & file scanning with resolved scope
    t0 = time.perf_counter()
    scanner, scope_result = scoped_scanner(target_path, scope_name)
    source_files = scanner.scan()
    t_ingest = time.perf_counter() - t0

    # AST parsing & Route extraction
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

    # APM Graph Synthesis
    t2 = time.perf_counter()
    builder = APMBuilder(project_name=target_path.name)
    apm = builder.build(target_path, source_files, parsed_files, endpoints)
    t_apm = time.perf_counter() - t2

    # Hypothesis Engine
    t3 = time.perf_counter()
    hyp_engine = HypothesisEngine()
    hypotheses = hyp_engine.derive_hypotheses(apm, endpoints)
    t_hyp = time.perf_counter() - t3

    # Evidence Correlation
    t4 = time.perf_counter()
    correlator = EvidenceCorrelator()
    findings = [f for h in hypotheses for f in [correlator.correlate(h, None, apm)] if f]
    t_corr = time.perf_counter() - t4

    # Bounded paths calculation (depth <= 3)
    bounded_paths = 0
    for ep in endpoints:
        ep_id = ep.id
        if ep_id in apm.graph:
            paths = apm.find_paths_from_endpoint(ep_id, max_depth=3)
            bounded_paths += len(paths)

    total_wall = time.perf_counter() - start_wall

    severities = {}
    categories = {}
    for f in findings:
        sev = f.severity.value
        severities[sev] = severities.get(sev, 0) + 1
        cat = f.category.value if hasattr(f.category, "value") else str(f.category)
        categories[cat] = categories.get(cat, 0) + 1

    return {
        "target": str(target_path.relative_to(WORKSPACE_ROOT)) if target_path != WORKSPACE_ROOT else ".",
        "scope": scope_name,
        "files_count": len(source_files),
        "endpoints_count": len(endpoints),
        "nodes_count": apm.graph.number_of_nodes(),
        "edges_count": apm.graph.number_of_edges(),
        "hypotheses_count": len(hypotheses),
        "findings_count": len(findings),
        "bounded_paths_depth3": bounded_paths,
        "severities": severities,
        "categories": categories,
        "latencies_ms": {
            "ingest_ms": round(t_ingest * 1000, 2),
            "parse_and_extract_ms": round(t_parse * 1000, 2),
            "apm_synthesis_ms": round(t_apm * 1000, 2),
            "hypotheses_ms": round(t_hyp * 1000, 2),
            "correlation_ms": round(t_corr * 1000, 2),
            "total_wall_ms": round(total_wall * 1000, 2),
        },
    }


def main():
    evidence_dir = WORKSPACE_ROOT / "benchmark_final" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "environment": get_env_metadata(),
        "scans": {},
    }

    # 1. Self scan with full scope
    print("Running self-scan (full scope)...")
    results["scans"]["self_full"] = measure_target_scan(WORKSPACE_ROOT, "full")

    # 2. Self scan with app scope
    print("Running self-scan (app scope)...")
    results["scans"]["self_app"] = measure_target_scan(WORKSPACE_ROOT, "app")

    # 3. Self scan with fixtures scope
    print("Running self-scan (fixtures scope)...")
    results["scans"]["self_fixtures"] = measure_target_scan(WORKSPACE_ROOT, "fixtures")

    # 4. test-repository with full scope
    testrepo_path = WORKSPACE_ROOT / "test-repository"
    if testrepo_path.exists():
        print("Running test-repository scan (full scope)...")
        results["scans"]["testrepo_full"] = measure_target_scan(testrepo_path, "full")

    # 5. testbed_hardcore with full scope
    testbed_path = WORKSPACE_ROOT / "testbed_hardcore"
    if testbed_path.exists():
        print("Running testbed_hardcore scan (full scope)...")
        results["scans"]["testbed_hardcore_full"] = measure_target_scan(testbed_path, "full")

    out_file = evidence_dir / "empirical_scan_benchmarks.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results saved to {out_file}")
    print(json.dumps(results["scans"], indent=2))


if __name__ == "__main__":
    main()

# CLAIMS VERIFICATION — Graph Metrics, Models, Timing, Benchmarks, Docs

Method: each claim lists exact wording/location, supporting code, dataset/target, command +
environment, observed result, verdict (**Verified / Partially verified / Unsupported /
Contradicted / Not tested / Blocked**). Nothing was re-measured by invention: weights are
absent (`models/*` holds tokenizers/metadata only), `benchmark.md` and the PPT do not exist
in-repo (globs empty), `D:\Startup\TDC-Main` and `D:\Startup\Onecrew` are unavailable here.

## 1. Graph metrics (reproduced on this machine, win32 py3.11.9)
| Claim | Evidence | Result | Verdict |
|---|---|---|---|
| "188 files indexed" (self-scan) | `ingest/repository.py` + root scan | **188** reproduced exactly | Verified |
| "38 API routes" | `framework/*` adapters + root scan | **38** reproduced exactly | Verified |
| "790 APM graph nodes" | `apm/builder.py` + `apm/model.py` | **790** reproduced exactly | Verified |
| "815 directed attack paths" | `apm/model.py:50-90` | 815 = **edge count** (`summary()` edges); bounded endpoint DFS (`max_depth=3`) yields **72 total paths on baseline composition, 65 on corrected composition** (re-verified; delta follows endpoint changes, not traversal logic); per-endpoint `find_paths_to_sinks` (cutoff 5) is the only sink-directed enumeration and was never totaled in any report | **Contradicted** (edges mislabeled as paths) |
| Nodes/edges after fix (`full`) | Same code path | **872/893** (file set grew: `scan_scope.py` + 5 test files + 3 verification-added V2 tests; re-verified after the port-0/scope fixes, which add no graph nodes beyond test functions) | Verified (new baseline) |
| Score 0/100 | `harness/engine.py:45-50` | 100−(3·20+25·10+12·3)→0 reproduced; corrected 28 findings still score 0 | Verified (arithmetic, not exploit proof) |
| test-repository "28 nodes, 21 edges" (`TRACE_Benchmark_and_Audit_Metrics.md` §3) | Per-fixture scan | Observed **59 nodes / 64 edges** for 16 files / 7 endpoints | **Contradicted** as stated (likely an older builder version or a subgraph; 7 endpoints match) |
| test-repository "15 files" | Same | 16 source files on disk now (drift) | Partially verified (off by drift) |

## 2. Model, latency and accuracy claims
| Claim | Evidence | Result | Verdict |
|---|---|---|---|
| "SecureBERT/ModernBERT: 38 inferences, 586 ms avg" | `cli.py:604-609` (`avg_lat*0.6` derived split, not per-model profiling); weights absent | Cannot execute neural path; fallback keyword scoring active | Unsupported here |
| "Laya: 38 inferences, 390 ms avg" | `cli.py:610-615` (`avg_lat*0.4`) | Same as above | Unsupported here |
| Laya "8.39 ms GPU / 20.18 ms ONNX", "88.6% Top-1 / 97.1% compound", SecureBERT "20.32 ms / 22.9%" (Benchmark Metrics doc §2) | `laya_metadata.json` (1265 train/195 val, prio 86.7/testpack 84.6, 7 epochs), `training_metadata.json` (peak F1 0.658, 5 ep), `training/*`, `evaluation.py` | Metadata consistent with small-scale training; no weights, no GPU (torch cpu-only here), no rerun | Unsupported here (metadata only; provenance from filenames insufficient) |
| "96.4% precision / 88.2% recall / <3.6% FPR", "100% BOLA/IDOR" | `benchmarks/runner.py` (needs `benchmarks/owasp-python`, staged-deleted), hardcore tests | Heuristic FPs demonstrated (search-SQLi, preview-SSTI, synthetic endpoints); suite has no whole-repo ground truth | Unsupported here |
| "0.26 s scan / 15.79 ms micro-audit" (`docs/BENCHMARKS.md`) | No timing harness in repo for root scans | Measured datapoint this machine: root scan ≈ **2.71 s wall** (interpreter start included; different HW) | Not verified (env-specific; single datapoint, not a refutation) |
| "0.94 s AI analysis / 83 endpoints / 1202 nodes" (TDC-Main) | External path, unavailable | — | Blocked |
| Footprints (205.8 kB tarball, 1.83 MB core, <300 MB RAM, ~990 MB weights) | `package.json`, `pyproject.toml`, downloader `min_size` (498 MB + 267 MB) | No packaging/RAM measurement run | Not tested |

## 3. Testbed / benchmark-target claims
| Claim | Evidence | Result | Verdict |
|---|---|---|---|
| test-repository 7 endpoints | Fixture scan | 5 Dart + 2 Kotlin reproduced | Verified |
| "11 hypotheses, 11 findings, 11/11 (100%) CONFIRMED" at `127.0.0.1:18082` | `test-repository/server.py` + testpacks, run here loopback-only | 6/6 sampled oracles confirm (BOLA, BFLA, SSRF, mass-assignment, AUTH×2; conf 0.90–0.98); full 11/11 not re-run (server covers the same routes; SSTI was never a server route) | Partially verified (sample confirms oracle-fixture agreement; SSTI row was miscategorized) |
| pytest "23/23, 8.05 s" (Metrics doc §5) | `tests/` on this machine | Now **123 passed, 1 skipped** across all files (121 in the main run incl. scope/edge tests, +2 laya-training singles from the prior run; laya benchmark test alone takes 305 s here) | Partially verified (superset passes; old counts stale) |
| CLI repro commands (`trace.bat test-all …`, `replay …`) | `cli.py` commands exist | `test`/`scan`/`test-all`/`replay`/`explain` present; `--scope` added (default `full`); `--scope bogus` cleanly rejected (`BadParameter`, verified); MCP `scope` verified incl. `fixtures`-on-fixture fallback (7 eps/8 findings on `test-repository`), unknown-scope error dict, out-of-scope-target `refused` with zero fetches | Verified (interfaces + behaviors), timings not re-run |

## 4. Documentation corrections needed (user-facing, after this evidence)
1. Relabel "815 attack paths" → "815 attack-path edges (72 bounded endpoint paths at depth ≤3 on baseline composition, 65 corrected;
   sink-directed paths enumerated per endpoint, cutoff 5)". Touches `README.md`, `docs/BENCHMARKS.md`,
   any PPT source slides repeating the figure.
2. Present 586/390 ms as what they are (proportional splits of one measured average in
   `cli.py:586-617`) or replace with per-model profiling on named hardware; do not present
   fallback-heuristic runs as neural latencies.
3. Qualify test-repository 11/11: runtime agreement of co-designed oracles/fixtures; remove the
   SSTI row or reclassify it as SSRF (the actual sink).
4. Update graph figures for test-repository (59 nodes/64 edges on current builder) or pin the
   builder version the old figures refer to.
5. Mark accuracy/FPR/100%-BOLA as benchmark-harness results with dataset, split and command —
   or drop them until `benchmarks/owasp-python` + weights + blind eval are runnable.
6. State scan scope on every report (now automatic via the Scope section + `scan_scope` payload):
   self (`app`, 0 findings), fixtures (28), full reproduction.
7. `benchmark.md` / PPT have no in-repo sources — add them or stop referencing them; do not
   re-point claims at doc files that were never measured.

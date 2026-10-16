# BENCHMARK CLAIM AUDIT — `docs/BENCHMARKS.md` (frozen at `b25af40`, audited at `1ddb2ba`)

Scope: every numerical/performance/accuracy/cost/dataset/model/comparative claim in
`docs/BENCHMARKS.md` (186 lines, last modified in `b25af40` itself — unmodified by remediation).
`docs/BENCHMARKS.md` was NOT edited; corrections below are proposals awaiting review.
Cross-checked companion: `docs/TRACE_Benchmark_and_Audit_Metrics.md` (149 lines), which
disagrees with `BENCHMARKS.md` on several figures — flagged inline.

Status key: **Verified** (reproduced/measured here) · **Partially verified** (mechanism exists,
exact figure not reproduced) · **Unsupported** (no evidence runnable here) · **Misleading**
(wording overstates or contradicts evidence) · **Blocked** (target/data unavailable).

Source states — original commit `b25af40` (audited docs, stale stored scan); tested working
tree == frozen commit `1ddb2ba` (content identity verified: `git diff HEAD --name-only` shows
only the 6 pre-existing deletions, so all test/scan evidence collected on the tree applies
exactly to `1ddb2ba`; benchmark runs predate both and are NOT attributed to either).

## 1. Claim table (`docs/BENCHMARKS.md` §1 — summary + Key Metrics)

| # | Exact claim (location) | Definition / denominator | Evidence found | Status | Proposed correction |
|---|---|---|---|---|---|
| 1.1 | "eliminates LLM generative inference lag entirely during scanning" (§1 prose) | Default scan path makes no LLM calls | Verified by absence: `TestPlanner` constructed (`orchestrator.py:39`) but `llm_planner.*` has zero call sites; `OllamaProvider` used only by `trace doctor` probe and opt-in planner (loopback). No tokens/cost possible in default path | Partially verified (code, not measured) | Qualify: "in default scan configuration; optional Ollama features excluded" |
| 1.2 | "LLM-based scanners take 30–120+ s, tens of thousands of tokens" (§1) | Unspecified tools/targets | No competitor runs anywhere in repo (only match: "SonarQube" in a SARIF docstring) | Unsupported (unfair comparison: no versions, targets, scope) | Drop or cite an external, dated source |
| 1.3 | "pure compiled native speeds … Tree-sitter … SQLite … quantized neural inference" (§1) | Architecture | Tree-sitter ✓, SQLite persistence ✓ (`apm/serialization.py`), ONNX runtime path ✓ — but no quantization code found (ONNX export ≠ quantization evidence) | Misleading wording | "ONNX-optimized" instead of "quantized" unless quantization is shown |
| 1.4 | "End-to-End Scan Time (189 files): 0.261 s" (§1 table) | Unknown command/env/HW | No script prints the 6-stage table (searched stage labels/timings); only per-model timers exist (`evaluation.py`, `orchestrator.py:552`). Own datapoint: repo-root scan ≈2.71 s wall (different HW/scope) | Unsupported | Publish command + HW + scope, or mark illustrative |
| 1.5 | "Micro-Audit 0.016 s" (§1) | Same | Same gap as 1.4 | Unsupported | Same |
| 1.6 | "$0.00 (100% Offline Edge Execution)" (§1) | Default scan | Scan path verified offline-capable (1.1); BUT updater (`updater.py`), model downloader (`downloader.py`), MoreFixes pipeline and live testpacks use the network when invoked/online | Misleading as blanket | "No per-scan model/API spend in default static mode; updates, model downloads and live probes use the network" |
| 1.7 | "0 Tokens" (§1) | Default scan | Same basis as 1.1 | Partially verified | Same qualifier as 1.1 |
| 1.8 | "NPM Download Size 205.8 kB" (§1, §4, §8 "205 kB") | `trace-sec` tarball | Measured here, offline: `npm pack --dry-run` → **219.1 kB** (134 files), unpacked 904.6 kB | Partially verified (same order; +6.5% drift, re-measure on release) | Update to measured value + method |
| 1.9 | "Disk Footprint 1.83 MB / 1.8 MB core" (§1, §4, §8) | Global install | Unpacked tarball measured 904.6 kB; 1.83 MB not reproduced (likely older layout) | Partially verified (sub-2 MB class holds) | Re-measure or soften to "<2 MB class" |
| 1.10 | "Neural Weights 990.67 MB" (§1) vs "TOTAL 992.50 MB" (§4 box) | LFS artifacts | Git-LFS pointers (blobs absent): safetensors 498,637,432 B (498.64 MB), laya `.pt` 267,874,026 B, `.onnx` 267,968,870 B → **actual total 1,034.48 MB**; SecureBERT 498.64 vs claimed 478.97; Laya pt+onnx 535.84 vs claimed 511.70. Table total 992.50 = 990.67+1.83 (core double-counted into a "weights+core" box while prose says "both models") | Misleading / contradicted | Publish per-artifact sizes from LFS + method (MB vs MiB); fix 990.67-vs-992.50 labeling |
| 1.11 | "False Positive Rate < 3.6%" (§1, §6, §8) | Undefined (no TP/FP/TN/denominator anywhere) | No ground-truth run in repo; OWASP harness (`benchmark/owasp.py`, proper TP/FP/TN/FN) exists but `benchmarks/owasp-python/` data is absent (staged-deleted gitlink). Demonstrated heuristic FPs (search-SQLi, preview-SSTI, synthetic endpoints) contradict generalizability | Unsupported | Remove until OWASP run with published TP/FP/TN/FN; never conflate with precision |
| 1.12 | "96.4% Precision / 88.2% Recall" (§1) vs "∼65/∼70" (§1) vs "∼62/∼71" (§6) | Undefined | No script outputs these; industry figures shift between sections with no source; no competitor runs | Unsupported + internally inconsistent | Remove or source both sides with dated runs |
| 1.13 | "F1 0.921" (§6; arithmetic 2·.964·.882/(.964+.882)=0.9216 ✓) | Derived | Internally consistent but grounded on unsupported inputs (1.12) | Unsupported (inherits 1.12) | Same as 1.12 |

## 2. Onecrew production benchmark (§2: 189 files / 39 eps / 36 hyps / 36 findings + 6-stage 260.76 ms table)

Target `D:\Startup\Onecrew` does not exist here (**Blocked**). Internal checks only:
counts are mutually consistent; stage percentages sum to 100.1 (rounding); the six stage
labels match the real pipeline phases, but **no code prints this table** and the exact
189-file count equals this repo's own original self-scan file count (188–194 across runs) —
a reader cannot tell whether Onecrew and the self-scan are distinct measurements.
Status: **Unsupported** (blocked target, no generating script, no raw log).
Correction: publish the exact command, commit, HW, and raw log; confirm Onecrew ≠ self-scan.

## 3. Micro-audit `testbed_hardcore` (§3: 15 endpoints, "12 high-severity", 15.79 ms table)

Reproduced on frozen code (standalone target): **6 files, 10 endpoints, 8 hypotheses
(7 HIGH + 1 MEDIUM)** — 15 endpoints / 12 highs reflect the pre-dedupe adapter (5 synthetic
endpoints). The 15.79 ms stage table has no generating script. Status: endpoint/high counts
**contradicted on current code** (stale snapshot at best); timings **unsupported**.
Correction: re-run on current code and publish raw output, or version-pin the claim.

## 4. Storage (§4) and inference latencies (§5)

- §4 box: see 1.8–1.10. "Zero-Dependency Core" is misleading wording: `pyproject.toml`
  lists 10 runtime deps (typer, rich, pydantic, networkx, httpx, …) — it means "no neural
  weights", not zero dependencies. Correction: "model-free core".
- §5 latencies (Laya GPU ~4.8 ms, ONNX ~11.2 ms, SecureBERT ~16.4 ms, ensemble ~24.1 ms)
  **directly contradict** the Metrics doc §2 (8.39 / 20.18 / 20.32 / 15.23 ms for the same
  named engines). Neither is reproducible here (no weights, CPU-only torch). The measuring
  harness exists (`evaluation.py:695-759`, per-endpoint `perf_counter`, 35 hand-labeled inline
  snippets) and runs (suite passes), but its labels are author-written, so it measures
  heuristic-vs-label agreement, not independent accuracy. Status: **contradicted between docs,
  otherwise unsupported**. Correction: one hardware-pinned table with weights version, or drop.

## 5. Datasets, training, convergence (§6)

- MoreFixes "2.8 GB raw / 14,533 verified CVE diffs / 10 CWE / 471 topologies": the numbers
  are used consistently across `train_all.py` headers, `interactive.py` prints and
  `laya_metadata.json` arithmetic (276 + 195 = 471 base; 276 + 989 mined = 1265 train) — but
  `.trace/datasets/morefixes/` is absent, Zenodo 20776007 is referenced not vendored, no
  license/manifest file was found, and sibling figures in-code say "43,357 unique CVEs" and
  "52k patches parsed". Status: **internally consistent narrative, externally unverifiable**.
  Correction: publish manifest hashes + license + extraction command.
- Convergence table: SecureBERT row ("Epoch 4/7", val loss 0.1504, exact 74.0%, hamming 96.6%)
  matches **neither** artifact — `training_history.json` (4 epochs: exact 69.8/71.0/73.2/72.9,
  hamming 96.2/96.1/96.5/96.4) peaks at exact 73.2, not 74.0; only the val-loss figure
  (0.1504 at epoch 4) matches, while `training_metadata.json` (5 epochs) ends at exact
  65.6/hamming 96.56/F1 0.658. Laya row matches `laya_metadata.json` (1.0563, 84.6, 0.795)
  except "Epoch 7/11" (`epochs_trained: 7`; "/11" unexplained; trainer default is 6 + early
  stopping). Status: **partially verified with inconsistencies**. Correction: one table, one
  artifact, explain "/7" and "/11".
- Triangulation requirements (§6 prose): static reachability ✓ (APM exists) + runtime oracle ✓
  (testpacks exist) as a *design*, but "path reachability … to sink" overstates heuristic
  edges (815 edges were mislabeled "attack paths" — see claims doc). Status: **partially
  verified (mechanisms) / misleading (guarantee wording)**.

## 6. Head-to-head §7 and summary §8

Every comparative cell (Snyk/Sonar 30–120 s, Semgrep 5–20 s, LLM 45–180 s, costs, token counts,
"code uploaded to cloud", storage figures, "hallucinates code") has **zero runs, versions,
targets, or dates** behind it. "LLM Agents Alone … Native [bridge]" vs "Native MCP + Skills"
is a category error, not a measurement. Status: **unsupported throughout; several cells
unfair by construction**. Correction: replace with a dated, same-target, same-scope
evaluation or label the table "illustrative positioning (not measured)".
§8 inherits all of the above; v2.1.18 is the only fully verified line (`pyproject.toml`).

## 7. Scanner-scope caveats (confirmed against frozen `1ddb2ba` + raw JSON in `.trace/verification/`)

- Root `app`: 142 files, **0 endpoints, 0 findings** (`scan_self_app.json`). A zero-finding
  scan with zero recognized endpoints is **not** evidence of application security or accuracy.
- Root `fixtures`: 50 files, 38 endpoints, **28 findings** (`scan_self_fixtures.json`).
- Root `full`: 194 files, 38 endpoints (0 unregistered), 872 nodes, 893 edges, **65 bounded
  endpoint paths (depth ≤3)**, **28 findings** (CORS 11 / AUTH 10 / BFLA 4 / INJ 2 / BOLA 1).
- `test-repository`: 16 files, **7 endpoints, 59 nodes, 64 edges**, 8 hyps / 8 static findings,
  13 bounded paths (`scan_testrepo_full.json`) — contradicts the Metrics doc's "28 nodes,
  21 edges".
- The 28 retained findings are fixture/test detections or unresolved leads (28-row table in
  the evidence summary); **none is a TRACE application vulnerability**.

## 8. Reproduction commands (genuinely reproducible on frozen code)

```powershell
$env:PYTHONPATH='src'
python -m pytest tests/ -q --ignore=tests/test_laya_training.py        # 124 passed, 1 skipped
python -m pytest tests/test_laya_training.py::test_laya_training_corpus_generation -q
python -m pytest tests/test_laya_training.py::test_run_intelligence_benchmark -q
python .trace/baseline/repro_scan.py                                     # 188/38/790/815 on b25af40 code path
npm pack --dry-run                                                       # 219.1 kB measured here
git show HEAD:models/securebert-finetuned/model.safetensors | head      # LFS pointer: size 498637432
python -m trace_engine.cli scan --help                                   # --scope documented
```

## 9. Missing evidence (blockers for any stronger claim)

LFS weight blobs; `benchmarks/owasp-python/` data (gitlink staged-deleted); Onecrew/TDC-Main
targets; any competitor run (versions/targets/logs); raw logs for 260.76/15.79 ms tables;
TP/FP/FN/TN + ground-truth labels behind <3.6%/96.4%/88.2%; dataset manifest/license/raw
archive; per-artifact weighing method; training predictions/checkpoints; GPU/HW specs.

## 10. Evidence-bounded summary (what TRACE can responsibly claim today)

Sub-second-class static pipeline exists (timing HW-dependent; own datapoint 2.71 s wall for
a 194-file root scan on this machine); default scans make no LLM calls and spend no API
budget (network used only by updater/downloads/live probes); package is sub-MB unpacked
(~0.9 MB measured); 38-route/790-node-scale graph construction reproduced exactly;
fixture oracles agree 6/6 with co-designed fixtures; OWASP harness code exists but is
unrunnable without data. Everything else — global accuracy, FPR, SOTA comparisons,
per-model millisecond tables, dataset-scale training proof — awaits the missing evidence.

## 11. Source-state statement

Original commit `b25af40`; tested working tree == frozen commit
`1ddb2ba1052956b4fbbd3f6a2fbb5df4df5cfab0` (verified: `git diff HEAD --name-only` shows only
the 6 pre-existing deletions, so all test/scan evidence applies exactly to `1ddb2ba`).
Benchmark runs quoted in `docs/BENCHMARKS.md` predate both and are **not** attributed to
either commit. Backup: `.trace/verification/freeze/` (patch SHA256
`F3F6B65742071D5C4E0CF8755449888F969EB3CA225ABCD3905BCDE6412793B8`, 14 untracked files,
tested-state hashes). Staged deletions and audit drafts were excluded from the commit and
remain untouched in the tree.

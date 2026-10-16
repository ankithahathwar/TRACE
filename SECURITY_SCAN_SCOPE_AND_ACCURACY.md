# SCAN SCOPE, ROUTE EXTRACTION & ACCURACY — Design, Corrections, Evidence

## 1. Why the self-scan mixed implementation with fixtures
`RepositoryScanner` scans the process working directory with only `.traceignore` + built-in
ignores; labs, test repositories, testbeds and unit tests are ordinary source dirs, so the
original full scan (188 files) legitimately inventoried 38 endpoints from
`labs/` (9), `test-repository/` (7), `testbed_hardcore/` (15) and `tests/` (7), while TRACE
`src/` itself contributes **0 endpoints**. The 40 stored findings were therefore always
fixture/test detections — never TRACE vulnerabilities. Verified, not assumed (§5 of nursing
repro: per-fixture scans + `src/`-only scan with 0 endpoints).

## 2. Scope policy (`src/trace_engine/scan_scope.py`, new)
Explicit profiles, generic directory patterns (usable for any repo), nothing silent:
- `full` (default): byte-identical to the original scan. Preserves every existing workflow.
- `app`: excludes `FIXTURE_DIR_PATTERNS` (labs, test(s), fixtures, benchmarks, e2e, examples,
  `testbed*`, …). Reports each excluded top-level dir with its reason.
- `fixtures`: scans *only* those dirs (benchmark reproduction).
`.traceignore` is honored in all profiles; `resolve_scope()` reports included/excluded dirs;
`scoped_scanner()` wires the result into `RepositoryScanner(exclude_patterns, only_top_dirs)`
(new optional parameters; default behavior unchanged). CLI `--scope` on `test`, `scan`,
`test-all`/`audit`; MCP `trace_scan` accepts optional `scope`; `test_all_report.json` and
`trace_scan` responses carry a `scan_scope` block; Markdown reports gained an optional
Scan Scope section (`output/markdown.py`, backward-compatible default).

Differentiated reports: `trace scan --scope app` (TRACE implementation assessment),
`--scope fixtures` (benchmark detections), `--scope full` (original reproduction).
A fixture finding is now labeled by scope instead of masquerading as a product finding;
users who want test code analyzed choose `full`/`fixtures` (no global test exclusion exists).

Verification corrections (independent audit): if a `fixtures`-profile target has no
fixture-named top-level dirs (e.g. scanning `test-repository` directly), the profile scans
the whole target with an explanatory `note` instead of returning a misleading empty scan
(`test-repository` + `scope=fixtures` via MCP: 7 endpoints, 8 static findings, verified).
Unknown profiles no longer traceback: MCP returns `{"status":"error",...}` and the CLI
rejects with `BadParameter`. Out-of-scope MCP targets return `refused` with zero fetches
(mock-verified). Markdown Scope sections verified present (and absent by default).

## 3. Corrected counts (same machine, repo root, static-only)
| Profile | Files | Endpoints | Nodes | Edges | Hyps | Findings |
|---|---|---|---|---|---|---|
| Baseline stored report | 188 | 38 | 790 | 815 | (42 live) | 40 (stale: predates priv-esc rule) |
| Live baseline code (pristine worktree, new files excluded) | 189* | 38 | — | — | 42 | 42 |
| Corrected `full` | 194 | 38 | 872 | 893 | — | **28** |
| Corrected `app` | 142 | 0 | 545 | 544 | 0 | **0** |
| Corrected `fixtures` | 50 | 38 | 324 | 345 | — | 28 |
(Node/edge drift 869/890 → 872/893 is test-code growth: 3 added V2 regression tests mean
3 more function nodes/edges. Independent re-verification confirms current values.)
\* 189 = 188 + `src/trace_engine/scan_scope.py` counted? No — live-baseline run excluded new files
from parsing but not from the file count; the +1 is the new test/source files present on disk.
194 = 188 + `scan_scope.py` + 5 new test files. 142 + 50 = 192; the remaining 2 are `.agents/*.json`
(top part starts with `.`, outside fixtures-only selection, inside `full`/`app`).

Per-difference attribution (live-baseline 42 → corrected 28, −14):
- −4: synthetic Django endpoints (`/api/analytics-metric-query`, `/api/tenant-vault-secret-entry`,
  `/api/webhook-integration-dispatch`, `/api/system-vacuum-cleanup`) removed by the registration
  gate + same-file dedupe (`framework/django.py`).
- −4: test-string BOLA (`tests/test_django_adapter.py`, `tests/test_trace.py`) removed by the
  evidence-based `database_access` gate (no handler body → uncertainty, not proof).
- −1: `GET /api/search` INJECTION FP removed by the SQL-construction sink gate.
- −1: `POST .../webhooks/preview` SSTI FP removed by the template-sink gate.
- −7/+1 BFLA: file-wide `admin` role contamination no longer suffices (needs path or
  handler/basename evidence) — orgs, preview, billing, profile, dart-auth BFLAs gone, plus the
  `/admin/users/role` priv-esc duplicate; bare-`role`-substring escalation tightened to
  assignment evidence. Net BFLA 11 → 4.
- +2: real routes newly covered — `POST /api/v1/analytics/query` AUTH (method fix GET→POST),
  `POST /api/v1/system/maintenance/vacuum` AUTH (method fix), `POST /api/v1/go/query`
  INJECTION (Sprintf sink; was AUTH-only).
- Unchanged: CORS 11 (documented lead-noise), labs refund/users/fetch-url/search-AUTH,
  Kotlin records, tenant-vault BOLA, patients AUTH, Go vault AUTH, test-string `/admin/export`
  BFLA (path evidence) + 2 CORS leads.
Endpoint total stays 38 by coincidence (−5 synthetic −4 test-string-BOLA… vs +5 new-test-file
string endpoints + method-split changes); the composition is fully listed in the nursing log.

## 4. Route-extraction corrections (`framework/*`, `findings` flow)
- `Endpoint` gains `registered: bool = True`, `confidence: str = "high"` (`base.py`).
- Django: URL-pattern endpoints keep `registered=True`; method corrected from same-file
  `@api_view` declarations (fixes `analytics_metric_query` POST and `system_vacuum_cleanup`
  POST); name-guessed methods marked `confidence="medium"`; `database_access` from the
  referenced handler's own body (uncertainty → `False`); view-derived entries marked
  `registered=False, confidence="low"` and dropped when their handler is URL-referenced.
- FastAPI regex fallback: `database_access=False`, `confidence="low"` (was unconditional `True`).
- `HypothesisEngine` skips `registered=False` endpoints (inventory stays in the APM graph).
- Fixtures added: real vs unregistered vs duplicate routes, method inference right/wrong,
  db-evidence default (`tests/test_route_extraction.py`, 5 tests).

## 5. Vulnerability-rule corrections (`security/hypotheses.py`)
- INJECTION: route words + `has_unsafe_sql_construction()` (f-string/`Sprintf`/`.format()`/
  `+`-concat/`%`-format SELECT); parameterized `%s` usage is evidence *against*.
- SSTI: route/param trigger + `has_template_sink()` (jinja2/mako/`render_template`/`Template(`…);
  SSRF fetch evidence never counts as SSTI.
- BFLA: `admin` path, or admin role *plus* handler/basename evidence (absolute workspace paths
  excluded from evidence — base name only); role-escalation needs a role parameter or
  role-field assignment (`role[:=]`, `is_admin`, …), not a bare substring.
- Positive controls kept green: labs refund/users, tenant-vault BOLA, analytics + Go injections,
  unsafe-template SSTI, admin-path BFLA (`tests/test_hypothesis_rules.py`, 13 tests incl.
  safe parameterized-query, sink-less search/preview, role-only negatives).

## 6. Accuracy statement (defined denominators only)
- Fixture-oracle agreement (controlled `127.0.0.1:18082` server, fixed guard + scoped client):
  6/6 packs confirm (BOLA, BFLA, SSRF, mass-assignment, AUTH×2; conf 0.90–0.98). Oracle and
  fixtures are co-designed — agreement, not independent exploit proof.
- Rule unit suite: 13/13 pairs behave as specified (vuln fires / safe silent).
- No global accuracy/FPR is claimed: the denominator for a whole-repo rate would require
  ground truth for all 38 endpoints including test strings, which does not exist. The
  `<3.6% FPR` / `96.4%` / `100% BOLA` claims therefore remain **unsupported here** (see
  claims doc). Known residual FNs (unchanged behavior, documented): Dart/Go/Kotlin per-route
  auth + body params, `callbackUrl`-style SSRF params, query-param file paths, labs-orders BOLA
  (no DB flag), patient-record BOLA category, mass-assignment on Dart profile.

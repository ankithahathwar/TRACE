# SECURITY FINDING TRIAGE — All 40 Original Findings + Corrections

Source of truth for IDs/rows: `.trace/baseline/findings_baseline_b25af40.json` (copy of the stored
`.trace/findings.json` at `b25af40`; the stored report is **stale**: live `b25af40` code generates
42 hypotheses/42 static findings — the stored 40 predate the privilege-escalation rule branch —
see row TR-MASS-005 and §7). Verdicts below were each checked against the cited source file.
Nothing here is a vulnerability in TRACE itself: every finding originates in bundled
labs / benchmark fixtures / test files. Severity/confidence are the scanner's static priors
unless §7 runtime confirmation applies.

Legend — **OC** oracle-confirmed (controlled local fixture server, §7); **SS** strong-static
(intentional flaw visible in code, exploit not run here); **LEAD** plausible, context missing;
**FP** false positive; **STALE** artifact of the outdated stored report.

## 1. Labs `labs/vending-api/app/main.py` (intentionally vulnerable app, all routes registered via FastAPI decorators)

| ID | Cat/Sev | Endpoint | File:line | Provenance | Registered? | Dangerous op / missing control? | Verdict | Scanner change |
|---|---|---|---|---|---|---|---|---|
| TR-CORS-001 | CORS/MED | GET /api/orders/{id} | main.py:83 | Lab | Yes (`@app.get`) | No CORS header evidence; generic auth+sensitive rule | LEAD (noise) | None (rule kept; counted as lead) |
| TR-BFLA-002 | BFLA/HIGH | POST /api/admin/refund | main.py:94 | Lab | Yes | Real: any authenticated user refunds (`if not current_user` only, no role check, main.py:94-103) | SS | None (kept) |
| TR-CORS-003 | CORS/MED | POST /api/admin/refund | main.py:94 | Lab | Yes | Same as above, no header evidence | LEAD | None |
| TR-AUTH-004 | AUTH/HIGH | POST /api/fetch-url | main.py:109 | Lab | Yes | Real: no auth on SSRF sink (`httpx.Client...client.get(req.url)`, main.py:109-115) | SS | None (kept) |
| TR-MASS-005 | MASS/MED | PATCH /api/users/{id} | main.py:121 | Lab | Yes | **STALE**: live code reports this as priv-esc BFLA instead (`user.update(payload)` can set `role`/`is_admin`, main.py:121-127); corrected scan: TR-BFLA-005 HIGH/HIGH | SS (recategorized) | None (elif structure pre-existing) |
| TR-CORS-006 | CORS/MED | PATCH /api/users/{id} | main.py:121 | Lab | Yes | No header evidence | LEAD | None |
| TR-AUTH-007 | AUTH/HIGH | GET /api/search | main.py:132 | Lab | Yes | Debatable: read-only search flagged via sensitive heuristic; no auth, no sensitive data handling | LEAD | None |
| TR-INJ-008 | INJ/CRIT | GET /api/search | main.py:132 | Lab | Yes | **No SQL sink** (simulated error string + list filter, main.py:131-139) | FP | **Removed by sink gate** (no INJ on this route in corrected scan) |

## 2. Orders, patients, tenant-vaults — exact sources ( RCT: benchmark fixture, LAB, TEST-STR = unit-test string, SYN = synthetic adapter output)

- `/api/admin/refund` → TR-BFLA-002, LAB `labs/vending-api/app/main.py:94`, registered, SS (any-authenticated refund). Not TRACE application code (TRACE `src/` has 0 endpoints).
- `/api/v1/orders` (bare) → **no finding ever existed**; the inventory has `POST /api/v1/orders/create` (TEST-STR `tests/test_django_adapter.py:16` and `tests/test_route_extraction.py`), unregistered application-wise, no rule fired. Nothing to confirm.
- `/api/v1/orders/{order_id}` → TR-BOLA-034, TEST-STR `tests/test_django_adapter.py:15` (a `path(...)` string inside a unit test, never registered in any app). FP as an application finding; removed in corrected scan by the handler-evidence gate (no handler body → `database_access=False`).
- `/api/orders/{id}` → two rows: TR-CORS-001 (LAB `main.py:83`, registered; BOLA-shape flaw is real — `get_order` returns any order without ownership check, main.py:82-88 — but flagged only CORS; the scanner never claimed BOLA here) and TR-BOLA-040 (TEST-STR `tests/test_trace.py:55`, sample code in a parser test; FP as app finding, removed by evidence gate).
- Patient export `GET /api/v3/patients/{patientId}/records/export` → TR-AUTH-033, RCT `testbed_hardcore/services/kotlin_data/src/RecordsController.kt:11-12`, registered (`@GetMapping`, class `@RequestMapping("/api/v3/patients")`). Code comment declares intentional BOLA (no org/doctor check, returns `medicalHistory`); scanner flagged AUTHENTICATION (unauthenticated sensitive) rather than BOLA (Kotlin `database_access` heuristic missed it). Verdict: **SS intentional-fixture detection with debatable category** (kept as AUTH lead; BOLA-category FN documented).
- Tenant vault `GET /api/v2/tenants/{tenant_id}/vaults/{vault_id}/entries/{entry_id}` → TR-BOLA-023, RCT `testbed_hardcore/backend/views.py:27-30`, registered (`urlpatterns`, views.py:62), real raw sink comment (`db.query...filter_by(id=entry_id)`), no tenant check → **SS** (kept, now with correct POST/GET methods around it). Its synthetic shadow `GET /api/tenant-vault-secret-entry` (TR-AUTH-026) was SYN (unregistered `@api_view` invention) → **FP removed** by the registration gate.

## 3. All remaining rows

| IDs | Endpoint (origin) | Verdict | Notes / change |
|---|---|---|---|
| TR-BFLA-009 | GET orgs/.../projects (Dart `routes.dart:14`, RCT) | LEAD (was miscat BFLA) | Fired only via file-wide `admin` role contamination (adapter set `roles=[admin]` because `admin_controller` is imported). Corrected: no BFLA (kept CORS-010). True tenant-ownership flaw noted as BOLA-category FN (Dart `database_access` is file-level). |
| TR-BFLA-011 | POST admin/users role (Dart :18, RCT) | SS | Real admin path (`/admin/` + role-modify handler `admin_controller.dart`); kept as TR-BFLA-009. OC at runtime (role → SUPER_ADMIN, §7). |
| TR-BFLA-013 | POST webhooks/preview (Dart :22, RCT) | FP (wrong category) | Same contamination; real flaw is SSRF (see OC). Corrected: BFLA gone, CORS-011 lead kept, SSRF covered by OC run. |
| TR-SSTI-014 | POST webhooks/preview (Dart :22) | FP | No template sink (`webhook_controller.dart` only `http.get`); **removed by template-sink gate**. Must never have been CRITICAL. |
| TR-BFLA-016 | POST billing refund (Dart :26, RCT) | FP (wrong category) | Contamination; handler truly lacks JWT (comment) → AUTH-shape lead, but file-level `auth=True` hides it (documented FN). Corrected: BFLA gone, CORS-012 kept. |
| TR-BFLA-018 | PUT users/profile (Dart :30, RCT) | FP (wrong category) | Contamination; true flaw is mass assignment (`user_controller` binds arbitrary fields) but Dart extracts no body params (documented FN). Corrected: BFLA gone, CORS-013 kept. |
| TR-AUTH-020/021 | Kotlin records (RCT `RecordController.kt:15,32`) | SS | BOLA-shape (`findRecordById`, no tenant check) + partial SSRF denylist (`dispatchAuditExport` blocks 4 substrings only — bypassable). Flagged AUTH (unauthenticated) — plausible; SSRF-category FN documented. |
| TR-INJ-022 | GET /api/v1/analytics/query (RCT `views.py:61`) | SS w/ wrong method | Real `f"SELECT ... '{filter_val}'"` (views.py:20). Baseline extracted GET; actual `@api_view(["POST"])`. Corrected: TR-INJ-017 **POST** + new TR-AUTH-016 on the real route. |
| TR-AUTH-024 | POST webhook/dispatch (RCT views.py:63) | SS | Real `requests.get(target_url)` from nested `webhook.target_url` (views.py:35-40). Kept (TR-AUTH-019). |
| TR-AUTH-025/027/028 | `/api/analytics-metric-query`, `/api/webhook-integration-dispatch`, `/api/system-vacuum-cleanup` (views.py fns) | FP (SYN, unregistered) | Decorator-derived invented paths; **removed by registration gate + dedupe**. Real vacuum route now correctly covered (TR-AUTH-020 POST). |
| TR-BFLA-029 | PUT /api/v1/auth/profile (`dart_auth/routes.dart:10`, RCT) | FP (wrong category) | `is_admin`/`role` substrings set file-wide admin role; handler is mass-assignment, not admin. Corrected: BFLA gone; CORS-021 kept; mass-assign FN (no body params in Dart) documented. |
| TR-AUTH-031/032 | Go query/vault (`go_service/main.go:19,27`, RCT) | SS (query), LEAD (vault) | `Sprintf("SELECT...")` is a genuine SQLi sink → corrected scan newly reports TR-INJ-023 CRITICAL (was AUTH-only). Vault tenant leak stays AUTH lead (BOLA-category FN: Go `database_access` heuristic misses it). |
| TR-BOLA-035, TR-CORS-036, TR-BFLA-037, TR-CORS-038 | `tests/test_django_adapter.py:17-18` strings | FP (TEST-STR) except 037 | 034/035/039/040-class: removed by evidence gate. 037 (`/admin/export`) kept (TR-BFLA-027): path-admin evidence is genuine even in a string; CORS-036/038 kept as leads. Residual test-string extraction is a known regex limitation (§6 of scope doc). |
| TR-BOLA-039 | `tests/test_trace.py:38` sample | FP (TEST-STR) | Removed by evidence gate. |

## 4. Corrected-scan disposition (full profile, 28 findings)
CORS 11 (leads), AUTH 10 (8 SS/test-confirmed + 2 leads), BFLA 4 (002 refund SS, 005 users priv-esc SS, 009 admin-role SS/OC, 027 test-string path-admin LEAD), INJECTION 2 (analytics POST SS, Go Sprintf SS), BOLA 1 (tenant-vault SS). Zero CONFIRMED in static mode by design; runtime confirmations in §7. `app` profile: 0 findings (TRACE `src/` exposes no endpoints). `fixtures` profile: all 28 (fixture detections, explicitly labeled, reproducible via `--scope fixtures`).

## 5. Required scanner/reporting changes (done vs documented)
Done: sink-gated INJ/SSTI (`hypotheses.py`), admin-evidence BFLA guard, role-assignment tightening, Django registration/dedupe/method/db-evidence, FastAPI fallback (`database_access=False`, low confidence), scope profiles + report scope sections, stale-score language (see claims doc). Documented-not-changed: CORS-per-endpoint noise (kept as leads), Dart/Go/Kotlin per-route auth + body-param extraction (needs cross-file handler analysis), test-string regex matches, duplicate BFLA+priv-esc on one route, `GET /` include-route inventory.

## 6. Order/patient/vault answers
Every order finding traces to LAB (`main.py:94` refund SS; `main.py:83` CORS-only on a BOLA-shape route) or TEST-STR (034/040, removed); no order route exists in TRACE `src/`. Patient export and tenant vault trace to RCT benchmark fixtures with intentional flaws (SS), reported as static leads — valid benchmark detections, not TRACE vulnerabilities. No route was assumed vulnerable from its name in the corrected rules; each kept finding cites handler-source evidence.

## 7. Controlled runtime confirmations (loopback only, fixed guard)
`test-repository/server.py` on `127.0.0.1:18082` (stdlib, terminated after), target authorized via fixed `allow_target`, all requests via `ScopedHttpClient`: BOLA projects, BFLA role→SUPER_ADMIN, SSRF preview (internal-loopback probe echoed), mass-assignment `is_admin`, AUTH records + AUTH refund — **6/6 oracle-confirmed** (conf 0.90–0.98). This validates the fixtures as genuinely exploitable *by the harness's own oracles* and proves the V2 fix preserves authorized-target workflows; it is not an independent pentest (oracles and fixtures are co-designed).

## 8. V3 / V4 / V5 separate triage (no code changes bundled)
- **V3 updater** (`updater.py:218,226-232,252-280,26-28,76-142`): (a) `shell=True` (win32) + unquoted-allowl
...[truncated 1580 chars]
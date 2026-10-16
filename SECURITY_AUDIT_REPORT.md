# SECURITY AUDIT REPORT — TRACE b25af40
Date 2026-10-15. Env win32 Python3.11.9. pytest absent so suite NOT run. Repo dirty (staged deletions from interrupted clone) — source reads unaffected.

## A. Executive summary
- TRACE itself IS vulnerable: V1 path traversal CONFIRMED (arbitrary overwrite via absolute + ../), V2 allowlist bypass CONFIRMED (any host whitelisted). V3 conditional shell injection shape + missing updater integrity. V4 MCP arbitrary local path by design, needs hardening. V5 low.
- Scanner pipeline is real (ingest>parse>adapters>APM>hypotheses>testpacks>correlate>report) but self-scan 40 findings are against INTENTIONAL fixtures (labs/vending-api, test-repository), mostly MEDIUM static-only, not prod 0-days. Model weights absent locally so latency/training claims unverified here.
- Do NOT fix yet per instructions. Regression tests specified below.

## B. Confirmed register
| ID | File:line | Root cause | Precond | Impact | Sev | Evidence |
|---|---|---|---|---|---|---|
| V1 | harness/patcher.py:21,39,95,134 | no containment on rel_path | control rel_path + invoke patch | overwrite any file user can write; RCE only if exec file + run | High (CWE-22) | absolute True PWNED2; ../sent2 True PWN |
| V2 | policy/scope.py:74-80 + callers cli 322/mcp283/verify90 | allow_target adds any host | control target param | SSRF guard bypass incl metadata | High (CWE-285) | evil + 169.254 validated BYPASS |
| V3a | updater.py:226 shell=True win | unsanitized target_version in shell | malicious registry/cache | cmd injection | Med-High cond | code read; no regex |
| V3b | updater cache | no HMAC/perms | write ~/.trace/cache | version downgrade/pin | Medium | code read |
| V4 | mcp/server.py:196 ingest/repo.py:23 | no repo allowlist | MCP client access | local file disclosure/DoS | Medium/Low | code + 2MB cap only |

## C. V1-V5 disposition vs preliminary
V1 correct but RCE overstated as unconditional — needs exec. V2 correct as bypass, SSRF needs fetch path. V3 bundled too much — split above. V4 overstated as vuln — largely intended local-tool power. V5 false-positive as RCE — list-form safe, hardening only.
Safe-A torch verified safe-shape (weights_only True, single site). Safe-B verified for examined HTML contexts. Safe-C partially protected (revalidate present, TOCTOU+DNS gap, defeated by V2).

## D. Scanner validity
Routes /api/search (labs/main.py) and /webhooks/preview (routes.dart:22) exist in fixtures with vuln comments. APM NetworkX edges File>Endpoint>Handler verified in apm/builder.py. Severity from correlate static-only. Prior 40-count not re-derived (no pytest/models) — classify as Strong-static/Potential, not Confirmed exploits.

## E. PPT claims: mostly Not-tested here (no weights, no suite, no PPT binary read). Code supports pipeline + adapters + SARIF/MCP; perf/model numbers Unsupported-locally.

## F. Repro log
- rev-parse b25af40 ok. PoCs via python -c tmpdir sentinel only. pytest unavailable. Symlink test blocked (Win privilege). _audit file removed.
- Commands in AUDIT_NOTES.

## G. Remediation (do NOT apply yet)
V1: resolve+is_relative_to+reject absolute/symlink escape; tests fail-before/pass-after. V2: allow_target only loopback/private + DNS resolve + per-request re-resolve. V3: shell=False, version allowlist regex, TLS default + provenance note, cache HMAC/perms. V4: repo allowlist + secret exclude + caps. V5: port int check + command allowlist.

## H. Verdict
1 Yes. 2 V1,V2 genuine; V3 cond; V4 design; V5 hardening. 3 Preliminary severities partly overstated. 4 No — 40 are fixture static findings. 5 Potential/strong-static, not confirmed RCE. 6 Architecture supported; perf/model claims not reproduced here. 7 Next: install pytest+run suite; pull LFS weights + re-bench; implement V1+V2 fixes with red-green after approval.

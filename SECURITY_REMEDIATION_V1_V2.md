# SECURITY REMEDIATION V1 + V2 — Root Causes, Fixes, Red-Green Evidence

Branch: `security/remediation-and-scan-quality` (from `b25af40b69f9c1609b3eb1073071bce47a5ead16`).
Historical audits `AUDIT_NOTES1.md` / `SECURITY_AUDIT_REPORT1.md` left unchanged.
Baseline artifacts: `.trace/baseline/findings_baseline_b25af40.json(.md)`, `.trace/baseline/repro_baseline_b25af40.json`, `.trace/baseline/repro_scan.py` (inside ignored `.trace/`, so they do not affect scan counts).
Env: win32, Python 3.11.9, torch 2.12.1+cpu, pytest 9.1.1. Pre-existing working-tree state preserved: 6 staged deletions (LFS/submodule pointers: `benchmarks/owasp-python`, `models/*/laya_dual_head.{onnx,pt}`, `models/*/model.safetensors`, `research/laya`, `research/securebert2`) were documented, not discarded, and are untouched by this work.

No `benchmark.md` and no PPT exist in the repository (glob for `**/benchmark*.md`, `**/*.pptx`, `**/*.ppt` all empty); claim mapping uses `docs/BENCHMARKS.md`, `docs/TRACE_Benchmark_and_Audit_Metrics.md`, `README.md` (see `SECURITY_CLAIMS_VERIFICATION.md`).

---

## 1. V1 — SafePatcher workspace containment

### Root cause
`src/trace_engine/harness/patcher.py` built every file target as `self.workspace_root / rel_path` in `backup()` (:19), `apply_replacement()` (:39), `apply_full_content()` (:95) and `rollback()` (:134), with no absolute-path rejection, no `..` containment, no symlink/junction resolution, and no validation of the rollback source. Reachable via MCP `trace_eval_patch.target_file` (`mcp/server.py:119,331-344` → `plugin/evaluator.py:49,103`) and via findings-store `source_location.file` (`harness/engine.py:104,161`). Temporary-file handling: backups are written under `.trace/backups/` with separator-mangled names — an outside `rel_path` leaked outside content into the workspace.

### Fix (`harness/patcher.py`, plus caller hardening in `harness/engine.py`)
- New `WorkspaceBoundaryError(ValueError)` and `_looks_like_absolute_or_unc()` (POSIX `Path.is_absolute` + `PureWindowsPath` + drive-letter regex + UNC prefixes in either separator + NUL rejection), so Windows shapes are refused on any platform and vice versa.
- New `_resolve_contained(rel_path)`: rejects empty/absolute/UNC/drive paths, joins, `resolve()`s (symlinks/junctions resolved by the OS), and requires `is_relative_to(workspace_root)`. Returns the resolved path so callers operate on the validated destination — never a reconstructed one. Dot-segments resolving inside (e.g. `sub/../ok.txt`) still work.
- `_resolve_backup_file()`: rollback sources must resolve inside this patcher's `.trace/backups/` dir (blocks foreign-file read-into-workspace).
- `backup()` raises `WorkspaceBoundaryError` on escape (still `FileNotFoundError` for missing inside files); `apply_*` return `PatchResult(success=False)` on escape (API preserved); `rollback()` returns `False` on any boundary failure.
- `harness/engine.py:build_remediation_package`: snippet reads are containment-checked (exact path, then contained subdirectory fallback); outside paths yield an empty snippet instead of leaking file content into agent context.
- Race note: resolve-then-operate narrows the validation-to-use window (single resolved `Path` object, no re-joining), but OS-level TOCTOU (symlink swapped between check and write) cannot be fully closed without handle-based (`O_NOFOLLOW`) I/O — documented limitation; the residual requires a local attacker racing a patch operation.

### Red-green evidence (`tests/test_v1_patcher_containment.py`, 9 tests)
Vulnerable baseline: **6 failed, 2 passed, 1 skipped**. Fixed: **8 passed, 1 skipped**.
The 2 baseline passes were vacuous (non-existent `C:\…`/UNC shapes → `FileNotFound`, not a block); the 6 true reds (absolute overwrite of an existing sentinel, `../outside.txt`, nested `sub/../../outside.txt`, backup exfil, rollback-outside, foreign-backup) all fail before and pass after. Sentinel files verified byte-identical after each blocked attempt; legitimate replacement/full-content/rollback/`sub/../` cases pass. Skip: symlink-escape test (Windows privilege 1314 without elevation — same blocker as the original audit; POSIX CI covers it).

### Limitations
Symlink-race TOCTOU (above); backup filenames still derive from the (now guaranteed-inside) relative path; absolute-path MCP callers get an explicit error and must send workspace-relative paths (minor compat note).

## 2. V2 — Target authorization and HTTP access

### Root cause (two parts)
(a) `ScopeGuard.allow_target()` (`policy/scope.py:74-80`) unconditionally added any hostname+port, and all six call sites (`cli.py`, `mcp/server.py:283`, `verify.py:90`, `interactive.py:588`) invoked it on operator input before validation — conflating registration with authorization, so any influenced `target` (external host, `169.254.169.254`) validated afterwards. No DNS resolution, no IP normalization beyond literal `ipaddress`, no rebinding consideration.
(b) Liveness probes fetched operator URLs with raw `httpx` and no guard at all (`cli.py:335,625`, `interactive.py:578`).

### Fix
`policy/scope.py` rewritten around registration-vs-authorization:
- `register_target(url)` — parse-only inventory, grants nothing (registered-but-unauthorized hosts stay blocked; tested).
- `allow_target(url)` — kept name for compatibility but is now explicit, *checked* authorization: scheme/host/port parse, `_authorizable()` (always-blocked metadata names; literals must satisfy address policy; unknown non-literal names refused even offline; listed names pass subject to DNS re-check), then record + full `validate_url`, with rollback on failure.
- `validate_url()` — hostname normalization (lowercase, trailing-dot, IDNA); legacy IPv4 forms via `inet_aton` semantics (`127.1`, `2130706433`, `0x7f…` → loopback; `0xA9FEA9FE` → link-local → blocked); address policy (loopback always; `0.0.0.0` kept as loopback-equivalent with documented rationale; link-local/multicast/reserved/global always blocked; private only in `private-lab` mode); DNS re-check of authorized names through an injectable resolver (fail-open only when unresolvable — offline labs; any resolved prohibited address blocks, defeating naive rebinding); loopback keeps any valid port (existing behavior), other hosts require listed ports.
- `runtime/client.py` — added `probe_target_online(guard, url, timeout)`: validates first, returns `False` on policy refusal without sending anything. `ScopedHttpClient.execute` still validates pre-request and revalidates redirect `Location`s with `follow_redirects=False` (no auto-follow).
- Call sites: `cli.py` (2 scan flows + lab health), `interactive.py`, `verify.py` (refused target → `INCONCLUSIVE`, no probe), `mcp/server.py` (`trace_scan` returns `status: refused`, no request), `ai/ollama.py` (endpoint scope-checked; refusal → unavailable/`None`). Raw `httpx.get(target)` probes eliminated; the hardcoded loopback candidates in `interactive.py:416` are unchanged (no user input) with a comment.
- Deliberately untouched (documented, out of V1/V2 patch scope): model-training bulk downloader (`morefixes_pipeline.py:87`, `follow_redirects=True`, dev-only pipeline), model-weight downloader hosts, updater fetches — see §4 / triage doc.

### Red-green evidence (`tests/test_v2_scope_guard.py`, 15 tests)
Vulnerable baseline: **11 failed, 4 passed**. Fixed: **15 passed**. Fail→pass covers: external/metadata refusal by `allow_target`, registered-but-unauthorized blocking, DNS-public blocking, DNS-loopback acceptance, offline listed-lab acceptance, private-lab literal acceptance, local-mode private refusal, legacy-IP normalization both directions, redirect rejection, pre-request validation (mock asserts no fetch), probe-helper refusal without fetch + loopback success. Existing `tests/test_bugs_and_edge_cases.py` (7 tests) passes unchanged, including the `my-lab.local` allow-target workflow (now via checked authorization + offline fail-open for listed names).

### Limitations (do not claim complete SSRF prevention)
Validate-then-connect TOCTOU remains (httpx resolves independently; connection-level IP pinning would be needed for full closure). DNS fail-open for unresolvable *listed* names is a deliberate offline-lab tradeoff. `0.0.0.0` remains allowed as loopback-equivalent. Explicit authorization is still bounded by local/lab-only policy — a public `--target` is refused with a clear error rather than scanned.

## 3. Regression + acceptance runs
- New: V1 (8 passed/1 skipped), V2 (15 passed), scope (6), route-extraction (5), hypothesis-rules (13) = 45 passed, 1 skipped.
- Existing suite: full `tests/` in batches — 112 passed/1 skipped (main batch, incl. updated `test_new_vulnerabilities.py`), 6 passed (`test_hardcore_testbed.py` + `test_intelligence.py`), 2 passed (`test_laya_training.py`, one taking 305 s — the reason the file exceeds a 120 s default timeout). Total **120 passed, 1 skipped**; the single skip is the Windows symlink test (needs elevation).
- One existing test updated for the intended contract change (`test_new_vulnerabilities.py`: SSTI case now supplies template-sink evidence via tmp file); no other existing tests touched.
- Runtime proof the V2 fix preserves legit workflows: fixture server on `127.0.0.1:18082` authorized via fixed `allow_target`, and all 6 testpack oracles executed through `ScopedHttpClient` (see triage doc §7).

## 4. V3 / V4 / V5 — separate triage, no code changes bundled
Per the phase-9 constraint, updater (shell/cache/trust), MCP path/ingest, and lab/tool-subprocess issues received **no code changes** in this patch. Evidence and recommendations live in `SECURITY_FINDING_TRIAGE.md` §8. The only HTTP-surface changes (ollama endpoint check, downloader untouched) are V2 scan-path enforcement, not supply-chain remediation.

## 5. Independent verification addendum (post-remediation audit)
An independent pass re-verified every claim above against the code (not the prose) and found
three defects, all fixed here — no other behavior changed:
- **Port `:0` validated as port 80 (V2 gap, fixed).** `parsed.port or default` turns explicit
  `:0` (falsy) into 80, so the validated URL differed from the requested one. Both
  `validate_url` and `allow_target` now reject port 0 explicitly; regression test
  `test_explicit_port_zero_is_rejected_not_defaulted` added. Impact was negligible (port 0
  never connects), but a security boundary must not validate a different URL than requested.
- **Drive-relative `C:evil.txt` shapes (V1 checked, no change needed).** Empirically,
  `workspace / "C:evil.txt"` resolves *inside* the workspace on Windows (pathlib keeps the
  left anchor), so resolve+`is_relative_to` holds; the attempt ends in `File not found` with
  no write. Backslash traversal, `....//`, device paths (`\\?\C:\…`), NUL and empty paths all
  refused with sentinels byte-identical.
- **Scope robustness (fixed).** `trace_scan` with `scope=fixtures` on a repo that itself has
  no fixture-named dirs (e.g. `test-repository`) returned a misleading empty `completed`
  scan; it now scans the whole target with an explanatory `note` (also surfaced in
  `test_all_report.json` / MCP `scan_scope`). Unknown scope values raised an unhandled
  `ValueError`; MCP now returns `{"status":"error",...}` and CLI commands reject with
  `typer.BadParameter`. Tests added (`test_fixtures_profile_on_fixture_repo_scans_it_whole`,
  `test_mcp_rejects_unknown_scope_without_traceback`,
  `test_mcp_refuses_out_of_scope_target_without_fetch`).
- **Deliberate strictness (unchanged):** IPv4-mapped IPv6 loopback (`::ffff:127.0.0.1`) stays
  refused (fail-closed; operators use `127.0.0.1`); `evil.com@127.0.0.1` is correctly allowed
  (userinfo is not the connect target) while `127.0.0.1@evil.com` is blocked; `0.0.0.0`
  remains a loopback-equivalent by documented decision.
- **Red-green re-established independently** on a pristine `b25af40` worktree with the new
  test files copied in: **18 failed / 8 passed / 1 skipped** (6 V1 behavioral + V2 behavioral
  and new-API failures; the 8 passes are pre-existing behaviors such as loopback acceptance
  and literal-metadata refusal). Fixed tree: **26 passed / 1 skipped** for the two files
  (27 tests incl. the 3 port-0/userinfo/mapped-loopback additions; skip = Windows symlink
  privilege). Full suite after all verification fixes: **121 passed / 1 skipped** (`tests/`,
  laya-training excluded) + 2 laya-training passes from the prior run = **123 / 1** total.
- Verification side effects cleaned: an MCP probe wrote `test-repository/.trace/` (git-ignored);
  removed. Root `.trace/findings.json` and `.trace/baseline/*` untouched (timestamps verified).

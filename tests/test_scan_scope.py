"""Scan-scope profiles: full/app/fixtures separation without silent hiding."""

from pathlib import Path

from trace_engine.scan_scope import (
    FIXTURE_DIR_PATTERNS,
    VALID_PROFILES,
    resolve_scope,
    scoped_scanner,
)


def _make_repo(tmp_path: Path) -> Path:
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "app" / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/hi')\ndef hi(): return {}\n",
        encoding="utf-8",
    )
    (tmp_path / "labs" / "vuln").mkdir(parents=True)
    (tmp_path / "labs" / "vuln" / "app.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x(): pass\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "notes.md").write_text("# notes\n", encoding="utf-8")
    return tmp_path


def test_profiles_are_explicit_and_known():
    assert set(VALID_PROFILES) == {"full", "app", "fixtures"}
    assert "labs" in FIXTURE_DIR_PATTERNS and "tests" in FIXTURE_DIR_PATTERNS


def test_full_scope_reproduces_unfiltered_scan(tmp_path):
    repo = _make_repo(tmp_path)
    scanner, result = scoped_scanner(repo, "full")
    files = scanner.scan()
    paths = {f.path for f in files}
    assert "src/app/main.py" in paths
    assert "labs/vuln/app.py" in paths
    assert "tests/test_x.py" in paths
    assert result.excluded_top_dirs == {}


def test_app_scope_excludes_fixture_dirs_and_reports_why(tmp_path):
    repo = _make_repo(tmp_path)
    scanner, result = scoped_scanner(repo, "app")
    paths = {f.path for f in scanner.scan()}
    assert "src/app/main.py" in paths
    assert "labs/vuln/app.py" not in paths
    assert "tests/test_x.py" not in paths
    assert "labs" in result.excluded_top_dirs
    assert "tests" in result.excluded_top_dirs
    assert result.excluded_top_dirs["labs"] == "fixture/test directory pattern"
    assert any("labs" in line for line in result.summary_lines())


def test_fixtures_scope_scans_only_fixture_dirs(tmp_path):
    repo = _make_repo(tmp_path)
    scanner, result = scoped_scanner(repo, "fixtures")
    paths = {f.path for f in scanner.scan()}
    assert "labs/vuln/app.py" in paths
    assert "tests/test_x.py" in paths
    assert "src/app/main.py" not in paths
    assert "src" in result.excluded_top_dirs


def test_traceignore_still_honored_in_every_profile(tmp_path):
    repo = _make_repo(tmp_path)
    (repo / ".traceignore").write_text("src/app/main.py\n", encoding="utf-8")
    for profile in ("full", "app", "fixtures"):
        scanner, _ = scoped_scanner(repo, profile)
        paths = {f.path for f in scanner.scan()}
        assert "src/app/main.py" not in paths


def test_unknown_profile_rejected(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        resolve_scope(tmp_path, "everything")


def test_fixtures_profile_on_fixture_repo_scans_it_whole(tmp_path):
    # A benchmark fixture repo has no fixture-named top dirs; the fixtures
    # profile must scan it whole (with a note), not return a silent empty scan.
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "routes.dart").write_text("router.get('/x', h);\n", encoding="utf-8")
    scanner, result = scoped_scanner(tmp_path, "fixtures")
    paths = {f.path for f in scanner.scan()}
    assert "lib/routes.dart" in paths
    assert result.excluded_top_dirs == {}
    assert "whole target" in result.note


def test_mcp_rejects_unknown_scope_without_traceback():
    from trace_engine.mcp.server import TraceMCPServer

    res = TraceMCPServer().execute_tool(
        "trace_scan", {"repository": ".", "scope": "bogus", "target": "http://127.0.0.1:9"}
    )
    assert res["status"] == "error"
    assert "bogus" in res["error"]


def test_mcp_refuses_out_of_scope_target_without_fetch():
    from unittest.mock import patch

    from trace_engine.mcp.server import TraceMCPServer

    with patch("httpx.Client") as cli:
        res = TraceMCPServer().execute_tool(
            "trace_scan", {"repository": ".", "scope": "full", "target": "http://evil.com/"}
        )
        assert res["status"] == "refused"
        cli.assert_not_called()

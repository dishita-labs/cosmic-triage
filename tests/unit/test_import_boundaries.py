"""§13.2 Snapshot-only data access, enforced two ways: import-linter contracts and a direct AST scan."""

from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from pathlib import Path

from cosmic_triage.settings import PROJECT_ROOT

SRC = PROJECT_ROOT / "src" / "cosmic_triage"
DECISION_PKGS = ("belief", "value", "schedule")
NON_REPLAY_PKGS = ("belief", "value", "schedule", "investigator", "metrics", "api", "contracts")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
            out.update(f"{node.module}.{a.name}" for a in node.names)
    return out


def _files(pkg: str) -> list[Path]:
    return sorted((SRC / pkg).rglob("*.py"))


def test_import_linter_contracts_kept() -> None:
    exe = shutil.which("lint-imports") or str(Path(sys.executable).parent / "lint-imports")
    proc = subprocess.run([exe], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "0 broken" in proc.stdout


def test_only_replay_imports_bts_truth() -> None:
    for pkg in NON_REPLAY_PKGS:
        for f in _files(pkg):
            bad = {m for m in _imports(f) if m.startswith("cosmic_triage.ingest.bts") or m.endswith("BTSCatalog")}
            assert not bad, f"{f.relative_to(PROJECT_ROOT)} imports BTS truth: {bad}"


def test_decision_modules_never_touch_ingest_or_cache() -> None:
    for pkg in DECISION_PKGS:
        for f in _files(pkg):
            bad = {m for m in _imports(f) if m.startswith(("cosmic_triage.ingest", "cosmic_triage.replay"))}
            assert not bad, f"{f.relative_to(PROJECT_ROOT)} bypasses Snapshot: {bad}"


def test_no_module_outside_ingest_reads_cache_files_directly() -> None:
    """No raw reads of data/cache outside ingest (string scan for the cache path)."""
    for f in SRC.rglob("*.py"):
        if f.is_relative_to(SRC / "ingest") or f.name == "settings.py":
            continue
        assert "data/cache" not in f.read_text(), f"{f.relative_to(PROJECT_ROOT)} references the raw cache path"


def test_ingest_package_does_not_reexport_bts() -> None:
    import cosmic_triage.ingest as ingest

    assert not hasattr(ingest, "BTSCatalog")


def test_import_linter_catches_an_injected_violation(tmp_path: Path) -> None:
    """The rule must actually bite: copy the package, make `belief` import BTS truth, expect a broken contract."""
    shutil.copytree(SRC, tmp_path / "src" / "cosmic_triage")
    shutil.copy(PROJECT_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    (tmp_path / "src" / "cosmic_triage" / "belief" / "leak.py").write_text(
        "from cosmic_triage.ingest.bts import BTSCatalog  # injected violation\n"
    )
    exe = shutil.which("lint-imports") or str(Path(sys.executable).parent / "lint-imports")
    env = {"PYTHONPATH": str(tmp_path / "src"), "PATH": str(Path(sys.executable).parent)}
    proc = subprocess.run([exe], cwd=tmp_path, capture_output=True, text=True, timeout=120, env=env)
    assert proc.returncode != 0, proc.stdout
    assert "Only replay may import BTS truth labels BROKEN" in proc.stdout

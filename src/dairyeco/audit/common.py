"""Shared helpers for the ML audit layer (hashing, code references, persistence).

The audit layer only *describes* the pipeline: it never trains production models and never
writes into ``data/raw``. Records are persisted as JSON under ``artifacts/audit/``.
"""

from __future__ import annotations

import ast
import hashlib
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

import numpy as np

from dairyeco.config import AUDIT_DIR, PROJECT_ROOT

NOT_RECORDED = "Not recorded / Unknown"

# Source files whose content defines the data -> model pipeline (used for the code fingerprint).
PIPELINE_SOURCE_FILES: tuple[str, ...] = (
    "src/dairyeco/data/inventory.py",
    "src/dairyeco/data/audit_inspectors.py",
    "src/dairyeco/data/harmonize.py",
    "src/dairyeco/models/registry.py",
    "src/dairyeco/models/pipeline.py",
    "src/dairyeco/lca/engine.py",
    "src/dairyeco/economics/engine.py",
    "src/dairyeco/optimization/pareto.py",
)


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def code_fingerprint() -> dict[str, Any]:
    """Content hash of the pipeline sources and current git commit (if under git)."""
    files = {}
    for f in PIPELINE_SOURCE_FILES:
        p = PROJECT_ROOT / f
        files[f] = sha256_file(p) if p.exists() else "missing"
    agg = hashlib.sha256("\n".join(f"{k}:{v}" for k, v in sorted(files.items())).encode()).hexdigest()
    vcs = f"{NOT_RECORDED} (project is not under version control)"
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            vcs = res.stdout.strip()
    except OSError:
        pass
    return {"vcs_commit": vcs, "files": files, "aggregate_sha256": agg}


def environment_versions() -> dict[str, str]:
    versions = {"python": sys.version.split()[0], "platform": platform.platform()}
    for pkg in ("scikit-learn", "pandas", "numpy", "catboost", "joblib", "streamlit", "scipy"):
        try:
            versions[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            versions[pkg] = "not installed"
    return versions


def symbol_exists(rel_path: str, symbol: str) -> bool:
    """True if ``symbol`` (function, class, or ``Class.method``) is defined in the file (AST check)."""
    p = PROJECT_ROOT / rel_path
    if not p.exists():
        return False
    tree = ast.parse(p.read_text(encoding="utf-8"))
    parts = symbol.split(".")
    scope: list[ast.stmt] = tree.body
    node: ast.AST | None = None
    for part in parts:
        node = next(
            (n for n in scope
             if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.name == part),
            None,
        )
        if node is None:
            # module-level assignments (e.g. constants)
            for n in scope:
                if isinstance(n, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == part for t in n.targets
                ):
                    return True
                if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == part:
                    return True
            return False
        scope = getattr(node, "body", [])
    return True


def symbol_source(rel_path: str, symbol: str, max_lines: int = 60) -> str:
    """Return the real source text of a function/class (truncated), or an empty string."""
    p = PROJECT_ROOT / rel_path
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    tree = ast.parse(text)
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == symbol.split(".")[-1]:
            lines = text.splitlines()[n.lineno - 1 : n.end_lineno]
            if len(lines) > max_lines:
                lines = [*lines[:max_lines], f"... ({len(lines) - max_lines} more lines)"]
            return "\n".join(lines)
    return ""


def _json_default(obj: Any) -> Any:
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, (Path,)):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    return str(obj)


def write_audit_json(name: str, payload: Any, audit_dir: Path = AUDIT_DIR) -> Path:
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, default=_json_default), encoding="utf-8")
    return path


def read_audit_json(name: str, audit_dir: Path = AUDIT_DIR) -> Any | None:
    path = audit_dir / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))

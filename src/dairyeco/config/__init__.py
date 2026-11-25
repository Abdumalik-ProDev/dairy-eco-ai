"""Centralized filesystem paths and runtime configuration for DairyEco AI."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[3]
DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_DIR: Path = DATA_DIR / "raw"
INTERIM_DIR: Path = DATA_DIR / "interim"
REFERENCE_DIR: Path = DATA_DIR / "reference"
PROCESSED_DIR: Path = DATA_DIR / "processed"
SYNTHETIC_DIR: Path = DATA_DIR / "synthetic"
METADATA_DIR: Path = DATA_DIR / "metadata"
ARTIFACTS_DIR: Path = PROJECT_ROOT / "artifacts" / "models"
AUDIT_DIR: Path = PROJECT_ROOT / "artifacts" / "audit"
EXPERIMENTS_DIR: Path = PROJECT_ROOT / "artifacts" / "experiments"
REPORTS_DIR: Path = PROJECT_ROOT / "reports"
DOCS_DIR: Path = PROJECT_ROOT / "docs"

__all__ = [
    "ARTIFACTS_DIR",
    "AUDIT_DIR",
    "DATA_DIR",
    "DOCS_DIR",
    "EXPERIMENTS_DIR",
    "INTERIM_DIR",
    "METADATA_DIR",
    "PROCESSED_DIR",
    "PROJECT_ROOT",
    "RAW_DIR",
    "REFERENCE_DIR",
    "REPORTS_DIR",
    "SYNTHETIC_DIR",
]

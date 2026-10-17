"""Process settings, secret loading and config hashing.

Secrets are read from the project ``.env`` (never printed, logged, or written to fixtures).
``COSMIC_OFFLINE=1`` disables every network call; cache misses then raise.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SECRET_NAMES: tuple[str, ...] = (
    "ANTHROPIC_API_KEY",
    "TYPESAFE_API_KEY",
    "OPENROUTER_API_KEY",
    "LASAIR_TOKEN",
    "ADS_TOKEN",
    "TNS_BOT_ID",
    "TNS_BOT_NAME",
    "TNS_API_KEY",
)


@lru_cache(maxsize=1)
def _dotenv() -> dict[str, str]:
    path = PROJECT_ROOT / ".env"
    if not path.exists():
        return {}
    return {k: v for k, v in dotenv_values(path).items() if v}


def get_secret(name: str) -> str | None:
    """Process env wins over ``.env``. Returns None when unset; callers raise CredentialMissing."""
    if name not in SECRET_NAMES:
        raise KeyError(f"{name} is not a registered secret")
    return os.environ.get(name) or _dotenv().get(name) or None


def secret_values() -> list[str]:
    """All configured secret values (for scrubbing checks only; never log these)."""
    vals = [get_secret(n) for n in SECRET_NAMES]
    return [v for v in vals if v and len(v) >= 6]


def is_offline() -> bool:
    return os.environ.get("COSMIC_OFFLINE", "0").lower() in ("1", "true", "yes")


def cache_dir() -> Path:
    return Path(os.environ.get("COSMIC_CACHE_DIR", PROJECT_ROOT / "data" / "cache"))


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str, allow_nan=True)


def sha256_hex(data: str | bytes) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def load_config(path: str | Path) -> tuple[dict[str, Any], str]:
    """Load a versioned YAML config and return (content, content hash). Every config must carry ``version``."""
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    data = yaml.safe_load(p.read_text())
    if not isinstance(data, dict) or "version" not in data:
        raise ValueError(f"config {p} must be a mapping with a 'version' field")
    return data, sha256_hex(canonical_json(data))[:16]


def combined_hash(hashes: dict[str, str]) -> str:
    return sha256_hex(canonical_json(hashes))[:16]


def code_version() -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        dirty = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return out.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")
    except (OSError, subprocess.SubprocessError):
        return "unknown"

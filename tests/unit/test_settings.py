from __future__ import annotations

from pathlib import Path

import pytest

from cosmic_triage import settings


def test_offline_flag_set_in_tests() -> None:
    assert settings.is_offline()


def test_load_config_requires_version(tmp_path: Path) -> None:
    p = tmp_path / "c.yaml"
    p.write_text("a: 1\n")
    with pytest.raises(ValueError):
        settings.load_config(p)


def test_config_hash_is_content_hash(tmp_path: Path) -> None:
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_text("version: '1'\nx: 1\ny: 2\n")
    b.write_text("# comment\ny: 2\nversion: '1'\nx: 1\n")
    assert settings.load_config(a)[1] == settings.load_config(b)[1]


def test_all_repo_configs_are_versioned() -> None:
    for p in (settings.PROJECT_ROOT / "configs").rglob("*.yaml"):
        settings.load_config(p)


def test_unknown_secret_name_rejected() -> None:
    with pytest.raises(KeyError):
        settings.get_secret("NOT_A_SECRET")


def test_env_example_has_names_only() -> None:
    text = (settings.PROJECT_ROOT / ".env.example").read_text()
    for name in ("ANTHROPIC_API_KEY", "TYPESAFE_API_KEY", "OPENROUTER_API_KEY", "LASAIR_TOKEN", "TNS_BOT_ID",
                 "TNS_BOT_NAME", "TNS_API_KEY"):
        assert f"{name}=" in text
    for line in text.splitlines():
        if line.strip() and not line.startswith("#"):
            assert line.split("=", 1)[1].strip() == "", f"value present in .env.example: {line.split('=')[0]}"


def test_dotenv_is_gitignored() -> None:
    lines = (settings.PROJECT_ROOT / ".gitignore").read_text().splitlines()
    assert ".env" in lines and "!.env.example" in lines

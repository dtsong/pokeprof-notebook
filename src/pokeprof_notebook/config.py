"""Configuration loader for PokéProf Notebook."""

from __future__ import annotations

from pathlib import Path

from pokeprof_notebook.types import DomainConfig

# Project root is 3 levels up from this file: src/pokeprof_notebook/config.py
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_project_root() -> Path:
    """Return the project root directory."""
    return _PROJECT_ROOT


def load_config(config_path: str | Path | None = None) -> DomainConfig:
    """Load the domain configuration.

    Args:
        config_path: Optional explicit path. Defaults to config/domain_config.yaml
            relative to the project root.
    """
    if config_path is None:
        config_path = _PROJECT_ROOT / "config" / "domain_config.yaml"
    return DomainConfig.from_yaml(config_path)

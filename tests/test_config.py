"""Tests for pokeprof_notebook.config — project root and config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from pokeprof_notebook.config import get_project_root, load_config


class TestGetProjectRoot:
    """get_project_root() returns a valid project directory."""

    def test_returns_path_instance(self):
        root = get_project_root()
        assert isinstance(root, Path)

    def test_points_to_existing_directory(self):
        root = get_project_root()
        assert root.is_dir()


class TestLoadConfig:
    """load_config() YAML loading and path resolution."""

    def test_explicit_path_loads_successfully(self, tmp_path):
        cfg_file = tmp_path / "custom.yaml"
        cfg_file.write_text(
            "domain_name: test_domain\n"
            "routing_hints:\n"
            "  doc_a:\n"
            "    - keyword\n"
        )
        config = load_config(cfg_file)
        assert config.domain_name == "test_domain"
        assert config.routing_hints == {"doc_a": ["keyword"]}

    def test_string_path_accepted(self, tmp_path):
        cfg_file = tmp_path / "str_path.yaml"
        cfg_file.write_text("domain_name: str_test\nrouting_hints: {}\n")
        config = load_config(str(cfg_file))
        assert config.domain_name == "str_test"

    def test_missing_config_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path / "nonexistent.yaml")

    def test_default_path_loads_project_config(self):
        config = load_config()
        assert config.domain_name == "pokemon_tcg"

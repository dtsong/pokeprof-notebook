"""Tests for PokéProf Notebook CLI commands.

Uses Click's CliRunner to invoke each subcommand. External API calls
(TCGDex, Compendium, Anthropic) are mocked so tests run offline.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from pokeprof_notebook.cli import main
from pokeprof_notebook.indexer import save_tree
from pokeprof_notebook.types import (
    DocumentIndex,
    DocumentType,
    NodeMetadata,
    TreeNode,
)


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def tmp_project(tmp_path, monkeypatch):
    """Set up a minimal project structure in tmp_path and patch paths."""
    sources = tmp_path / "data" / "sources"
    intermediate = tmp_path / "data" / "intermediate"
    indexes = tmp_path / "data" / "indexes"
    config_dir = tmp_path / "config"
    prompts_dir = config_dir / "prompts"

    for d in (sources, intermediate, indexes, prompts_dir):
        d.mkdir(parents=True)

    # Minimal domain config — only rulebook to avoid routing noise
    (config_dir / "domain_config.yaml").write_text(
        """\
domain_name: pokemon_tcg
documents:
  - name: rulebook
    description: "Rulebook"
    source_path: data/intermediate/rulebook.md
    index_path: data/indexes/rulebook.json
    section_pattern: ''
  - name: card_db_pokemon
    description: "Pokemon cards"
    source_path: data/intermediate/card_db_pokemon.md
    index_path: data/indexes/card_db_pokemon.json
    section_pattern: ''
  - name: card_db_trainers
    description: "Trainer cards"
    source_path: data/intermediate/card_db_trainers.md
    index_path: data/indexes/card_db_trainers.json
    section_pattern: ''
  - name: card_db_energy
    description: "Energy cards"
    source_path: data/intermediate/card_db_energy.md
    index_path: data/indexes/card_db_energy.json
    section_pattern: ''
  - name: rulings_compendium
    description: "Rulings Compendium"
    source_path: data/intermediate/rulings_compendium.md
    index_path: data/indexes/rulings_compendium.json
    section_pattern: ''
personas:
  judge:
    system_prompt: config/prompts/judge_system.txt
    description: "Judge"
  professor:
    system_prompt: config/prompts/professor_system.txt
    description: "Professor"
routing_hints:
  rulebook: ["rule", "energy", "attack"]
  card_db_pokemon: ["card", "pokemon"]
  card_db_trainers: ["trainer", "supporter"]
  card_db_energy: ["special energy", "basic energy"]
  rulings_compendium: ["ruling", "compendium"]
""",
        encoding="utf-8",
    )

    (prompts_dir / "judge_system.txt").write_text(
        "You are PokéProf, a judge assistant.", encoding="utf-8"
    )
    (prompts_dir / "professor_system.txt").write_text(
        "You are PokéProf, a professor assistant.", encoding="utf-8"
    )

    # Patch module-level paths in cli
    import pokeprof_notebook.cli as cli_mod

    monkeypatch.setattr(cli_mod, "_ROOT", tmp_path)
    monkeypatch.setattr(cli_mod, "_SOURCES_DIR", sources)
    monkeypatch.setattr(cli_mod, "_INTERMEDIATE_DIR", intermediate)
    monkeypatch.setattr(cli_mod, "_INDEXES_DIR", indexes)

    # Patch config loader to use our tmp config
    import pokeprof_notebook.config as config_mod

    monkeypatch.setattr(config_mod, "_PROJECT_ROOT", tmp_path)

    # Clear cached card name index so router picks up test data
    import pokeprof_notebook.router as router_mod

    monkeypatch.setattr(router_mod, "_card_name_index", None)

    return tmp_path


def _make_index(doc_name: str, doc_type: DocumentType, title: str = "Test Section") -> DocumentIndex:
    """Create a minimal DocumentIndex for testing."""
    root_meta = NodeMetadata(document_type=doc_type, title=doc_name)
    child_meta = NodeMetadata(
        document_type=doc_type, section_number="1", title=title
    )
    child = TreeNode(
        id="1", content=f"Content for {title}.", metadata=child_meta, token_count=5
    )
    root = TreeNode(id="root", content="", metadata=root_meta, children=[child])
    return DocumentIndex(
        document_name=doc_name,
        document_type=doc_type,
        root=root,
        total_tokens=5,
        source_hash="abc123",
    )


def _write_index(indexes_dir: Path, doc_name: str, doc_type: DocumentType, title: str = "Test Section"):
    """Write a minimal index JSON file."""
    idx = _make_index(doc_name, doc_type, title)
    save_tree(idx, indexes_dir / f"{doc_name}.json")


# ── Test: root command shows help ──


class TestMainHelp:
    def test_no_args_shows_help(self, runner):
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "PokéProf Notebook" in result.output

    def test_help_flag(self, runner):
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "ingest" in result.output
        assert "query" in result.output
        assert "serve" in result.output
        assert "fetch-cards" in result.output
        assert "fetch-compendium" in result.output


# ── Test: ingest ──


class TestIngest:
    def test_ingest_help(self, runner):
        result = runner.invoke(main, ["ingest", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output

    def test_ingest_unknown_document(self, runner, tmp_project):
        result = runner.invoke(main, ["ingest", "nonexistent"])
        assert result.exit_code == 0
        assert "Unknown document" in result.output

    def test_ingest_missing_source(self, runner, tmp_project):
        result = runner.invoke(main, ["ingest", "rulebook"])
        assert result.exit_code == 0
        assert "Source file not found" in result.output

    def test_ingest_html_document(self, runner, tmp_project):
        """Ingest an HTML source through the full pipeline."""
        sources = tmp_project / "data" / "sources"
        (sources / "Current Standard Legal Card List \u2013 The PokeGym.html").write_text(
            "<html><body><h1>Legal Cards</h1><p>Card list here.</p></body></html>",
            encoding="utf-8",
        )

        # Add legal_card_list to config
        config_path = tmp_project / "config" / "domain_config.yaml"
        config_text = config_path.read_text()
        # Append to the documents list (before personas)
        config_text = config_text.replace(
            "personas:",
            """\
  - name: legal_card_list
    description: "Legal Card List"
    source_path: data/intermediate/legal_card_list.md
    index_path: data/indexes/legal_card_list.json
    section_pattern: ''
personas:""",
        )
        config_path.write_text(config_text)

        result = runner.invoke(main, ["ingest", "legal_card_list"])
        assert result.exit_code == 0
        assert "Parsed" in result.output or "Done" in result.output

    def test_ingest_tcgdex_source(self, runner, tmp_project):
        """Ingest TCGDex card data (from pre-existing JSON)."""
        sources = tmp_project / "data" / "sources"
        card_data = {
            "fetched_at": "2025-01-01T00:00:00+00:00",
            "total_cards": 1,
            "sets_fetched": 1,
            "set_names": ["Test Set"],
            "cards": [
                {
                    "id": "test-1",
                    "name": "Pikachu ex",
                    "category": "Pokemon",
                    "hp": 200,
                    "types": ["Lightning"],
                    "stage": "Basic",
                    "attacks": [
                        {"name": "Thunderbolt", "cost": ["Lightning", "Colorless"], "damage": "120"}
                    ],
                    "set": {"name": "Test Set"},
                }
            ],
        }
        (sources / "tcgdex_cards.json").write_text(json.dumps(card_data), encoding="utf-8")

        result = runner.invoke(main, ["ingest", "card_db_pokemon"])
        assert result.exit_code == 0
        assert "Parsed" in result.output or "Done" in result.output

        # Verify intermediate markdown was created
        md = tmp_project / "data" / "intermediate" / "card_db_pokemon.md"
        assert md.exists()
        assert "Pikachu ex" in md.read_text()

    def test_ingest_compendium_source(self, runner, tmp_project):
        """Ingest Compendium rulings from pre-existing JSON."""
        sources = tmp_project / "data" / "sources"
        rulings_data = {
            "fetched_at": "2025-01-01T00:00:00+00:00",
            "total_posts": 1,
            "categories": [{"id": 1, "name": "Attacks", "parent": 0, "count": 1}],
            "posts": [
                {
                    "id": 100,
                    "title": "Thunderbolt (Pikachu ex)",
                    "content": "Q: Does Thunderbolt discard all energy?\nA: Yes.",
                    "date": "2025-01-01",
                    "category_id": 1,
                    "category_name": "Attacks",
                }
            ],
        }
        (sources / "compendium_rulings.json").write_text(json.dumps(rulings_data), encoding="utf-8")

        result = runner.invoke(main, ["ingest", "rulings_compendium"])
        assert result.exit_code == 0
        assert "Parsed" in result.output or "Done" in result.output

        md = tmp_project / "data" / "intermediate" / "rulings_compendium.md"
        assert md.exists()
        assert "Thunderbolt" in md.read_text()

    def test_ingest_skips_unchanged(self, runner, tmp_project):
        """Second ingest skips if source hash is unchanged."""
        intermediate = tmp_project / "data" / "intermediate"
        md_path = intermediate / "rulebook.md"
        md_path.write_text("# Rulebook\n## Section 1\nSome rule.", encoding="utf-8")

        sources = tmp_project / "data" / "sources"
        (sources / "pfl_rulebook_en.pdf").write_bytes(b"fake pdf")

        with patch("pokeprof_notebook.parsers.pdf.parse_pdf", return_value=md_path):
            result1 = runner.invoke(main, ["ingest", "rulebook"])
            assert result1.exit_code == 0

        with patch("pokeprof_notebook.parsers.pdf.parse_pdf", return_value=md_path):
            result2 = runner.invoke(main, ["ingest", "rulebook"])
            assert result2.exit_code == 0
            assert "Up to date" in result2.output

    def test_ingest_force_reindexes(self, runner, tmp_project):
        """--force re-indexes even if hash is unchanged."""
        intermediate = tmp_project / "data" / "intermediate"
        md_path = intermediate / "rulebook.md"
        md_path.write_text("# Rulebook\n## Section 1\nSome rule.", encoding="utf-8")

        sources = tmp_project / "data" / "sources"
        (sources / "pfl_rulebook_en.pdf").write_bytes(b"fake pdf")

        with patch("pokeprof_notebook.parsers.pdf.parse_pdf", return_value=md_path):
            result1 = runner.invoke(main, ["ingest", "rulebook"])
            assert result1.exit_code == 0

        with patch("pokeprof_notebook.parsers.pdf.parse_pdf", return_value=md_path):
            result2 = runner.invoke(main, ["ingest", "rulebook", "--force"])
            assert result2.exit_code == 0
            assert "Indexing" in result2.output
            assert "Done" in result2.output


# ── Test: fetch-cards ──


class TestFetchCards:
    def test_fetch_cards_help(self, runner):
        result = runner.invoke(main, ["fetch-cards", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output

    def test_fetch_cards_calls_api(self, runner, tmp_project):
        """fetch-cards invokes tcgdex.fetch_all_standard_cards."""
        output_path = tmp_project / "data" / "sources" / "tcgdex_cards.json"

        with patch("pokeprof_notebook.tcgdex.fetch_all_standard_cards") as mock_fetch:
            mock_fetch.return_value = output_path
            result = runner.invoke(main, ["fetch-cards"])

        assert result.exit_code == 0
        assert "Fetching" in result.output
        mock_fetch.assert_called_once_with(output_path, force=False)

    def test_fetch_cards_force_flag(self, runner, tmp_project):
        output_path = tmp_project / "data" / "sources" / "tcgdex_cards.json"

        with patch("pokeprof_notebook.tcgdex.fetch_all_standard_cards") as mock_fetch:
            mock_fetch.return_value = output_path
            result = runner.invoke(main, ["fetch-cards", "--force"])

        assert result.exit_code == 0
        mock_fetch.assert_called_once_with(output_path, force=True)

    def test_fetch_cards_handles_error(self, runner, tmp_project):
        with patch("pokeprof_notebook.tcgdex.fetch_all_standard_cards") as mock_fetch:
            mock_fetch.side_effect = RuntimeError("Connection failed")
            result = runner.invoke(main, ["fetch-cards"])

        assert result.exit_code == 1
        assert "Failed to fetch cards" in result.output


# ── Test: fetch-compendium ──


class TestFetchCompendium:
    def test_fetch_compendium_help(self, runner):
        result = runner.invoke(main, ["fetch-compendium", "--help"])
        assert result.exit_code == 0
        assert "--force" in result.output

    def test_fetch_compendium_calls_api(self, runner, tmp_project):
        output_path = tmp_project / "data" / "sources" / "compendium_rulings.json"

        with patch("pokeprof_notebook.compendium.fetch_all_rulings") as mock_fetch:
            mock_fetch.return_value = output_path
            result = runner.invoke(main, ["fetch-compendium"])

        assert result.exit_code == 0
        assert "Fetching" in result.output
        mock_fetch.assert_called_once_with(output_path, force=False)

    def test_fetch_compendium_force_flag(self, runner, tmp_project):
        output_path = tmp_project / "data" / "sources" / "compendium_rulings.json"

        with patch("pokeprof_notebook.compendium.fetch_all_rulings") as mock_fetch:
            mock_fetch.return_value = output_path
            result = runner.invoke(main, ["fetch-compendium", "--force"])

        assert result.exit_code == 0
        mock_fetch.assert_called_once_with(output_path, force=True)

    def test_fetch_compendium_handles_error(self, runner, tmp_project):
        with patch("pokeprof_notebook.compendium.fetch_all_rulings") as mock_fetch:
            mock_fetch.side_effect = RuntimeError("Connection failed")
            result = runner.invoke(main, ["fetch-compendium"])

        assert result.exit_code == 1
        assert "Failed to fetch rulings" in result.output


# ── Test: query ──


class TestQuery:
    def test_query_help(self, runner):
        result = runner.invoke(main, ["query", "--help"])
        assert result.exit_code == 0
        assert "--persona" in result.output
        assert "--no-llm" in result.output
        assert "--format" in result.output
        assert "--model" in result.output
        assert "--verbose" in result.output

    def test_query_no_api_key(self, runner, tmp_project, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = runner.invoke(main, ["query", "What is the energy rule?"])
        assert result.exit_code == 1
        assert "ANTHROPIC_API_KEY" in result.output

    def test_query_no_api_key_ok_with_no_llm(self, runner, tmp_project, monkeypatch):
        """--no-llm should not require ANTHROPIC_API_KEY (but will fail on missing indexes)."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = runner.invoke(main, ["query", "some rule", "--no-llm"])
        # Exits 1 because no indexes, but doesn't complain about API key
        assert result.exit_code == 1
        assert "ANTHROPIC_API_KEY" not in result.output

    def test_query_no_indexes(self, runner, tmp_project, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        result = runner.invoke(main, ["query", "What is the rule?", "--no-llm"])
        assert result.exit_code == 1
        assert "No indexes found" in result.output or "Index not found" in result.output

    def test_query_no_llm_with_index(self, runner, tmp_project, monkeypatch):
        """--no-llm mode returns raw sections without calling Anthropic."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        indexes_dir = tmp_project / "data" / "indexes"
        _write_index(indexes_dir, "rulebook", DocumentType.RULEBOOK, "Energy Attachment")

        result = runner.invoke(main, ["query", "energy rule", "--no-llm"])
        assert result.exit_code == 0
        assert "Energy Attachment" in result.output

    def test_query_json_output(self, runner, tmp_project, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        indexes_dir = tmp_project / "data" / "indexes"
        _write_index(indexes_dir, "rulebook", DocumentType.RULEBOOK, "Energy Attachment")

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Energy rule answer")]

        # Mock retriever LLM (tree descent) to select child 0
        retriever_msg = MagicMock()
        retriever_msg.content = [MagicMock(text="0")]

        with (
            patch("pokeprof_notebook.synthesizer.Anthropic") as mock_synth,
            patch("pokeprof_notebook.retriever.Anthropic") as mock_retr,
        ):
            mock_synth.return_value.messages.create.return_value = mock_message
            mock_retr.return_value.messages.create.return_value = retriever_msg
            result = runner.invoke(
                main, ["query", "energy rule", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["query"] == "energy rule"
        assert data["persona"] == "judge"
        assert "answer" in data
        assert "sections" in data
        assert "routing" in data

    def test_query_markdown_output(self, runner, tmp_project, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        indexes_dir = tmp_project / "data" / "indexes"
        _write_index(indexes_dir, "rulebook", DocumentType.RULEBOOK, "Energy Attachment")

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Energy rule answer")]

        retriever_msg = MagicMock()
        retriever_msg.content = [MagicMock(text="0")]

        with (
            patch("pokeprof_notebook.synthesizer.Anthropic") as mock_synth,
            patch("pokeprof_notebook.retriever.Anthropic") as mock_retr,
        ):
            mock_synth.return_value.messages.create.return_value = mock_message
            mock_retr.return_value.messages.create.return_value = retriever_msg
            result = runner.invoke(
                main, ["query", "energy rule", "--format", "markdown"]
            )

        assert result.exit_code == 0
        assert "*Sections:" in result.output
        assert "Energy rule answer" in result.output

    def test_query_persona_option(self, runner, tmp_project, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        indexes_dir = tmp_project / "data" / "indexes"
        _write_index(indexes_dir, "rulebook", DocumentType.RULEBOOK, "Energy Attachment")

        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="Professor explanation")]

        retriever_msg = MagicMock()
        retriever_msg.content = [MagicMock(text="0")]

        with (
            patch("pokeprof_notebook.synthesizer.Anthropic") as mock_synth,
            patch("pokeprof_notebook.retriever.Anthropic") as mock_retr,
        ):
            mock_synth.return_value.messages.create.return_value = mock_message
            mock_retr.return_value.messages.create.return_value = retriever_msg
            result = runner.invoke(
                main, ["query", "energy rule", "--persona", "professor", "--format", "json"]
            )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["persona"] == "professor"

    def test_query_verbose_flag(self, runner, tmp_project, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        indexes_dir = tmp_project / "data" / "indexes"
        _write_index(indexes_dir, "rulebook", DocumentType.RULEBOOK, "Energy Attachment")

        result = runner.invoke(main, ["query", "energy rule", "--no-llm", "-v"])
        assert result.exit_code == 0
        assert "Route Decision" in result.output
        assert "Retrieved Sections" in result.output

    def test_query_no_relevant_sections(self, runner, tmp_project, monkeypatch):
        """Query that routes to an index but finds no matching sections."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        indexes_dir = tmp_project / "data" / "indexes"
        # Create an index with content that won't match the query
        _write_index(indexes_dir, "rulebook", DocumentType.RULEBOOK, "Completely Unrelated Topic")

        result = runner.invoke(main, ["query", "xyzzy nonsense gibberish", "--no-llm"])
        assert result.exit_code == 1
        assert "No relevant sections found" in result.output


# ── Test: serve ──


class TestServe:
    def test_serve_help(self, runner):
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--host" in result.output
        assert "--port" in result.output
        assert "--reload" in result.output

    def test_serve_calls_uvicorn(self, runner, tmp_project):
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(main, ["serve", "--port", "9999"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            "pokeprof_notebook.server:app",
            host="127.0.0.1",
            port=9999,
            reload=False,
        )

    def test_serve_custom_host(self, runner, tmp_project):
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(main, ["serve", "--host", "127.0.0.1", "--port", "3000"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            "pokeprof_notebook.server:app",
            host="127.0.0.1",
            port=3000,
            reload=False,
        )

    def test_serve_reload_flag(self, runner, tmp_project):
        with patch("uvicorn.run") as mock_run:
            result = runner.invoke(main, ["serve", "--reload"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(
            "pokeprof_notebook.server:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
        )


# ── Test: command registration ──


class TestCommandRegistration:
    """Verify all expected commands are registered on the CLI group."""

    EXPECTED_COMMANDS = ["ingest", "query", "serve", "fetch-cards", "fetch-compendium"]

    def test_all_commands_registered(self):
        registered = list(main.commands.keys())
        for cmd in self.EXPECTED_COMMANDS:
            assert cmd in registered, f"Command '{cmd}' not registered"

    def test_no_unexpected_commands(self):
        registered = set(main.commands.keys())
        expected = set(self.EXPECTED_COMMANDS)
        unexpected = registered - expected
        assert not unexpected, f"Unexpected commands registered: {unexpected}"

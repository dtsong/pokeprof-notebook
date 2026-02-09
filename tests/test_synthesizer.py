"""Tests for the answer synthesizer module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from anthropic import APIConnectionError

from pokeprof_notebook.synthesizer import (
    _ancestry_trail,
    _build_context,
    _build_messages,
    _is_card_section,
    synthesize,
)
from pokeprof_notebook.types import DocumentType
from conftest import make_node, make_section


# ── TestAncestryTrail ──


class TestAncestryTrail:
    @pytest.mark.parametrize(
        "section_number,title,node_id,expected",
        [
            ("1.2", "Energy", "n", "1.2. Energy"),
            ("3", "", "n", "3"),
            ("", "Overview", "n", "Overview"),
            ("", "", "my_node", "my_node"),
        ],
    )
    def test_ancestry_trail(self, section_number, title, node_id, expected):
        node = make_node(id=node_id, section_number=section_number, title=title)
        assert _ancestry_trail(node) == expected


# ── TestIsCardSection ──


class TestIsCardSection:
    def test_card_database_returns_true(self):
        section = make_section(
            node=make_node(document_type=DocumentType.CARD_DATABASE)
        )
        assert _is_card_section(section) is True

    def test_rulebook_returns_false(self):
        section = make_section(
            node=make_node(document_type=DocumentType.RULEBOOK)
        )
        assert _is_card_section(section) is False


# ── TestBuildContext ──


class TestBuildContext:
    def test_cards_ordered_before_rules(self):
        rules = make_section(
            node=make_node(
                id="r1", content="Rule text", document_type=DocumentType.RULEBOOK,
                section_number="1", title="Rules",
            )
        )
        card = make_section(
            node=make_node(
                id="c1", content="Card text", document_type=DocumentType.CARD_DATABASE,
                section_number="C1", title="Pikachu",
            )
        )
        # Pass rules first, cards second — cards should still appear first
        result = _build_context([rules, card], token_budget=6000)
        card_pos = result.index("Card text")
        rules_pos = result.index("Rule text")
        assert card_pos < rules_pos

    def test_type_headers_present_for_mixed_sections(self):
        card = make_section(
            node=make_node(
                id="c1", content="Card text", document_type=DocumentType.CARD_DATABASE,
            )
        )
        rules = make_section(
            node=make_node(
                id="r1", content="Rule text", document_type=DocumentType.RULEBOOK,
            )
        )
        result = _build_context([card, rules], token_budget=6000)
        assert "=== CARD TEXT ===" in result
        assert "=== GAME RULES ===" in result

    def test_token_budget_truncation(self):
        section = make_section(
            node=make_node(
                id="big", content="word " * 500,
                section_number="1", title="Big Section",
            )
        )
        result = _build_context([section], token_budget=100)
        assert "[...truncated]" in result

    def test_errata_context_appended(self):
        section = make_section(
            node=make_node(
                id="e1", content="Card text",
                document_type=DocumentType.CARD_DATABASE,
                section_number="E1", title="Errata Card",
            ),
            errata_context=["This card now says 'draw 2' instead of 'draw 3'."],
        )
        result = _build_context([section], token_budget=6000)
        assert "CARD ERRATA" in result
        assert "draw 2" in result

    def test_empty_sections_returns_empty(self):
        result = _build_context([], token_budget=6000)
        assert result == ""

    def test_compendium_sections_appear_last(self):
        compendium = make_section(
            node=make_node(
                id="comp1", content="Compendium ruling",
                document_type=DocumentType.RULINGS_COMPENDIUM,
                section_number="R1", title="Ruling",
            )
        )
        rules = make_section(
            node=make_node(
                id="r1", content="Rule text",
                document_type=DocumentType.RULEBOOK,
                section_number="1", title="Rules",
            )
        )
        card = make_section(
            node=make_node(
                id="c1", content="Card text",
                document_type=DocumentType.CARD_DATABASE,
                section_number="C1", title="Card",
            )
        )
        # Pass in compendium first — it should still appear last
        result = _build_context([compendium, rules, card], token_budget=6000)
        card_pos = result.index("Card text")
        rules_pos = result.index("Rule text")
        comp_pos = result.index("Compendium ruling")
        assert card_pos < rules_pos < comp_pos


# ── TestBuildMessages ──


class TestBuildMessages:
    def test_card_sections_use_card_framing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pokeprof_notebook.synthesizer.get_project_root", lambda: tmp_path
        )
        card = make_section(
            node=make_node(
                id="c1", content="Card text",
                document_type=DocumentType.CARD_DATABASE,
                section_number="C1", title="Card",
            )
        )
        _, user_msg = _build_messages("What does this card do?", [card], "judge")
        assert "card data and rule sections" in user_msg

    def test_rules_only_use_rules_framing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pokeprof_notebook.synthesizer.get_project_root", lambda: tmp_path
        )
        rules = make_section(
            node=make_node(
                id="r1", content="Rule text",
                document_type=DocumentType.RULEBOOK,
                section_number="1", title="Rules",
            )
        )
        _, user_msg = _build_messages("How does retreat work?", [rules], "judge")
        assert "rule sections" in user_msg
        assert "card data" not in user_msg

    def test_empty_sections_returns_empty_user_message(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pokeprof_notebook.synthesizer.get_project_root", lambda: tmp_path
        )
        system, user_msg = _build_messages("anything", [], "judge")
        assert user_msg == ""
        assert system  # system prompt should still be present


# ── TestSynthesize ──


class TestSynthesize:
    def test_returns_answer_text(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pokeprof_notebook.synthesizer.get_project_root", lambda: tmp_path
        )
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="The answer is 42.")]
        mock_client.messages.create.return_value = mock_message

        with patch("pokeprof_notebook.synthesizer.Anthropic", return_value=mock_client):
            section = make_section(
                node=make_node(id="r1", content="Rule content", section_number="1", title="Rule")
            )
            result = synthesize("What is the answer?", [section])
        assert result == "The answer is 42."

    def test_empty_sections_returns_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pokeprof_notebook.synthesizer.get_project_root", lambda: tmp_path
        )
        result = synthesize("any question", [])
        assert "couldn't find relevant rule sections" in result

    def test_api_error_propagates(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pokeprof_notebook.synthesizer.get_project_root", lambda: tmp_path
        )
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = APIConnectionError(request=MagicMock())

        with patch("pokeprof_notebook.synthesizer.Anthropic", return_value=mock_client):
            section = make_section(
                node=make_node(id="r1", content="Rule content", section_number="1", title="Rule")
            )
            with pytest.raises(APIConnectionError):
                synthesize("What is the answer?", [section])

    def test_empty_llm_response_returns_fallback(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "pokeprof_notebook.synthesizer.get_project_root", lambda: tmp_path
        )
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = []
        mock_client.messages.create.return_value = mock_message

        with patch("pokeprof_notebook.synthesizer.Anthropic", return_value=mock_client):
            section = make_section(
                node=make_node(id="r1", content="Rule content", section_number="1", title="Rule")
            )
            result = synthesize("What is the answer?", [section])
        assert "unable to generate an answer" in result

"""Tests for pokeprof_notebook.retriever — tree search, cross-references, card lookup."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from anthropic import APIConnectionError, AuthenticationError

from pokeprof_notebook.retriever import (
    _build_lookup,
    _keyword_select_children,
    detect_cross_doc_references,
    resolve_cross_references,
    search,
    search_by_card_names,
)
from pokeprof_notebook.types import DocumentType

from conftest import make_index, make_node, make_section


# ── Build lookup ──


class TestBuildLookup:
    def test_builds_section_number_to_node_dict(self):
        child = make_node(id="1", section_number="1", title="One")
        root = make_node(id="root", children=[child])
        index = make_index(root=root)
        lookup = _build_lookup(index)
        assert "1" in lookup
        assert lookup["1"] is child

    def test_skips_nodes_with_empty_section_number(self):
        child = make_node(id="x", section_number="", title="No Number")
        root = make_node(id="root", children=[child])
        index = make_index(root=root)
        lookup = _build_lookup(index)
        assert "x" not in lookup
        assert "" not in lookup

    def test_nested_tree_builds_complete_lookup(self, sample_tree):
        index = make_index(root=sample_tree)
        lookup = _build_lookup(index)
        assert "1" in lookup
        assert "2" in lookup
        assert "1.1" in lookup
        assert "1.2" in lookup
        assert "2.1" in lookup
        assert "2.2" in lookup


# ── Keyword child selection ──


class TestKeywordSelectChildren:
    def test_matches_children_by_keyword(self):
        c1 = make_node(id="a", content="energy rules apply", title="Energy")
        c2 = make_node(id="b", content="retreat cost info", title="Retreat")
        parent = make_node(id="root", children=[c1, c2])
        result = _keyword_select_children(parent, "energy")
        assert len(result) == 1
        assert result[0].id == "a"

    def test_returns_at_most_three_results(self):
        children = [
            make_node(id=str(i), content="attack damage rules", title=f"Section {i}")
            for i in range(6)
        ]
        parent = make_node(id="root", children=children)
        result = _keyword_select_children(parent, "attack damage rules")
        assert len(result) <= 3

    def test_no_match_returns_empty(self):
        c1 = make_node(id="a", content="water type", title="Water")
        parent = make_node(id="root", children=[c1])
        result = _keyword_select_children(parent, "xyznonexistent")
        assert result == []

    def test_case_insensitive_matching(self):
        c1 = make_node(id="a", content="ENERGY rules", title="Energy Rules")
        parent = make_node(id="root", children=[c1])
        result = _keyword_select_children(parent, "energy")
        assert len(result) == 1
        assert result[0].id == "a"


# ── Keyword search (integration via search()) ──


class TestSearchWithKeywords:
    def test_finds_matching_leaf(self):
        child = make_node(
            id="1", content="energy attachment rules", section_number="1",
            title="Energy", token_count=5,
        )
        root = make_node(id="root", children=[child])
        index = make_index(root=root)
        results = search("energy", index, use_llm=False)
        assert len(results) >= 1
        assert results[0].node.id == "1"

    def test_skips_root_node(self):
        root = make_node(id="root", content="energy mentioned here", children=[])
        index = make_index(root=root)
        results = search("energy", index, use_llm=False)
        assert all(r.node.id != "root" for r in results)

    def test_scores_by_word_overlap(self):
        c1 = make_node(
            id="1", content="energy attachment", section_number="1",
            title="Energy", token_count=3,
        )
        c2 = make_node(
            id="2", content="energy attachment retreat cost weakness",
            section_number="2", title="Full", token_count=5,
        )
        root = make_node(id="root", children=[c1, c2])
        index = make_index(root=root)
        results = search("energy attachment retreat", index, use_llm=False)
        assert len(results) >= 2
        # c2 matches all 3 words, c1 matches 2 — c2 should score higher
        assert results[0].node.id == "2"

    def test_respects_max_sections_limit(self):
        children = [
            make_node(
                id=str(i), content="energy rules apply", section_number=str(i),
                title=f"Section {i}", token_count=3,
            )
            for i in range(10)
        ]
        root = make_node(id="root", children=children)
        index = make_index(root=root)
        results = search("energy rules", index, max_sections=2, use_llm=False)
        assert len(results) <= 2


# ── LLM search ──


class TestSearchWithLLM:
    def _make_two_child_index(self):
        c1 = make_node(
            id="1", content="energy attachment rules", section_number="1",
            title="Energy", token_count=5,
        )
        c2 = make_node(
            id="2", content="retreat cost rules", section_number="2",
            title="Retreat", token_count=5,
        )
        root = make_node(id="root", children=[c1, c2])
        return make_index(root=root)

    @patch("pokeprof_notebook.retriever.Anthropic")
    def test_llm_selects_child(self, mock_anthropic_cls):
        client = MagicMock()
        message = MagicMock()
        message.content = [MagicMock(text="0")]
        client.messages.create.return_value = message
        mock_anthropic_cls.return_value = client

        index = self._make_two_child_index()
        results = search("energy", index, use_llm=True)
        assert len(results) >= 1
        assert results[0].node.id == "1"

    @patch("pokeprof_notebook.retriever.Anthropic")
    def test_unparseable_llm_response_falls_back_to_keywords(self, mock_anthropic_cls):
        client = MagicMock()
        message = MagicMock()
        message.content = [MagicMock(text="I don't understand the question")]
        client.messages.create.return_value = message
        mock_anthropic_cls.return_value = client

        index = self._make_two_child_index()
        results = search("energy", index, use_llm=True)
        # Should still produce results via keyword fallback
        assert len(results) >= 1

    @patch("pokeprof_notebook.retriever.Anthropic")
    def test_api_connection_error_falls_back_to_keywords(self, mock_anthropic_cls):
        client = MagicMock()
        client.messages.create.side_effect = APIConnectionError(request=MagicMock())
        mock_anthropic_cls.return_value = client

        index = self._make_two_child_index()
        results = search("energy", index, use_llm=True)
        assert len(results) >= 1

    @patch("pokeprof_notebook.retriever.Anthropic")
    def test_authentication_error_is_reraised(self, mock_anthropic_cls):
        client = MagicMock()
        client.messages.create.side_effect = AuthenticationError(
            message="bad key", response=MagicMock(), body=None,
        )
        mock_anthropic_cls.return_value = client

        index = self._make_two_child_index()
        with pytest.raises(AuthenticationError):
            search("energy", index, use_llm=True)


# ── Cross-reference resolution ──


class TestResolveCrossReferences:
    def test_resolves_see_section_reference(self):
        ref_node = make_node(id="1.2", content="Referenced content", section_number="1.2", title="Ref")
        source_node = make_node(id="1", content="See section 1.2 for details.", section_number="1", title="Source")
        lookup = {"1.2": ref_node}
        sections = [make_section(node=source_node)]
        result = resolve_cross_references(sections, lookup, "rulebook")
        assert len(result) == 2
        assert result[1].node.id == "1.2"
        assert result[1].score == 0.5

    def test_no_duplicate_refs(self):
        ref_node = make_node(id="1.2", content="Referenced", section_number="1.2", title="Ref")
        source = make_node(id="1", content="See section 1.2 for details.", section_number="1", title="Source")
        lookup = {"1.2": ref_node}
        # ref_node is already in sections
        sections = [make_section(node=source), make_section(node=ref_node)]
        result = resolve_cross_references(sections, lookup, "rulebook")
        ids = [r.node.id for r in result]
        assert ids.count("1.2") == 1

    def test_respects_max_sections(self):
        refs = []
        for i in range(10):
            refs.append(make_node(
                id=f"ref_{i}", content=f"Ref {i}", section_number=f"99.{i}", title=f"Ref {i}",
            ))
        content_parts = " ".join(f"See section 99.{i}." for i in range(10))
        source = make_node(id="1", content=content_parts, section_number="1", title="Source")
        lookup = {f"99.{i}": refs[i] for i in range(10)}
        sections = [make_section(node=source)]
        result = resolve_cross_references(sections, lookup, "rulebook", max_sections=3)
        assert len(result) <= 3

    def test_no_cross_refs_returns_unchanged(self):
        source = make_node(id="1", content="No references here.", section_number="1", title="Source")
        sections = [make_section(node=source)]
        result = resolve_cross_references(sections, {}, "rulebook")
        assert result == sections


# ── Cross-document reference detection ──


class TestDetectCrossDocReferences:
    def test_detects_see_the_rulebook(self):
        node = make_node(id="1", content="For more detail, see the rulebook.", title="Section")
        sections = [make_section(node=node, document_name="penalty_guidelines")]
        refs = detect_cross_doc_references(sections)
        assert "rulebook" in refs

    def test_detects_penalty_guidelines(self):
        node = make_node(id="1", content="As defined in the penalty guidelines.", title="Section")
        sections = [make_section(node=node, document_name="rulebook")]
        refs = detect_cross_doc_references(sections)
        assert "penalty_guidelines" in refs

    def test_no_matches_returns_empty_set(self):
        node = make_node(id="1", content="No cross-doc references at all.", title="Section")
        sections = [make_section(node=node, document_name="rulebook")]
        refs = detect_cross_doc_references(sections)
        assert refs == set()


# ── Card name search ──


class TestSearchByCardNames:
    def test_finds_node_with_matching_title(self):
        child = make_node(id="pika", content="Electric mouse", title="Pikachu", token_count=3)
        root = make_node(id="root", children=[child])
        index = make_index(root=root, document_name="card_db_pokemon")
        results = search_by_card_names(["Pikachu"], index)
        assert len(results) == 1
        assert results[0].node.id == "pika"
        assert results[0].score == 2.0

    def test_case_insensitive_lookup(self):
        child = make_node(id="pika", content="Electric mouse", title="Pikachu", token_count=3)
        root = make_node(id="root", children=[child])
        index = make_index(root=root, document_name="card_db_pokemon")
        results = search_by_card_names(["pikachu"], index)
        assert len(results) == 1

    def test_no_match_returns_empty(self):
        child = make_node(id="pika", content="Electric mouse", title="Pikachu", token_count=3)
        root = make_node(id="root", children=[child])
        index = make_index(root=root, document_name="card_db_pokemon")
        results = search_by_card_names(["Charizard"], index)
        assert results == []

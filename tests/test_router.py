"""Tests for pokeprof_notebook.router — query routing and classification."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pokeprof_notebook.router import (
    _detect_card_names,
    _has_interaction_intent,
    _is_ambiguous,
    _llm_classify,
    classify,
    route,
)


class TestClassify:
    """Keyword-based query classification."""

    @pytest.mark.parametrize(
        "query, expected",
        [
            ("penalty for slow play", "penalty"),
            ("is this card legal in standard", "format_legality"),
            ("what is the errata for this card", "card_specific"),
            ("how does retreat work", "rules_lookup"),
        ],
    )
    def test_keyword_classification(self, query, expected, reset_router_cache):
        assert classify(query) == expected

    def test_card_interaction_with_two_cards(self, monkeypatch, reset_router_cache):
        import pokeprof_notebook.router as router_mod

        monkeypatch.setattr(
            router_mod,
            "_get_card_name_index",
            lambda: {"pikachu ex": "card_db_pokemon", "charizard ex": "card_db_pokemon"},
        )
        result = classify("pikachu ex and charizard ex")
        assert result == "card_interaction"


class TestDetectCardNames:
    """Card name detection with word-boundary and longest-match logic."""

    def test_finds_known_card(self, monkeypatch, reset_router_cache):
        import pokeprof_notebook.router as router_mod

        monkeypatch.setattr(
            router_mod, "_get_card_name_index", lambda: {"pikachu ex": "card_db_pokemon"}
        )
        result = _detect_card_names("What does Pikachu ex do?")
        assert len(result) == 1
        assert result[0] == ("pikachu ex", "card_db_pokemon")

    def test_word_boundary_rejects_substring(self, monkeypatch, reset_router_cache):
        import pokeprof_notebook.router as router_mod

        monkeypatch.setattr(router_mod, "_get_card_name_index", lambda: {"ex": "card_db_pokemon"})
        result = _detect_card_names("hex maniac is powerful")
        assert result == []

    def test_longest_match_first(self, monkeypatch, reset_router_cache):
        import pokeprof_notebook.router as router_mod

        monkeypatch.setattr(
            router_mod,
            "_get_card_name_index",
            lambda: {"pikachu ex": "card_db_pokemon", "ex": "card_db_pokemon"},
        )
        result = _detect_card_names("pikachu ex is strong")
        names = [name for name, _ in result]
        assert "pikachu ex" in names
        assert "ex" not in names

    def test_no_overlap_in_matched_ranges(self, monkeypatch, reset_router_cache):
        import pokeprof_notebook.router as router_mod

        monkeypatch.setattr(
            router_mod,
            "_get_card_name_index",
            lambda: {"pikachu ex": "card_db_pokemon", "pikachu": "card_db_pokemon"},
        )
        result = _detect_card_names("pikachu ex is great")
        assert len(result) == 1
        assert result[0][0] == "pikachu ex"

    def test_empty_index_returns_empty(self, monkeypatch, reset_router_cache):
        import pokeprof_notebook.router as router_mod

        monkeypatch.setattr(router_mod, "_get_card_name_index", lambda: {})
        assert _detect_card_names("pikachu ex") == []

    def test_case_insensitive(self, monkeypatch, reset_router_cache):
        import pokeprof_notebook.router as router_mod

        monkeypatch.setattr(
            router_mod, "_get_card_name_index", lambda: {"pikachu ex": "card_db_pokemon"}
        )
        result = _detect_card_names("PIKACHU EX is my favourite")
        assert len(result) == 1


class TestHasInteractionIntent:
    """Interaction keyword detection."""

    def test_interaction_keyword_detected(self):
        assert _has_interaction_intent("how does Pikachu interact with energy") is True

    def test_no_interaction_keyword(self):
        assert _has_interaction_intent("what is the retreat cost") is False


class TestIsAmbiguous:
    """Ambiguity threshold checks on keyword score dicts."""

    def test_empty_scores_is_ambiguous(self):
        assert _is_ambiguous({}) is True

    def test_low_top_score_is_ambiguous(self):
        assert _is_ambiguous({"rulebook": 0.5, "penalty_guidelines": 0.3}) is True

    def test_close_scores_is_ambiguous(self):
        assert _is_ambiguous({"rulebook": 2.0, "penalty_guidelines": 1.8}) is True

    def test_clear_winner_not_ambiguous(self):
        assert _is_ambiguous({"rulebook": 3.0, "penalty_guidelines": 1.0}) is False


class TestRoute:
    """End-to-end route() decision tests."""

    def test_penalty_query_routes_to_penalty_guidelines(self, sample_config, reset_router_cache):
        decision = route("penalty for slow play", sample_config)
        assert decision.documents[0] == "penalty_guidelines"

    def test_player_persona_lowers_penalty_score(self, sample_config, reset_router_cache):
        judge_decision = route("penalty for slow play", sample_config, persona="judge")
        player_decision = route("penalty for slow play", sample_config, persona="player")
        judge_idx = judge_decision.documents.index("penalty_guidelines")
        player_idx = player_decision.documents.index("penalty_guidelines")
        assert player_idx >= judge_idx

    def test_card_names_populated(self, monkeypatch, sample_config, reset_router_cache):
        import pokeprof_notebook.router as router_mod

        monkeypatch.setattr(
            router_mod,
            "_get_card_name_index",
            lambda: {"pikachu ex": "card_db_pokemon"},
        )
        decision = route("how does pikachu ex attack", sample_config)
        assert "pikachu ex" in decision.card_names

    def test_confidence_between_zero_and_one(self, sample_config, reset_router_cache):
        decision = route("how does retreat work", sample_config)
        assert 0.0 <= decision.confidence <= 1.0

    def test_returns_route_decision(self, sample_config, reset_router_cache):
        from pokeprof_notebook.types import RouteDecision

        decision = route("basic rules question", sample_config)
        assert isinstance(decision, RouteDecision)


class TestLLMClassify:
    """LLM-based classification with mocked Anthropic client."""

    def test_valid_type_returned_and_cached(self, monkeypatch, reset_router_cache):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="penalty")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch("anthropic.Anthropic", return_value=mock_client):
            result = _llm_classify("what penalty for slow play")
            assert result == "penalty"

    def test_invalid_type_returns_none(self, monkeypatch, reset_router_cache):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="unknown_type")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch("anthropic.Anthropic", return_value=mock_client):
            result = _llm_classify("ambiguous question")
            assert result is None

    def test_no_api_key_returns_none(self, monkeypatch, reset_router_cache):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = _llm_classify("some query")
        assert result is None

    def test_result_cached_on_second_call(self, monkeypatch, reset_router_cache):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text="rules_lookup")]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_msg

        with patch("anthropic.Anthropic", return_value=mock_client):
            first = _llm_classify("how does retreat work")
            second = _llm_classify("how does retreat work")
            assert first == second == "rules_lookup"
            assert mock_client.messages.create.call_count == 1

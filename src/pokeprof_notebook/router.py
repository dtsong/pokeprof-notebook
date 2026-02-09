"""Query router for PokéProf Notebook.

Keyword-based routing that classifies queries and routes them to the
correct document(s) using routing_hints from domain_config.yaml.
Optionally uses LLM classification for ambiguous queries.
Card name detection via card_name_index.json for direct card routing.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from pokeprof_notebook.config import get_project_root
from pokeprof_notebook.types import DomainConfig, RouteDecision

logger = logging.getLogger(__name__)

_AMBIGUITY_THRESHOLD = 1.0

_INTERACTION_KEYWORDS = [
    "how does",
    "play off",
    "interact",
    "affect",
    "work with",
    "work together",
    "prevent",
    "block",
    "stack",
    "combo",
    "combined",
    "does it",
    "override",
    "negate",
]


def _load_card_name_index() -> dict[str, str]:
    """Load card_name_index.json mapping lowercase name -> doc name.

    Returns an empty dict if the index file doesn't exist yet.
    """
    index_path = get_project_root() / "data" / "indexes" / "card_name_index.json"
    if not index_path.exists():
        return {}
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.warning("Failed to load card name index", exc_info=True)
        return {}


# Cache the card name index with mtime tracking
_card_name_index: dict[str, str] | None = None
_card_name_index_mtime: float = 0.0


def _get_card_name_index() -> dict[str, str]:
    global _card_name_index, _card_name_index_mtime
    index_path = get_project_root() / "data" / "indexes" / "card_name_index.json"
    try:
        current_mtime = index_path.stat().st_mtime if index_path.exists() else 0.0
    except OSError:
        current_mtime = 0.0
    if _card_name_index is None or current_mtime != _card_name_index_mtime:
        _card_name_index = _load_card_name_index()
        _card_name_index_mtime = current_mtime
    return _card_name_index


def _detect_card_names(query: str) -> list[tuple[str, str]]:
    """Return (card_name, doc_name) pairs for any card names found in query.

    Uses longest-match-first to avoid partial matches (e.g. "Ogerpon ex"
    should match before just "ex" if both exist).
    """
    card_index = _get_card_name_index()
    if not card_index:
        return []

    q = query.lower()
    # Sort by name length descending for longest-match-first
    sorted_names = sorted(card_index.keys(), key=len, reverse=True)

    matches: list[tuple[str, str]] = []
    matched_ranges: list[tuple[int, int]] = []

    for name in sorted_names:
        start = q.find(name)
        if start == -1:
            continue
        end = start + len(name)
        # Word boundary check — reject substring matches
        if start > 0 and q[start - 1].isalnum():
            continue
        if end < len(q) and q[end].isalnum():
            continue
        # Check no overlap with already matched ranges
        if any(
            not (end <= mr_start or start >= mr_end)
            for mr_start, mr_end in matched_ranges
        ):
            continue
        matches.append((name, card_index[name]))
        matched_ranges.append((start, end))

    return matches


def _has_interaction_intent(query: str) -> bool:
    """Check if the query asks about card interactions."""
    q = query.lower()
    return any(kw in q for kw in _INTERACTION_KEYWORDS)


def classify(query: str) -> str:
    """Classify query type based on keyword patterns.

    Returns one of: rules_lookup, penalty, card_specific,
    format_legality, card_interaction.
    """
    q = query.lower()

    penalty_keywords = [
        "penalty",
        "infraction",
        "marked card",
        "game loss",
        "warning",
        "disqualif",
        "slow play",
        "deck error",
        "drawing extra",
        "unsporting",
        "caution",
    ]
    format_keywords = [
        "legal",
        "banned",
        "standard",
        "expanded",
        "format",
        "rotation",
        "allowed",
        "playable",
    ]
    card_keywords = ["errata", "card text", "errata'd"]

    if any(kw in q for kw in penalty_keywords):
        return "penalty"
    if any(kw in q for kw in format_keywords):
        return "format_legality"
    if any(kw in q for kw in card_keywords):
        return "card_specific"

    # Check for card interaction queries
    card_matches = _detect_card_names(q)
    if card_matches and _has_interaction_intent(q):
        return "card_interaction"
    if len(card_matches) >= 2:
        return "card_interaction"

    return "rules_lookup"


_llm_classify_cache: dict[tuple[str, str], str] = {}


def _llm_classify(
    query: str, model: str = "claude-haiku-4-5-20251001"
) -> str | None:
    """Use LLM to classify an ambiguous query.

    Caches successful results only — failures are not cached so they
    can be retried on the next call.
    """
    cache_key = (query, model)
    if cache_key in _llm_classify_cache:
        return _llm_classify_cache[cache_key]

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None

    try:
        from anthropic import Anthropic, APIConnectionError, APIStatusError, AuthenticationError

        client = Anthropic()
        message = client.messages.create(
            model=model,
            system=(
                "You classify Pokémon TCG rules questions. "
                "Respond with ONLY one of these types:\n"
                "- rules_lookup: game mechanics, general rules\n"
                "- penalty: infractions, penalties, warnings, judge calls\n"
                "- format_legality: legal cards, banned cards, standard/expanded format\n"
                "- card_specific: card errata, specific card text questions\n"
                "- card_interaction: how two or more specific cards interact, "
                "ability/attack interactions, energy interactions with cards\n"
                "Respond with just the type, nothing else."
            ),
            messages=[
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=20,
        )
        result = (message.content[0].text or "").strip().lower()
        valid_types = {
            "rules_lookup",
            "penalty",
            "format_legality",
            "card_specific",
            "card_interaction",
        }
        if result in valid_types:
            _llm_classify_cache[cache_key] = result
            return result
        return None
    except AuthenticationError:
        raise
    except (APIConnectionError, APIStatusError) as e:
        logger.warning("LLM classification failed (%s), falling back to keywords", e)
        return None


def _is_ambiguous(scores: dict[str, float]) -> bool:
    """Check if keyword scores indicate an ambiguous query."""
    if not scores:
        return True
    ranked = sorted(scores.values(), reverse=True)
    top = ranked[0]
    if top <= _AMBIGUITY_THRESHOLD:
        return True
    return len(ranked) >= 2 and (ranked[0] - ranked[1]) <= 0.5


def route(
    query: str,
    config: DomainConfig,
    persona: str = "judge",
    use_llm: bool = False,
    model: str = "claude-haiku-4-5-20251001",
) -> RouteDecision:
    """Route a query to the appropriate document(s).

    Scores each document by counting keyword hits from routing_hints,
    then applies persona bias, query type bias, and card name detection.
    """
    q = query.lower()

    # Score each document by keyword hits
    keyword_scores: dict[str, float] = {}
    for doc_name, keywords in config.routing_hints.items():
        score = sum(1.0 for kw in keywords if kw.lower() in q)
        keyword_scores[doc_name] = score

    # Card name detection — boost matched card_db documents
    card_matches = _detect_card_names(query)
    detected_card_names = [name for name, _ in card_matches]
    matched_docs = list({doc for _, doc in card_matches})

    for doc_name in matched_docs:
        if doc_name in keyword_scores:
            keyword_scores[doc_name] += 3.0

    # If card names detected and interaction intent, boost rules + compendium
    if card_matches and _has_interaction_intent(query):
        if "rulebook" in keyword_scores:
            keyword_scores["rulebook"] += 1.0
        if "rulings_compendium" in keyword_scores:
            keyword_scores["rulings_compendium"] += 2.0

    # Determine query type
    query_type = classify(query)
    llm_used = False

    if use_llm and _is_ambiguous(keyword_scores):
        llm_type = _llm_classify(query, model)
        if llm_type:
            query_type = llm_type
            llm_used = True

    scores = dict(keyword_scores)

    # Apply persona bias
    persona_bias: dict[str, dict[str, float]] = {
        "judge": {
            "rulebook": 0.5,
            "penalty_guidelines": 0.5,
        },
        "professor": {
            "rulebook": 0.5,
            "penalty_guidelines": 0.3,
        },
        "player": {
            "rulebook": 0.5,
            "penalty_guidelines": -0.5,
        },
    }
    bias = persona_bias.get(persona, {})
    for doc_name in scores:
        scores[doc_name] += bias.get(doc_name, 0)

    # Apply query type bias
    type_bias: dict[str, dict[str, float]] = {
        "penalty": {"penalty_guidelines": 2.0},
        "rules_lookup": {"rulebook": 1.0},
        "format_legality": {"legal_card_list": 2.0},
        "card_specific": {"rulebook": 0.5},
        "card_interaction": {
            "rulebook": 1.0,
            "rulings_compendium": 1.5,
        },
    }
    for doc_name, boost in type_bias.get(query_type, {}).items():
        if doc_name in scores:
            scores[doc_name] += boost

    # Rank documents by score
    ranked = sorted(scores.items(), key=lambda x: -x[1])
    documents = [name for name, score in ranked if score > 0]

    if not documents:
        max_score = ranked[0][1] if ranked else 0
        documents = [name for name, score in ranked if score == max_score]

    # Confidence
    if len(ranked) >= 2:
        top_score = ranked[0][1]
        total = sum(max(0, s) for _, s in ranked) or 1
        confidence = min(1.0, top_score / total)
    else:
        confidence = 0.8

    reasoning_parts = [f"query_type={query_type}"]
    if llm_used:
        reasoning_parts.append("llm_classified")
    if card_matches:
        reasoning_parts.append(f"cards_detected={','.join(detected_card_names)}")
    for name, score in ranked:
        if score > 0:
            reasoning_parts.append(f"{name}={score:.1f}")

    decision = RouteDecision(
        documents=documents,
        persona=persona,
        confidence=round(confidence, 2),
        reasoning=", ".join(reasoning_parts),
        card_names=detected_card_names,
    )
    return decision

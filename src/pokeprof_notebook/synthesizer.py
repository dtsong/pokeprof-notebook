"""Answer synthesizer for PokéProf Notebook.

Generates persona-aware answers from retrieved sections using the
Anthropic messages API with token budget management via tiktoken.
Supports both synchronous and streaming responses.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path

import tiktoken
from anthropic import Anthropic

from pokeprof_notebook.config import get_project_root
from pokeprof_notebook.types import DocumentType, RetrievedSection, TreeNode

logger = logging.getLogger(__name__)

_TOKEN_BUDGETS: dict[str, int] = {
    "judge": 6000,
    "professor": 4000,
    "player": 3000,
}

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_CARD_DB_TYPES = {DocumentType.CARD_DATABASE}


def _load_system_prompt(persona: str) -> str:
    """Load the system prompt for a persona from config/prompts/."""
    prompt_path = get_project_root() / "config" / "prompts" / f"{persona}_system.txt"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    logger.warning("System prompt not found at %s, using default", prompt_path)
    return (
        f"You are PokéProf, a helpful {persona} assistant for Pokémon TCG rules. "
        "Always cite specific section numbers. Never fabricate rulings."
    )


def _ancestry_trail(node: TreeNode) -> str:
    """Build an ancestry breadcrumb from node metadata."""
    section = node.metadata.section_number
    title = node.metadata.title
    if section and title:
        return f"{section}. {title}"
    return section or title or node.id


def _is_card_section(rs: RetrievedSection) -> bool:
    """Check if a retrieved section is from a card database document."""
    return rs.node.metadata.document_type in _CARD_DB_TYPES


def _is_compendium_section(rs: RetrievedSection) -> bool:
    """Check if a retrieved section is from the rulings compendium."""
    return rs.node.metadata.document_type == DocumentType.RULINGS_COMPENDIUM


def _build_context(sections: list[RetrievedSection], token_budget: int) -> str:
    """Assemble context from retrieved sections within the token budget.

    When card_db sections are present, structures context as:
    1. Card text sections first (quoted)
    2. General rules sections
    3. Compendium rulings
    """
    enc = tiktoken.encoding_for_model("gpt-4o-mini")

    # Separate sections by type
    card_sections = [s for s in sections if _is_card_section(s)]
    compendium_sections = [s for s in sections if _is_compendium_section(s)]
    rules_sections = [
        s for s in sections
        if not _is_card_section(s) and not _is_compendium_section(s)
    ]

    # Reorder: cards first, then rules, then compendium
    ordered = card_sections + rules_sections + compendium_sections

    parts: list[str] = []
    used_tokens = 0

    # Add section type headers when we have mixed content
    has_cards = bool(card_sections)
    has_rules = bool(rules_sections)
    has_compendium = bool(compendium_sections)

    current_type = None

    for rs in ordered:
        # Add section type header on transition
        if has_cards and (has_rules or has_compendium):
            if _is_card_section(rs) and current_type != "card":
                current_type = "card"
                parts.append("=== CARD TEXT ===")
            elif _is_compendium_section(rs) and current_type != "compendium":
                current_type = "compendium"
                parts.append("=== COMPENDIUM RULINGS ===")
            elif not _is_card_section(rs) and not _is_compendium_section(rs) and current_type != "rules":
                current_type = "rules"
                parts.append("=== GAME RULES ===")

        node = rs.node
        ancestry = _ancestry_trail(node)
        section_text = f"[{ancestry}]\n{node.content}"

        if rs.errata_context:
            section_text += "\n\n⚠ CARD ERRATA:\n" + "\n".join(rs.errata_context)

        section_tokens = len(enc.encode(section_text))

        if used_tokens + section_tokens > token_budget:
            remaining = token_budget - used_tokens
            if remaining > 50:
                truncated = enc.decode(enc.encode(section_text)[:remaining])
                parts.append(truncated + "\n[...truncated]")
            break

        parts.append(section_text)
        used_tokens += section_tokens

    return "\n\n---\n\n".join(parts)


def _build_messages(
    query: str,
    sections: list[RetrievedSection],
    persona: str,
) -> tuple[str, str]:
    """Build system prompt and user message for the LLM call."""
    system_prompt = _load_system_prompt(persona)
    token_budget = _TOKEN_BUDGETS.get(persona, 3000)
    context = _build_context(sections, token_budget)

    if not context.strip():
        return system_prompt, ""

    # Adjust the prompt framing when card data is present
    has_cards = any(_is_card_section(s) for s in sections)
    if has_cards:
        user_message = (
            f"Based on the following card data and rule sections, answer this question:\n\n"
            f"Question: {query}\n\n"
            f"Reference Material:\n{context}"
        )
    else:
        user_message = (
            f"Based on the following rule sections, answer this question:\n\n"
            f"Question: {query}\n\n"
            f"Rule Sections:\n{context}"
        )

    return system_prompt, user_message


def synthesize(
    query: str,
    sections: list[RetrievedSection],
    persona: str = "judge",
    model: str = _DEFAULT_MODEL,
) -> str:
    """Generate an answer from retrieved sections using an LLM."""
    system_prompt, user_message = _build_messages(query, sections, persona)

    if not user_message:
        return "I couldn't find relevant rule sections to answer this question."

    client = Anthropic()
    message = client.messages.create(
        model=model,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=1024,
    )

    if not message.content or not message.content[0].text:
        logger.warning("LLM returned empty response for query: %s", query[:100])
        return "I was unable to generate an answer. Please try rephrasing your question."
    return message.content[0].text


def synthesize_stream(
    query: str,
    sections: list[RetrievedSection],
    persona: str = "judge",
    model: str = _DEFAULT_MODEL,
) -> Generator[str, None, None]:
    """Generate a streaming answer from retrieved sections.

    Yields text chunks as they arrive from the API.
    """
    system_prompt, user_message = _build_messages(query, sections, persona)

    if not user_message:
        yield "I couldn't find relevant rule sections to answer this question."
        return

    client = Anthropic()
    try:
        with client.messages.stream(
            model=model,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message},
            ],
            temperature=0.1,
            max_tokens=1024,
        ) as stream:
            for text in stream.text_stream:
                yield text
    except Exception:
        logger.error("Streaming synthesis failed", exc_info=True)
        raise

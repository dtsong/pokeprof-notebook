"""Shared fixtures and factories for PokéProf Notebook tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pokeprof_notebook.types import (
    DocumentIndex,
    DocumentType,
    DomainConfig,
    NodeMetadata,
    RetrievedSection,
    TreeNode,
)


# ── Factory functions ──


def make_node(
    id: str = "node",
    content: str = "",
    document_type: DocumentType = DocumentType.RULEBOOK,
    section_number: str = "",
    title: str = "",
    children: list[TreeNode] | None = None,
    token_count: int = 0,
) -> TreeNode:
    """Create a TreeNode with sensible defaults."""
    meta = NodeMetadata(
        document_type=document_type,
        section_number=section_number,
        title=title,
    )
    return TreeNode(
        id=id,
        content=content,
        metadata=meta,
        children=children or [],
        token_count=token_count,
    )


def make_index(
    document_name: str = "rulebook",
    document_type: DocumentType = DocumentType.RULEBOOK,
    root: TreeNode | None = None,
    total_tokens: int = 0,
    source_hash: str = "abc123",
) -> DocumentIndex:
    """Create a DocumentIndex with sensible defaults."""
    if root is None:
        root_meta = NodeMetadata(document_type=document_type, title=document_name)
        child = make_node(
            id="1",
            content="Content for test section.",
            document_type=document_type,
            section_number="1",
            title="Test Section",
            token_count=5,
        )
        root = TreeNode(id="root", content="", metadata=root_meta, children=[child])
        total_tokens = 5
    return DocumentIndex(
        document_name=document_name,
        document_type=document_type,
        root=root,
        total_tokens=total_tokens,
        source_hash=source_hash,
    )


def make_section(
    node: TreeNode | None = None,
    score: float = 1.0,
    document_name: str = "rulebook",
    errata_context: list[str] | None = None,
) -> RetrievedSection:
    """Create a RetrievedSection with sensible defaults."""
    if node is None:
        node = make_node(
            id="1", content="Section content.", section_number="1", title="Section"
        )
    return RetrievedSection(
        node=node,
        score=score,
        document_name=document_name,
        errata_context=errata_context or [],
    )


# ── Fixtures ──


@pytest.fixture
def sample_tree() -> TreeNode:
    """A 3-level tree: root -> 2 children -> 2 grandchildren each."""
    gc1 = make_node(id="1.1", content="Grandchild 1.1", section_number="1.1", title="GC 1.1", token_count=3)
    gc2 = make_node(id="1.2", content="Grandchild 1.2", section_number="1.2", title="GC 1.2", token_count=3)
    gc3 = make_node(id="2.1", content="Grandchild 2.1", section_number="2.1", title="GC 2.1", token_count=3)
    gc4 = make_node(id="2.2", content="Grandchild 2.2", section_number="2.2", title="GC 2.2", token_count=3)

    child1 = make_node(
        id="1", content="Child 1", section_number="1", title="Child One",
        children=[gc1, gc2], token_count=2,
    )
    child2 = make_node(
        id="2", content="Child 2", section_number="2", title="Child Two",
        children=[gc3, gc4], token_count=2,
    )

    root = make_node(
        id="root", content="", title="Root", children=[child1, child2], token_count=0,
    )
    return root


@pytest.fixture
def sample_config() -> DomainConfig:
    """DomainConfig matching production routing_hints structure."""
    return DomainConfig(
        domain_name="pokemon_tcg",
        routing_hints={
            "rulebook": ["rule", "attack", "energy", "evolve", "retreat"],
            "penalty_guidelines": ["penalty", "infraction", "warning", "game loss"],
            "legal_card_list": ["legal", "banned", "standard", "format"],
            "card_db_pokemon": ["card", "pokemon", "ability", "attack"],
            "card_db_trainers": ["supporter", "item", "stadium", "tool"],
            "card_db_energy": ["energy", "special energy", "basic energy"],
            "rulings_compendium": ["ruling", "compendium", "interaction"],
        },
    )


@pytest.fixture
def mock_anthropic_client():
    """MagicMock Anthropic client with messages.create() configured."""
    client = MagicMock()
    message = MagicMock()
    message.content = [MagicMock(text="Mock LLM response")]
    client.messages.create.return_value = message
    return client


@pytest.fixture
def reset_router_cache(monkeypatch):
    """Clear router module-level caches between tests."""
    import pokeprof_notebook.router as router_mod

    monkeypatch.setattr(router_mod, "_card_name_index", None)
    monkeypatch.setattr(router_mod, "_card_name_index_mtime", 0.0)
    monkeypatch.setattr(router_mod, "_llm_classify_cache", {})

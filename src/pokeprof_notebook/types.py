"""PokéProf Notebook data types — domain models for Pokémon TCG document companion."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import yaml


class DocumentType(Enum):
    """Type of source document."""

    RULEBOOK = "rulebook"
    PENALTY_GUIDELINES = "penalty_guidelines"
    LEGAL_CARD_LIST = "legal_card_list"
    RULINGS_COMPENDIUM = "rulings_compendium"
    CARD_DATABASE = "card_database"


@dataclass
class NodeMetadata:
    """Metadata attached to a tree node (section-level annotations)."""

    document_type: DocumentType
    section_number: str = ""
    title: str = ""


@dataclass
class TreeNode:
    """A node in a hierarchical document index (PageIndex tree)."""

    id: str
    content: str
    metadata: NodeMetadata
    children: list[TreeNode] = field(default_factory=list)
    token_count: int = 0

    def walk(self) -> list[TreeNode]:
        """Return all nodes in depth-first order."""
        result = [self]
        for child in self.children:
            result.extend(child.walk())
        return result


@dataclass
class DocumentIndex:
    """A complete indexed document — root of a PageIndex tree."""

    document_name: str
    document_type: DocumentType
    root: TreeNode
    total_tokens: int = 0
    source_hash: str = ""


@dataclass
class RetrievedSection:
    """A section retrieved by the retriever, scored for relevance."""

    node: TreeNode
    score: float
    document_name: str
    errata_context: list[str] = field(default_factory=list)


@dataclass
class RouteDecision:
    """Router output — which documents and persona to use for a query."""

    documents: list[str]
    persona: str
    confidence: float
    reasoning: str = ""
    card_names: list[str] = field(default_factory=list)


@dataclass
class DomainConfig:
    """Top-level domain configuration parsed from domain_config.yaml."""

    domain_name: str
    routing_hints: dict[str, list[str]]

    @classmethod
    def from_yaml(cls, path: str | Path) -> DomainConfig:
        """Load domain configuration from a YAML file."""
        path = Path(path)
        with open(path) as f:
            data = yaml.safe_load(f)

        routing_hints: dict[str, list[str]] = data.get("routing_hints", {})

        return cls(
            domain_name=data["domain_name"],
            routing_hints=routing_hints,
        )

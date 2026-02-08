"""Tree retriever for PokéProf Notebook.

Performs LLM-guided tree descent to find relevant rule sections for a
query. Builds a flat section_number -> TreeNode lookup at load time for
O(1) cross-reference resolution. Supports direct card name lookup for
card database documents.
"""

from __future__ import annotations

import logging
import re

from anthropic import Anthropic, APIConnectionError, APIStatusError, AuthenticationError

from pokeprof_notebook.types import DocumentIndex, RetrievedSection, TreeNode

logger = logging.getLogger(__name__)

_CROSS_REF_RE = re.compile(
    r"(?:see\s+)?(?:rule|section)\s+(\d{1,3}(?:\.\d+)*(?:\.[a-z](?:\.\d+)*)?)",
    re.IGNORECASE,
)

# Cross-document reference patterns for Pokemon TCG
_CROSS_DOC_RE = re.compile(
    r"(?:as\s+(?:defined|described|outlined|specified)\s+in\s+(?:the\s+)?|"
    r"see\s+(?:the\s+)?|refer\s+to\s+(?:the\s+)?)"
    r"(rulebook|rules?\s+(?:and\s+)?regulations|penalty\s+guidelines|"
    r"legal\s+card\s+list|standard\s+(?:legal\s+)?list)",
    re.IGNORECASE,
)

_DOC_NAME_MAP: dict[str, str] = {
    "rulebook": "rulebook",
    "rule and regulations": "rulebook",
    "rules and regulations": "rulebook",
    "rules regulations": "rulebook",
    "penalty guidelines": "penalty_guidelines",
    "legal card list": "legal_card_list",
    "standard list": "legal_card_list",
    "standard legal list": "legal_card_list",
}


def _build_lookup(index: DocumentIndex) -> dict[str, TreeNode]:
    """Build a flat section_number -> TreeNode lookup dict."""
    lookup: dict[str, TreeNode] = {}
    for node in index.root.walk():
        if node.metadata.section_number:
            lookup[node.metadata.section_number] = node
    return lookup


def _ancestry_context(node: TreeNode, lookup: dict[str, TreeNode]) -> str:
    """Build an ancestry breadcrumb trail for a node."""
    parts = node.metadata.section_number.split(".")
    trail: list[str] = []

    for i in range(1, len(parts) + 1):
        ancestor_num = ".".join(parts[:i])
        ancestor = lookup.get(ancestor_num)
        if ancestor:
            title = ancestor.metadata.title
            if title:
                trail.append(f"{ancestor_num}. {title}")
            else:
                trail.append(ancestor_num)
        else:
            trail.append(ancestor_num)

    return " > ".join(trail)


def _select_children(
    node: TreeNode, query: str, model: str = "claude-haiku-4-5-20251001"
) -> list[TreeNode]:
    """Use LLM to select which children are relevant to the query."""
    if not node.children:
        return []

    options: list[str] = []
    for i, child in enumerate(node.children):
        num = child.metadata.section_number or child.id
        title = child.metadata.title or "(no title)"
        preview = child.content[:100] if child.content else ""
        options.append(f"{i}. [{num}] {title}: {preview}")

    options_text = "\n".join(options)

    try:
        client = Anthropic()
        message = client.messages.create(
            model=model,
            system=(
                "You are a Pokémon TCG rules index navigator. Given a query and "
                "a list of sections, respond with ONLY the numbers (comma-separated) "
                "of the most relevant sections. Respond with just numbers, e.g. "
                "'0,2,5'. Select 1-3 sections maximum."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Query: {query}\n\nSections:\n{options_text}",
                },
            ],
            temperature=0,
            max_tokens=50,
        )

        result = message.content[0].text if message.content else ""
        result = result or ""
    except AuthenticationError:
        raise
    except (APIConnectionError, APIStatusError) as e:
        logger.warning(
            "LLM tree navigation failed (%s), falling back to keyword matching",
            e,
        )
        return _keyword_select_children(node, query)
    except Exception:
        logger.warning(
            "LLM tree navigation failed, falling back to keyword matching",
            exc_info=True,
        )
        return _keyword_select_children(node, query)

    selected: list[TreeNode] = []
    for part in result.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part)
            if 0 <= idx < len(node.children):
                selected.append(node.children[idx])

    if not selected and node.children:
        logger.warning(
            "LLM response unparseable ('%s'), falling back to keyword matching",
            result[:80],
        )
        return _keyword_select_children(node, query)

    return selected


def _keyword_select_children(node: TreeNode, query: str) -> list[TreeNode]:
    """Keyword-based child selection as LLM fallback."""
    q_lower = query.lower()
    scored = []
    for child in node.children:
        text = f"{child.metadata.title} {child.content}".lower()
        words = set(q_lower.split())
        matches = sum(1 for w in words if w in text)
        if matches > 0:
            scored.append((matches, child))
    scored.sort(key=lambda x: -x[0])
    return [child for _, child in scored[:3]]


def search(
    query: str,
    index: DocumentIndex,
    max_sections: int = 5,
    model: str = "claude-haiku-4-5-20251001",
    use_llm: bool = True,
) -> list[RetrievedSection]:
    """Search for relevant sections using LLM-guided tree descent.

    Starting from the root, the LLM selects relevant children at each
    level, descending until leaf nodes or max_sections is reached.
    """
    lookup = _build_lookup(index)

    if use_llm:
        return _search_with_llm(query, index, lookup, max_sections, model)
    return _search_with_keywords(query, index, lookup, max_sections)


def _search_with_llm(
    query: str,
    index: DocumentIndex,
    lookup: dict[str, TreeNode],
    max_sections: int,
    model: str,
) -> list[RetrievedSection]:
    """LLM-guided tree descent."""
    results: list[RetrievedSection] = []
    frontier: list[TreeNode] = [index.root]
    visited: set[str] = set()

    while frontier and len(results) < max_sections:
        node = frontier.pop(0)
        if node.id in visited:
            continue
        visited.add(node.id)

        if node.children:
            selected = _select_children(node, query, model)
            for child in selected:
                if child.children:
                    frontier.append(child)
                else:
                    results.append(
                        RetrievedSection(
                            node=child,
                            score=1.0,
                            document_name=index.document_name,
                        )
                    )
        elif node.id != "root":
            results.append(
                RetrievedSection(
                    node=node,
                    score=1.0,
                    document_name=index.document_name,
                )
            )

    results = resolve_cross_references(
        results, lookup, index.document_name, max_sections
    )
    return results[:max_sections]


def _search_with_keywords(
    query: str,
    index: DocumentIndex,
    lookup: dict[str, TreeNode],
    max_sections: int,
) -> list[RetrievedSection]:
    """Keyword-based search as fallback when LLM is not available."""
    q_lower = query.lower()
    scored: list[tuple[float, TreeNode]] = []

    for node in index.root.walk():
        if node.id == "root":
            continue
        text = f"{node.metadata.title} {node.content}".lower()
        words = set(q_lower.split())
        matches = sum(1 for w in words if w in text)
        if matches > 0:
            score = matches / len(words)
            scored.append((score, node))

    scored.sort(key=lambda x: -x[0])

    results = [
        RetrievedSection(
            node=node,
            score=score,
            document_name=index.document_name,
        )
        for score, node in scored[:max_sections]
    ]

    results = resolve_cross_references(
        results, lookup, index.document_name, max_sections
    )
    return results[:max_sections]


def resolve_cross_references(
    sections: list[RetrievedSection],
    lookup: dict[str, TreeNode],
    document_name: str,
    max_sections: int = 10,
) -> list[RetrievedSection]:
    """Expand cross-references found in retrieved sections."""
    existing_ids = {rs.node.id for rs in sections}
    new_sections: list[RetrievedSection] = []

    for rs in sections:
        refs = _CROSS_REF_RE.findall(rs.node.content)
        for ref_num in refs:
            ref_node = lookup.get(ref_num)
            if ref_node and ref_node.id not in existing_ids:
                new_sections.append(
                    RetrievedSection(
                        node=ref_node,
                        score=0.5,
                        document_name=document_name,
                    )
                )
                existing_ids.add(ref_node.id)
                if len(sections) + len(new_sections) >= max_sections:
                    break

    return sections + new_sections


def detect_cross_doc_references(
    sections: list[RetrievedSection],
) -> set[str]:
    """Detect cross-document references in retrieved sections."""
    referenced_docs: set[str] = set()
    for rs in sections:
        matches = _CROSS_DOC_RE.findall(rs.node.content)
        for match in matches:
            doc_name = _DOC_NAME_MAP.get(match.lower().strip())
            if doc_name and doc_name != rs.document_name:
                referenced_docs.add(doc_name)
    return referenced_docs


def search_by_card_names(
    card_names: list[str],
    index: DocumentIndex,
) -> list[RetrievedSection]:
    """Direct node lookup by card name — bypasses tree descent.

    Searches all leaf nodes for titles matching the given card names.
    """
    results: list[RetrievedSection] = []
    names_lower = {n.lower() for n in card_names}

    for node in index.root.walk():
        if node.id == "root":
            continue
        title_lower = node.metadata.title.lower()
        if title_lower in names_lower:
            results.append(
                RetrievedSection(
                    node=node,
                    score=2.0,  # High score for direct match
                    document_name=index.document_name,
                )
            )

    return results


def search_multi(
    query: str,
    indexes: dict[str, DocumentIndex],
    max_sections: int = 10,
    model: str = "claude-haiku-4-5-20251001",
    use_llm: bool = True,
    document_weights: dict[str, float] | None = None,
    card_names: list[str] | None = None,
) -> list[RetrievedSection]:
    """Search multiple document indexes and merge results by weighted score.

    When card_names is provided, uses direct lookup for card_db documents
    instead of tree descent.
    """
    weights = document_weights or {}
    all_results: list[RetrievedSection] = []

    # Card DB documents that should use direct lookup
    card_db_docs = {"card_db_pokemon", "card_db_trainers", "card_db_energy"}

    per_doc = max(3, max_sections // len(indexes)) if indexes else max_sections
    for doc_name, index in indexes.items():
        # Use direct card name lookup for card_db docs when names are detected
        if card_names and doc_name in card_db_docs:
            results = search_by_card_names(card_names, index)
            # Also do keyword search to catch related cards
            if len(results) < per_doc:
                extra = search(
                    query, index, max_sections=per_doc - len(results),
                    model=model, use_llm=use_llm,
                )
                results.extend(extra)
        else:
            results = search(
                query, index, max_sections=per_doc, model=model, use_llm=use_llm
            )

        weight = weights.get(doc_name, 1.0)
        for rs in results:
            rs.score *= weight
        all_results.extend(results)

    # Detect cross-document references
    cross_refs = detect_cross_doc_references(all_results)
    existing_docs = {rs.document_name for rs in all_results}
    for ref_doc in cross_refs:
        if ref_doc not in existing_docs and ref_doc in indexes:
            extra = search(
                query, indexes[ref_doc], max_sections=3, model=model, use_llm=use_llm
            )
            for rs in extra:
                rs.score *= 0.7
            all_results.extend(extra)

    # Deduplicate by (document_name, node_id) to avoid cross-document collisions
    seen: set[tuple[str, str]] = set()
    unique: list[RetrievedSection] = []
    for rs in all_results:
        key = (rs.document_name, rs.node.id)
        if key not in seen:
            unique.append(rs)
            seen.add(key)

    unique.sort(key=lambda x: -x.score)
    return unique[:max_sections]

"""Overlay manifest builder for PokéProf Notebook.

Maps card names to their errata and rule sections to updates,
enabling errata-aware retrieval and synthesis.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

from pokeprof_notebook.types import DocumentType, RetrievedSection

_RULE_REF_RE = re.compile(
    r"(?:rule|section)\s+(\d{1,3}(?:\.\d+)*(?:\.[a-z])?)", re.IGNORECASE
)


@dataclass
class ErrataOverlay:
    """Errata entry for a card."""

    card_name: str
    new_text: str
    old_text: str
    source: str


@dataclass
class OverlayManifest:
    """Maps card names to errata entries."""

    # card_name (lowercase) -> list of errata entries
    card_errata: dict[str, list[ErrataOverlay]] = field(default_factory=dict)


def extract_errata_from_compendium(compendium_path: Path) -> list[dict[str, str]]:
    """Extract errata entries from compendium_rulings.json.

    Reads the Errata category posts and converts them into the structured
    format expected by build_overlay().

    Args:
        compendium_path: Path to compendium_rulings.json.

    Returns:
        List of dicts with card_name, new_text, old_text, source.
    """
    data = json.loads(compendium_path.read_text(encoding="utf-8"))
    errata_posts = [
        p for p in data.get("posts", [])
        if p.get("category_name") == "Errata"
    ]

    entries: list[dict[str, str]] = []
    for post in errata_posts:
        title = post.get("title", "").strip()
        content = post.get("content", "").strip()
        if not title or not content:
            continue

        # Extract source from content (last "Source:" line)
        source = "Compendium Errata"
        source_match = re.search(
            r"Source:\s*(.+?)(?:\n|$)", content, re.IGNORECASE
        )
        if source_match:
            source = source_match.group(1).strip()

        entries.append({
            "card_name": title,
            "new_text": content,
            "old_text": "",
            "source": source,
        })

    logger.info("Extracted %d errata entries from compendium", len(entries))
    return entries


def build_overlay(
    errata_paths: list[Path],
) -> OverlayManifest:
    """Build an overlay manifest from errata JSON files.

    Args:
        errata_paths: Paths to errata JSON files.

    Returns:
        An OverlayManifest with card errata mappings.
    """
    manifest = OverlayManifest()

    for path in errata_paths:
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read errata file %s: %s", path, e)
            continue

        for i, entry in enumerate(entries):
            try:
                overlay = ErrataOverlay(
                    card_name=entry["card_name"],
                    new_text=entry["new_text"],
                    old_text=entry["old_text"],
                    source=entry.get("source", path.stem),
                )
                key = entry["card_name"].lower()
                manifest.card_errata.setdefault(key, []).append(overlay)
            except (KeyError, TypeError) as e:
                logger.warning("Skipping malformed errata entry %d in %s: %s", i, path.name, e)

    return manifest


def save_overlay(manifest: OverlayManifest, output_path: Path) -> None:
    """Serialize an overlay manifest to JSON."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "card_errata": {
            k: [asdict(e) for e in v] for k, v in manifest.card_errata.items()
        },
    }

    # Atomic write to prevent corruption
    fd, tmp_path = tempfile.mkstemp(dir=str(output_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        Path(tmp_path).replace(output_path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def load_overlay(input_path: Path) -> OverlayManifest:
    """Deserialize an overlay manifest from JSON.

    Returns an empty manifest if the file is corrupt or unreadable.
    """
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load overlay manifest %s: %s", input_path, e)
        return OverlayManifest()

    manifest = OverlayManifest()
    for card_name, errata_list in data.get("card_errata", {}).items():
        try:
            manifest.card_errata[card_name] = [ErrataOverlay(**e) for e in errata_list]
        except (TypeError, KeyError) as e:
            logger.warning("Skipping corrupt errata for card '%s': %s", card_name, e)

    return manifest


def lookup_card_errata(
    manifest: OverlayManifest, query: str
) -> list[ErrataOverlay]:
    """Find errata for cards mentioned in a query string."""
    q_lower = query.lower()
    results: list[ErrataOverlay] = []
    seen: set[str] = set()

    for card_key, errata_list in manifest.card_errata.items():
        if card_key in q_lower:
            for e in errata_list:
                if e.card_name not in seen:
                    results.append(e)
                    seen.add(e.card_name)

    return results


def annotate_sections(
    sections: list[RetrievedSection],
    manifest: OverlayManifest,
    query: str = "",
) -> list[RetrievedSection]:
    """Annotate retrieved sections with overlay data."""
    _CARD_DB_TYPES = {DocumentType.CARD_DATABASE}
    if query:
        card_errata = lookup_card_errata(manifest, query)
        if card_errata:
            errata_context = [
                f"{e.card_name}: OLD: {e.old_text[:150]} → NEW: {e.new_text[:150]}"
                for e in card_errata[:3]
            ]
            for rs in sections:
                if rs.node.metadata.document_type in _CARD_DB_TYPES:
                    rs.errata_context = errata_context

    return sections

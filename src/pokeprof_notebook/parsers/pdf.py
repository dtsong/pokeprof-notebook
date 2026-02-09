"""PDF parser for PokéProf Notebook.

Converts PDF documents to intermediate markdown using pymupdf4llm,
preserving heading hierarchy for the indexer.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_pdf(source_path: str | Path, output_path: str | Path) -> Path:
    """Convert a PDF to markdown using pymupdf4llm.

    Args:
        source_path: Path to the source PDF file.
        output_path: Path where the intermediate markdown will be written.

    Returns:
        The output path.
    """
    import pymupdf4llm

    source_path = Path(source_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Parsing PDF: %s", source_path.name)

    md_text = pymupdf4llm.to_markdown(
        str(source_path),
        show_progress=False,
    )

    # Clean up common artifacts from PDF extraction
    md_text = _clean_markdown(md_text)

    # Apply rulebook-specific heading restructuring if detected
    if _is_rulebook(md_text):
        md_text = _restructure_rulebook(md_text)

    output_path.write_text(md_text, encoding="utf-8")
    logger.info("Wrote markdown: %s (%d chars)", output_path.name, len(md_text))

    return output_path


def _is_rulebook(text: str) -> bool:
    """Detect if the markdown is from the Pokemon TCG rulebook."""
    first_500 = text[:500].upper()
    return "POKÉMON TRADING CARD GAME RULES" in first_500 or (
        "CONTENTS" in first_500 and "PLAYING THE GAME" in first_500
    )


def _restructure_rulebook(text: str) -> str:
    """Restructure flat h6 headings into proper hierarchy using TOC analysis.

    The rulebook PDF extracts with all headings as h6 (######) and sub-sections
    as bold text. This function:
    1. Promotes h6 main sections to h2
    2. Promotes bold-only sub-section lines to h3
    3. Promotes bold-only topic headings to h4
    4. Joins fragmented sentences from the graphical PDF layout
    """
    lines = text.split("\n")

    # Step 1: Parse the TOC to extract sub-section names.
    # TOC entries without bold are sub-sections under their preceding bold entry.
    toc_main: set[str] = set()
    toc_sub: set[str] = set()
    in_toc = False
    toc_end_idx = 0

    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"^#{1,6}\s+\**Contents\**", stripped):
            in_toc = True
            continue
        if in_toc:
            # A heading line ends the TOC
            if stripped.startswith("#") and "Contents" not in stripped:
                toc_end_idx = i
                break
            # TOC entries have dot leaders or end with page numbers
            if re.search(r"\.{3,}", stripped) or re.search(r"\d+\**\s*$", stripped):
                # Extract section name: strip bold markers, dots, page numbers
                name = re.sub(r"[\.\s]+\d+\**\s*$", "", stripped)
                name = re.sub(r"\*{1,2}", "", name)
                name = re.sub(r"_", "", name)
                name = name.strip(" .")
                # Normalize whitespace
                name = re.sub(r"\s+", " ", name).strip()
                if not name:
                    continue
                # Bold TOC entries = main sections, plain = sub-sections
                if stripped.startswith("**"):
                    toc_main.add(name)
                else:
                    toc_sub.add(name)

    logger.info(
        "Rulebook TOC: %d main sections, %d sub-sections",
        len(toc_main), len(toc_sub),
    )

    # Step 2: Build a normalized lookup for matching headings to TOC entries
    def _normalize(s: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[*_\[\]{}]", "", s)).strip().lower()

    toc_main_norm = {_normalize(n) for n in toc_main}
    toc_sub_norm = {_normalize(n) for n in toc_sub}

    # Step 3: Process lines — promote headings and bold sub-sections
    result: list[str] = []
    # Track whether we're past the TOC
    past_toc = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if i >= toc_end_idx and toc_end_idx > 0:
            past_toc = True

        if not past_toc:
            result.append(line)
            continue

        # Promote h5/h6 headings to h2
        h_match = re.match(r"^(#{5,6})\s+(.+)$", stripped)
        if h_match:
            heading_text = h_match.group(2).strip("* ")
            result.append(f"## {heading_text}")
            continue

        # Check if this is a bold-only line that should become a heading
        bold_match = re.match(r"^\*\*([^*]+)\*\*$", stripped)
        if bold_match:
            bold_text = bold_match.group(1).strip()
            bold_norm = _normalize(bold_text)

            # Skip numbered/lettered list items
            if re.match(r"^[0-9]+[).]", bold_text) or re.match(r"^[A-Z][).]", bold_text):
                result.append(line)
                continue

            # Skip if it ends with a period (likely a sentence, not a heading)
            if bold_text.endswith("."):
                result.append(line)
                continue

            # Check if it matches a TOC sub-section
            if bold_norm in toc_sub_norm:
                result.append(f"### {bold_text}")
                continue

            # Short bold-only lines (3-50 chars, not a sentence) → h4 topic heading
            if 3 <= len(bold_text) <= 50 and not bold_text.endswith(","):
                result.append(f"#### {bold_text}")
                continue

        result.append(line)

    text = "\n".join(result)

    # Step 4: Join fragmented sentences.
    # Lines that end without punctuation followed by lines starting lowercase
    # are likely fragments from the graphical PDF layout.
    text = _join_fragments(text)

    return text


def _join_fragments(text: str) -> str:
    """Join sentence fragments split across lines by PDF extraction."""
    lines = text.split("\n")
    merged: list[str] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip headings, blank lines, list items
        if (
            not stripped
            or stripped.startswith("#")
            or stripped.startswith("-")
            or stripped.startswith("|")
            or stripped.startswith(">")
        ):
            merged.append(line)
            i += 1
            continue

        # Check if this line should be joined with the next
        # Conditions: line doesn't end with sentence-ending punctuation,
        # and next line starts with lowercase or continues a sentence
        while i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if not next_line:
                break
            if next_line.startswith("#") or next_line.startswith("-") or next_line.startswith("|"):
                break
            # Join if current line doesn't end with terminating punctuation
            # and next line starts with lowercase or a continuation word
            if (
                not stripped.endswith((".", "!", "?", ":", ";", ")", "]"))
                and len(stripped) < 100
                and next_line[0].islower()
            ):
                stripped = stripped + " " + next_line
                i += 1
            else:
                break

        merged.append(stripped)
        i += 1

    return "\n".join(merged)


def _clean_markdown(text: str) -> str:
    """Clean up common PDF extraction artifacts."""
    lines = text.split("\n")
    cleaned: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Skip page break markers
        if stripped == "-----":
            continue

        # Skip repeated page headers/footers (Pokemon TCG rulebook pattern)
        if re.match(
            r"\*{0,2}THE POK[EÉ]MON TRADING CARD GAME\*{0,2}",
            stripped,
            re.IGNORECASE,
        ):
            continue

        # Skip lines that are just page numbers as headings (### 2, ### 3, etc.)
        if re.match(r"^#{1,6}\s+\d{1,3}$", stripped):
            continue

        # Skip lines that are just page numbers
        if stripped.isdigit() and len(stripped) <= 4:
            continue

        # Skip empty bold/italic artifacts
        if stripped in ("**.**", "_**|**_", "**[:]**", "[:]"):
            continue

        cleaned.append(line)

    return "\n".join(cleaned)

"""PDF parser for PokéProf Notebook.

Converts PDF documents to intermediate markdown using pymupdf4llm,
preserving heading hierarchy for the indexer.
"""

from __future__ import annotations

import logging
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

    output_path.write_text(md_text, encoding="utf-8")
    logger.info("Wrote markdown: %s (%d chars)", output_path.name, len(md_text))

    return output_path


def _clean_markdown(text: str) -> str:
    """Clean up common PDF extraction artifacts."""
    import re

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

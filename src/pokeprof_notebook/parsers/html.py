"""HTML parser for PokéProf Notebook.

Converts saved HTML pages to intermediate markdown using BeautifulSoup4,
preserving heading hierarchy for the indexer.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


def parse_html(source_path: str | Path, output_path: str | Path) -> Path:
    """Convert a saved HTML page to markdown.

    Args:
        source_path: Path to the source HTML file.
        output_path: Path where the intermediate markdown will be written.

    Returns:
        The output path.
    """
    source_path = Path(source_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Parsing HTML: %s", source_path.name)

    html = source_path.read_text(encoding="utf-8", errors="replace")
    soup = BeautifulSoup(html, "lxml")

    # Remove script and style elements
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # Find the main content area
    content = _find_main_content(soup)

    md_lines = _html_to_markdown(content)
    md_text = "\n".join(md_lines)

    output_path.write_text(md_text, encoding="utf-8")
    logger.info("Wrote markdown: %s (%d chars)", output_path.name, len(md_text))

    return output_path


def _find_main_content(soup: BeautifulSoup) -> Tag:
    """Find the main content area of the page."""
    # Try common content containers
    for selector in ["main", "article", ".entry-content", ".post-content", "#content"]:
        content = soup.select_one(selector)
        if content:
            return content

    # Fall back to body
    return soup.body or soup


def _html_to_markdown(element: Tag) -> list[str]:
    """Convert an HTML element tree to markdown lines."""
    lines: list[str] = []

    for child in element.children:
        if isinstance(child, str):
            text = child.strip()
            if text:
                lines.append(text)
            continue

        if not isinstance(child, Tag):
            continue

        tag_name = child.name

        # Headings
        if re.match(r"^h[1-6]$", tag_name):
            level = int(tag_name[1])
            text = child.get_text(strip=True)
            if text:
                lines.append("")
                lines.append(f"{'#' * level} {text}")
                lines.append("")

        # Paragraphs
        elif tag_name == "p":
            text = child.get_text(strip=True)
            if text:
                lines.append(text)
                lines.append("")

        # Lists
        elif tag_name in ("ul", "ol"):
            lines.extend(_list_to_markdown(child))
            lines.append("")

        # Tables
        elif tag_name == "table":
            lines.extend(_table_to_markdown(child))
            lines.append("")

        # Divs, sections, article — recurse
        elif tag_name in ("div", "section", "article", "span", "blockquote", "main"):
            lines.extend(_html_to_markdown(child))

        # Bold/strong as inline
        elif tag_name in ("strong", "b", "em", "i", "a"):
            text = child.get_text(strip=True)
            if text:
                lines.append(text)

    return lines


def _list_to_markdown(list_element: Tag, indent: int = 0) -> list[str]:
    """Convert a ul/ol to markdown list items."""
    lines: list[str] = []
    prefix = "  " * indent

    for i, li in enumerate(list_element.find_all("li", recursive=False)):
        # Check for nested lists
        nested = li.find(["ul", "ol"])
        if nested:
            # Get text before nested list
            text_parts = []
            for child in li.children:
                if isinstance(child, Tag) and child.name in ("ul", "ol"):
                    break
                text = child.get_text(strip=True) if isinstance(child, Tag) else str(child).strip()
                if text:
                    text_parts.append(text)

            text = " ".join(text_parts)
            if text:
                marker = f"{i + 1}." if list_element.name == "ol" else "-"
                lines.append(f"{prefix}{marker} {text}")
            lines.extend(_list_to_markdown(nested, indent + 1))
        else:
            text = li.get_text(strip=True)
            if text:
                marker = f"{i + 1}." if list_element.name == "ol" else "-"
                lines.append(f"{prefix}{marker} {text}")

    return lines


def _table_to_markdown(table: Tag) -> list[str]:
    """Convert an HTML table to a markdown table."""
    lines: list[str] = []
    rows = table.find_all("tr")

    if not rows:
        return lines

    for i, row in enumerate(rows):
        cells = row.find_all(["th", "td"])
        cell_texts = [c.get_text(strip=True).replace("|", "\\|") for c in cells]
        lines.append("| " + " | ".join(cell_texts) + " |")

        # Add header separator after first row
        if i == 0:
            lines.append("| " + " | ".join("---" for _ in cell_texts) + " |")

    return lines

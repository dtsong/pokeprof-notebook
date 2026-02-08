"""Compendium rulings parser for PokéProf Notebook.

Converts compendium_rulings.json into intermediate markdown organized
by the Compendium's category hierarchy.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def rulings_to_markdown(
    source_path: str | Path,
    output_path: str | Path,
) -> Path:
    """Convert compendium_rulings.json to intermediate markdown.

    Args:
        source_path: Path to compendium_rulings.json.
        output_path: Path for the intermediate markdown file.

    Returns:
        Path to the output markdown file.
    """
    source_path = Path(source_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(source_path.read_text(encoding="utf-8"))
    posts = data.get("posts", [])
    categories_list = data.get("categories", [])
    logger.info("Processing %d rulings from %s", len(posts), source_path.name)

    # Build category hierarchy
    category_map: dict[int, dict[str, Any]] = {}
    for cat in categories_list:
        category_map[cat["id"]] = cat

    # Group posts by category
    posts_by_category: dict[str, list[dict[str, Any]]] = {}
    for post in posts:
        cat_name = post.get("category_name", "Uncategorized")
        posts_by_category.setdefault(cat_name, []).append(post)

    # Build markdown
    lines = ["# Pokemon Rulings Compendium", ""]

    for cat_name in sorted(posts_by_category.keys()):
        cat_posts = posts_by_category[cat_name]
        lines.append(f"## {cat_name}")
        lines.append("")

        for post in sorted(cat_posts, key=lambda p: p.get("title", "")):
            title = post.get("title", "Untitled")
            content = post.get("content", "").strip()
            date = post.get("date", "")

            lines.append(f"### {title}")
            if content:
                lines.append(content)
            if date:
                lines.append(f"Source: compendium.pokegym.net | Date: {date[:10]}")
            lines.append("")

    md_text = "\n".join(lines)
    output_path.write_text(md_text, encoding="utf-8")
    logger.info(
        "Wrote %s (%d rulings, %d categories)",
        output_path.name,
        len(posts),
        len(posts_by_category),
    )
    return output_path

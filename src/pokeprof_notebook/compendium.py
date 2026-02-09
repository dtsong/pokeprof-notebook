"""Client for the Pokemon Rulings Compendium at compendium.pokegym.net.

Scrapes the all-rulings-by-category HTML page and caches the result
to data/sources/compendium_rulings.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

_ALL_RULINGS_URL = "https://compendium.pokegym.net/all-rulings-by-category/"
_USER_AGENT = "Mozilla/5.0 (compatible; PokeProfNotebook/1.0)"
_CACHE_MAX_AGE_DAYS = 7

# The 8 known top-level categories in display order
_CATEGORY_NAMES = [
    "Errata",
    "Meta-Rulings",
    "Attacks",
    "Abilities",
    "Trainers",
    "Energy",
    "Gameplay",
    "Team Battle",
]


def _parse_rulings_page(html_content: str) -> dict[str, Any]:
    """Parse the all-rulings-by-category HTML page into structured data.

    Walks the HTML linearly, tracking the current h3 (category) and h4
    (topic/card name). Ruling divs under each h4 are grouped into a
    single post with their text concatenated.

    Returns:
        Dict matching the expected JSON schema with fetched_at,
        total_posts, categories, and posts.
    """
    soup = BeautifulSoup(html_content, "lxml")

    # Find the main content area
    main = soup.find("main", class_="site-content")
    if main is None:
        # Fallback: try article or the whole body
        main = soup.find("article") or soup.find("main") or soup.body
    if main is None:
        raise ValueError("Could not find main content area in HTML page")

    # Build category lookup: name -> id (synthetic, 1-indexed)
    category_id_map: dict[str, int] = {}
    categories_list: list[dict[str, Any]] = []
    for idx, name in enumerate(_CATEGORY_NAMES, start=1):
        category_id_map[name] = idx
        categories_list.append({
            "id": idx,
            "name": name,
            "parent": 0,
            "count": 0,
        })
    next_category_id = len(_CATEGORY_NAMES) + 1

    # Walk through direct children of main, tracking current h3/h4
    current_category: str | None = None
    current_category_id: int = 0
    current_topic: str | None = None

    # Accumulator: (category_name, category_id, topic_name) -> list of ruling texts
    topic_rulings: dict[tuple[str, int, str], list[str]] = {}
    # Track latest date per topic
    topic_dates: dict[tuple[str, int, str], str] = {}

    # We need to iterate all descendants in document order, not just
    # direct children, because the structure may be nested.
    # Use recursive iteration over elements.
    for element in main.descendants:
        if not isinstance(element, Tag):
            continue

        if element.name == "h3":
            heading_text = element.get_text(strip=True)
            if heading_text:
                current_category = heading_text
                if current_category not in category_id_map:
                    category_id_map[current_category] = next_category_id
                    categories_list.append({
                        "id": next_category_id,
                        "name": current_category,
                        "parent": 0,
                        "count": 0,
                    })
                    next_category_id += 1
                current_category_id = category_id_map[current_category]
                current_topic = None

        elif element.name == "h4":
            heading_text = element.get_text(strip=True)
            if heading_text and current_category is not None:
                current_topic = heading_text

        elif (
            element.name == "div"
            and element.get("class")
            and any(
                cls.startswith("ruling-")
                for cls in element.get("class", [])
            )
        ):
            if current_category is None or current_topic is None:
                continue

            key = (current_category, current_category_id, current_topic)

            # Extract ruling text from <dl class="single-entry"><dd>...</dd></dl>
            ruling_parts: list[str] = []
            for dd in element.find_all("dd"):
                text = dd.get_text(strip=True)
                if text:
                    ruling_parts.append(text)

            # Extract source line
            source_div = element.find("div", id="source")
            if source_div is None:
                # Try finding by content pattern
                source_div = element.find(
                    "div", string=re.compile(r"Source", re.IGNORECASE)
                )
            source_text = ""
            if source_div:
                source_text = source_div.get_text(strip=True)
                ruling_parts.append(source_text)

            if ruling_parts:
                ruling_block = "\n".join(ruling_parts)
                topic_rulings.setdefault(key, []).append(ruling_block)

            # Extract date from source line (YYYY-MM-DD pattern)
            if source_text:
                date_match = re.search(r"\d{4}-\d{2}-\d{2}", source_text)
                if date_match:
                    topic_dates[key] = date_match.group(0)

    # Build posts from accumulated topic rulings
    posts: list[dict[str, Any]] = []
    post_id = 1
    category_counts: dict[int, int] = {}

    for (cat_name, cat_id, topic_name), rulings in topic_rulings.items():
        content = "\n\n".join(rulings)

        # Use the latest date found, or empty string
        date = topic_dates.get((cat_name, cat_id, topic_name), "")

        posts.append({
            "id": post_id,
            "title": topic_name,
            "content": content,
            "date": date,
            "category_id": cat_id,
            "category_name": cat_name,
        })
        post_id += 1
        category_counts[cat_id] = category_counts.get(cat_id, 0) + 1

    # Update category counts
    for cat in categories_list:
        cat["count"] = category_counts.get(cat["id"], 0)

    # Remove categories with zero posts
    categories_list = [c for c in categories_list if c["count"] > 0]

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_posts": len(posts),
        "categories": categories_list,
        "posts": posts,
    }


def fetch_all_rulings(
    output_path: str | Path,
    force: bool = False,
) -> Path:
    """Fetch all Compendium rulings and write to JSON cache.

    Scrapes the all-rulings-by-category page at compendium.pokegym.net
    and parses the HTML into structured ruling data.

    Skips if the cache is less than CACHE_MAX_AGE_DAYS old unless force=True.

    Returns:
        Path to the output JSON file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Check cache freshness
    if not force and output_path.exists():
        try:
            existing = json.loads(output_path.read_text(encoding="utf-8"))
            fetched_at = existing.get("fetched_at", "")
            if fetched_at:
                fetched_dt = datetime.fromisoformat(fetched_at)
                age_days = (datetime.now(timezone.utc) - fetched_dt).days
                if age_days < _CACHE_MAX_AGE_DAYS:
                    logger.info(
                        "Compendium cache is %d days old (max %d), skipping fetch",
                        age_days,
                        _CACHE_MAX_AGE_DAYS,
                    )
                    return output_path
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Compendium cache appears corrupt, re-fetching: %s", e)

    logger.info("Fetching all rulings from %s", _ALL_RULINGS_URL)

    with httpx.Client(
        timeout=60.0,
        headers={"User-Agent": _USER_AGENT},
        follow_redirects=True,
    ) as client:
        resp = client.get(_ALL_RULINGS_URL)
        resp.raise_for_status()
        html_content = resp.text

    logger.info(
        "Downloaded %d bytes of HTML, parsing rulings...",
        len(html_content),
    )

    result = _parse_rulings_page(html_content)

    logger.info(
        "Parsed %d posts across %d categories",
        result["total_posts"],
        len(result["categories"]),
    )

    # Atomic write to prevent corruption on interrupted fetch
    fd, tmp_path = tempfile.mkstemp(dir=str(output_path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
        Path(tmp_path).replace(output_path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise

    logger.info("Wrote %d rulings to %s", result["total_posts"], output_path)
    return output_path

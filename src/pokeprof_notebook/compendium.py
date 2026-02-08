"""Synchronous client for the Pokémon Rulings Compendium WordPress REST API.

Fetches rulings from compendium.pokegym.net and caches the result
to data/sources/compendium_rulings.json.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://compendium.pokegym.net/wp-json/wp/v2"
_RATE_LIMIT_SLEEP = 0.2  # 200ms between requests
_CACHE_MAX_AGE_DAYS = 7
_PER_PAGE = 100


def _strip_html(html: str) -> str:
    """Strip HTML tags and decode entities to plain text."""
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</?p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    # Decode common HTML entities
    text = text.replace("&amp;", "&")
    text = text.replace("&lt;", "<")
    text = text.replace("&gt;", ">")
    text = text.replace("&quot;", '"')
    text = text.replace("&#8217;", "'")
    text = text.replace("&#8220;", '"')
    text = text.replace("&#8221;", '"')
    text = text.replace("&#8211;", "-")
    text = text.replace("&#8212;", "--")
    text = text.replace("&nbsp;", " ")
    # Collapse whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_categories(client: httpx.Client) -> list[dict[str, Any]]:
    """Fetch all categories from the WordPress REST API."""
    categories: list[dict[str, Any]] = []
    page = 1

    while True:
        resp = client.get(
            f"{_BASE_URL}/categories",
            params={"per_page": _PER_PAGE, "page": page},
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        categories.extend(batch)

        try:
            total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
        except ValueError:
            total_pages = 1
        if page >= total_pages:
            break
        page += 1
        time.sleep(_RATE_LIMIT_SLEEP)

    logger.info("Fetched %d categories", len(categories))
    return categories


def fetch_posts_for_category(
    client: httpx.Client, category_id: int, category_name: str
) -> list[dict[str, Any]]:
    """Fetch all posts for a category, handling pagination."""
    posts: list[dict[str, Any]] = []
    page = 1

    while True:
        resp = client.get(
            f"{_BASE_URL}/posts",
            params={
                "categories": category_id,
                "per_page": _PER_PAGE,
                "page": page,
            },
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break

        for post in batch:
            posts.append({
                "id": post["id"],
                "title": post.get("title", {}).get("rendered", ""),
                "content": post.get("content", {}).get("rendered", ""),
                "date": post.get("date", ""),
                "category_id": category_id,
                "category_name": category_name,
            })

        try:
            total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
        except ValueError:
            total_pages = 1
        if page >= total_pages:
            break
        page += 1
        time.sleep(_RATE_LIMIT_SLEEP)

    return posts


def fetch_all_rulings(
    output_path: str | Path,
    force: bool = False,
) -> Path:
    """Fetch all Compendium rulings and write to JSON cache.

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

    with httpx.Client(
        timeout=30.0,
        headers={"Accept": "application/json"},
        follow_redirects=True,
    ) as client:
        categories = fetch_categories(client)

        # Build category hierarchy
        category_map: dict[int, dict[str, Any]] = {}
        for cat in categories:
            category_map[cat["id"]] = {
                "id": cat["id"],
                "name": _strip_html(cat.get("name", "")),
                "parent": cat.get("parent", 0),
                "count": cat.get("count", 0),
            }

        all_posts: list[dict[str, Any]] = []
        for cat in categories:
            cat_id = cat["id"]
            cat_name = _strip_html(cat.get("name", ""))
            post_count = cat.get("count", 0)
            if post_count == 0:
                continue

            logger.info("Fetching %d posts from category: %s", post_count, cat_name)
            posts = fetch_posts_for_category(client, cat_id, cat_name)
            all_posts.extend(posts)
            logger.info("  Fetched %d posts (total: %d)", len(posts), len(all_posts))
            time.sleep(_RATE_LIMIT_SLEEP)

    # Strip HTML from post content
    for post in all_posts:
        post["content"] = _strip_html(post["content"])
        post["title"] = _strip_html(post["title"])

    result = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_posts": len(all_posts),
        "categories": list(category_map.values()),
        "posts": all_posts,
    }

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
    logger.info("Wrote %d rulings to %s", len(all_posts), output_path)
    return output_path

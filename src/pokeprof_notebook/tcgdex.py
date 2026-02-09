"""Synchronous TCGDex API client for PokéProf Notebook.

Fetches standard-legal card data from the TCGDex REST API and caches
the result to data/sources/tcgdex_cards.json.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.tcgdex.net/v2"
_RATE_LIMIT_SLEEP = 0.1  # 100ms between individual card requests
_CACHE_MAX_AGE_DAYS = 7
_MAX_FAILURE_RATE = 0.2  # Abort if >20% of cards in a set fail


def fetch_standard_sets(client: httpx.Client) -> list[dict[str, Any]]:
    """Fetch all sets and filter to standard-legal ones."""
    resp = client.get(f"{_BASE_URL}/en/sets")
    resp.raise_for_status()
    all_sets = resp.json()

    standard_sets = []
    for s in all_sets:
        # Fetch full set details to check legal status
        set_resp = client.get(f"{_BASE_URL}/en/sets/{s['id']}")
        set_resp.raise_for_status()
        set_data = set_resp.json()
        time.sleep(_RATE_LIMIT_SLEEP)

        legal = set_data.get("legal", {})
        if legal.get("standard"):
            standard_sets.append(set_data)
            logger.info(
                "Standard set: %s (%s) — %d cards",
                set_data["name"],
                set_data["id"],
                len(set_data.get("cards", [])),
            )

    logger.info("Found %d standard-legal sets", len(standard_sets))
    return standard_sets


def fetch_cards_for_set(
    client: httpx.Client, set_data: dict[str, Any]
) -> list[dict[str, Any]]:
    """Fetch full card details for every card in a set."""
    cards = []
    card_summaries = set_data.get("cards", [])

    failed = 0
    for card_summary in card_summaries:
        card_id = card_summary["id"]
        try:
            resp = client.get(f"{_BASE_URL}/en/cards/{card_id}")
            resp.raise_for_status()
            cards.append(resp.json())
        except (httpx.HTTPError, json.JSONDecodeError) as e:
            failed += 1
            logger.warning("Failed to fetch card %s: %s", card_id, e)
        time.sleep(_RATE_LIMIT_SLEEP)

    if failed:
        total = len(card_summaries)
        failure_rate = failed / total if total else 0
        logger.warning(
            "Failed to fetch %d/%d cards from set %s (%.0f%%)",
            failed, total, set_data.get("name", "unknown"), failure_rate * 100,
        )
        if failure_rate > _MAX_FAILURE_RATE:
            raise RuntimeError(
                f"Too many failures fetching set {set_data.get('name', 'unknown')}: "
                f"{failed}/{total} cards failed ({failure_rate:.0%})"
            )
    return cards


def fetch_all_standard_cards(
    output_path: str | Path,
    force: bool = False,
) -> Path:
    """Fetch all standard-legal cards and write to JSON cache.

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
                        "Card cache is %d days old (max %d), skipping fetch",
                        age_days,
                        _CACHE_MAX_AGE_DAYS,
                    )
                    return output_path
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning("Card cache appears corrupt, re-fetching: %s", e)

    with httpx.Client(
        timeout=30.0,
        headers={"Accept": "application/json"},
        follow_redirects=True,
    ) as client:
        standard_sets = fetch_standard_sets(client)

        all_cards: list[dict[str, Any]] = []
        for set_data in standard_sets:
            logger.info(
                "Fetching cards for %s (%s)...",
                set_data["name"],
                set_data["id"],
            )
            cards = fetch_cards_for_set(client, set_data)
            all_cards.extend(cards)
            logger.info(
                "  Fetched %d cards from %s (total: %d)",
                len(cards),
                set_data["name"],
                len(all_cards),
            )

    result = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "total_cards": len(all_cards),
        "sets_fetched": len(standard_sets),
        "set_names": [s["name"] for s in standard_sets],
        "cards": all_cards,
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
    logger.info("Wrote %d cards to %s", len(all_cards), output_path)
    return output_path

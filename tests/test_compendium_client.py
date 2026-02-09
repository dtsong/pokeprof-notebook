"""Tests for pokeprof_notebook.compendium — HTML scraping and cache-aware fetching."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from pokeprof_notebook.compendium import _parse_rulings_page, fetch_all_rulings


# ── HTML parsing ──


SAMPLE_HTML = """\
<html><body>
<main class="site-content">
  <h3>Errata</h3>
  <h4>Rare Candy</h4>
  <div class="ruling-101">
    <dl class="single-entry">
      <dd>You may use Rare Candy on a Pokemon during your first turn.</dd>
    </dl>
    <div id="source">
      <span style="font-weight: bold;">Source:</span>
      PUI Rules Team (2023-06-15)
    </div>
  </div>
  <div class="ruling-102">
    <dl class="single-entry">
      <dd>Rare Candy can skip the Stage 1 form entirely.</dd>
    </dl>
    <div id="source">
      <span style="font-weight: bold;">Source:</span>
      PUI Rules Team (2024-01-10)
    </div>
  </div>
  <h4>Professor Oak</h4>
  <div class="ruling-201">
    <dl class="single-entry">
      <dd>Discard your hand, then draw 7 cards.</dd>
    </dl>
    <div id="source">
      <span style="font-weight: bold;">Source:</span>
      PUI Rules Team (2022-03-01)
    </div>
  </div>
  <h3>Attacks</h3>
  <h4>Thunderbolt</h4>
  <div class="ruling-301">
    <dl class="single-entry">
      <dd>You must discard all Energy attached to the Pokemon.</dd>
    </dl>
    <div id="source">
      <span style="font-weight: bold;">Source:</span>
      PUI Rules Team (2023-11-20)
    </div>
  </div>
</main>
</body></html>
"""


class TestParseRulingsPage:
    def test_parses_categories(self):
        result = _parse_rulings_page(SAMPLE_HTML)
        cat_names = {c["name"] for c in result["categories"]}
        assert "Errata" in cat_names
        assert "Attacks" in cat_names

    def test_parses_topics_as_posts(self):
        result = _parse_rulings_page(SAMPLE_HTML)
        titles = {p["title"] for p in result["posts"]}
        assert titles == {"Rare Candy", "Professor Oak", "Thunderbolt"}

    def test_groups_rulings_under_topic(self):
        result = _parse_rulings_page(SAMPLE_HTML)
        rare_candy = next(p for p in result["posts"] if p["title"] == "Rare Candy")
        # Should contain both rulings concatenated
        assert "first turn" in rare_candy["content"]
        assert "skip the Stage 1" in rare_candy["content"]

    def test_extracts_dates(self):
        result = _parse_rulings_page(SAMPLE_HTML)
        rare_candy = next(p for p in result["posts"] if p["title"] == "Rare Candy")
        # Should have the latest date from its rulings
        assert rare_candy["date"] == "2024-01-10"

    def test_assigns_category_ids(self):
        result = _parse_rulings_page(SAMPLE_HTML)
        rare_candy = next(p for p in result["posts"] if p["title"] == "Rare Candy")
        assert rare_candy["category_name"] == "Errata"
        assert rare_candy["category_id"] == 1  # Errata is first in _CATEGORY_NAMES

        thunderbolt = next(p for p in result["posts"] if p["title"] == "Thunderbolt")
        assert thunderbolt["category_name"] == "Attacks"
        assert thunderbolt["category_id"] == 3  # Attacks is third

    def test_total_posts_count(self):
        result = _parse_rulings_page(SAMPLE_HTML)
        assert result["total_posts"] == 3

    def test_category_counts(self):
        result = _parse_rulings_page(SAMPLE_HTML)
        cat_map = {c["name"]: c["count"] for c in result["categories"]}
        assert cat_map["Errata"] == 2  # Rare Candy + Professor Oak
        assert cat_map["Attacks"] == 1  # Thunderbolt

    def test_includes_source_in_content(self):
        result = _parse_rulings_page(SAMPLE_HTML)
        thunderbolt = next(p for p in result["posts"] if p["title"] == "Thunderbolt")
        assert "Source:" in thunderbolt["content"]
        assert "PUI Rules Team" in thunderbolt["content"]

    def test_empty_categories_excluded(self):
        result = _parse_rulings_page(SAMPLE_HTML)
        cat_names = {c["name"] for c in result["categories"]}
        # Only categories with actual posts should appear
        assert "Trainers" not in cat_names
        assert "Energy" not in cat_names

    def test_raises_on_empty_html(self):
        with pytest.raises(ValueError, match="Could not find main content"):
            _parse_rulings_page("")

    def test_fetched_at_is_set(self):
        result = _parse_rulings_page(SAMPLE_HTML)
        assert "fetched_at" in result
        # Should be parseable as ISO datetime
        datetime.fromisoformat(result["fetched_at"])


# ── fetch_all_rulings cache behaviour ──


class TestFetchAllRulings:
    def _write_cache(self, path, fetched_at: str | None = None, corrupt: bool = False):
        if corrupt:
            path.write_text("{bad json", encoding="utf-8")
        else:
            data = {
                "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(),
                "total_posts": 0,
                "categories": [],
                "posts": [],
            }
            path.write_text(json.dumps(data), encoding="utf-8")

    def test_skips_fresh_cache(self, tmp_path):
        cache_file = tmp_path / "rulings.json"
        self._write_cache(cache_file)

        with patch("pokeprof_notebook.compendium.httpx.Client") as mock_client_cls:
            result = fetch_all_rulings(cache_file)

        assert result == cache_file
        mock_client_cls.assert_not_called()

    def test_force_ignores_cache(self, tmp_path):
        cache_file = tmp_path / "rulings.json"
        self._write_cache(cache_file)

        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_HTML
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("pokeprof_notebook.compendium.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            fetch_all_rulings(cache_file, force=True)

        mock_client_cls.assert_called_once()

    def test_corrupt_cache_triggers_refetch(self, tmp_path):
        cache_file = tmp_path / "rulings.json"
        self._write_cache(cache_file, corrupt=True)

        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_HTML
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("pokeprof_notebook.compendium.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            fetch_all_rulings(cache_file)

        mock_client_cls.assert_called_once()

    def test_writes_valid_json(self, tmp_path):
        cache_file = tmp_path / "rulings.json"

        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_HTML
        mock_resp.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("pokeprof_notebook.compendium.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            fetch_all_rulings(cache_file, force=True)

        data = json.loads(cache_file.read_text(encoding="utf-8"))
        assert data["total_posts"] == 3
        assert len(data["posts"]) == 3
        assert len(data["categories"]) > 0

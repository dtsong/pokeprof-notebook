"""Tests for pokeprof_notebook.compendium — HTML stripping and cache-aware fetching."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from pokeprof_notebook.compendium import _strip_html, fetch_all_rulings


# ── HTML stripping ──


class TestStripHtml:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            pytest.param("<b>bold</b>", "bold", id="removes_tags"),
            pytest.param("line1<br/>line2", "line1\nline2", id="br_to_newline"),
            pytest.param(
                "<p>para1</p><p>para2</p>",
                "para1\n\npara2",
                id="p_to_newline",
            ),
            pytest.param("&amp; &lt;", "& <", id="decodes_entities"),
            pytest.param("a\n\n\n\nb", "a\n\nb", id="collapses_whitespace"),
        ],
    )
    def test_strip_html(self, raw: str, expected: str):
        result = _strip_html(raw)
        assert result == expected


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

        mock_client = MagicMock()
        # categories endpoint returns empty list (no posts to fetch)
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.headers = {"X-WP-TotalPages": "1"}
        mock_client.get.return_value = mock_resp

        with patch("pokeprof_notebook.compendium.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            fetch_all_rulings(cache_file, force=True)

        mock_client_cls.assert_called_once()

    def test_corrupt_cache_triggers_refetch(self, tmp_path):
        cache_file = tmp_path / "rulings.json"
        self._write_cache(cache_file, corrupt=True)

        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        mock_resp.headers = {"X-WP-TotalPages": "1"}
        mock_client.get.return_value = mock_resp

        with patch("pokeprof_notebook.compendium.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            fetch_all_rulings(cache_file)

        mock_client_cls.assert_called_once()

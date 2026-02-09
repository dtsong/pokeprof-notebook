"""Tests for pokeprof_notebook.tcgdex — set filtering, card fetching, and cache logic."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest

from pokeprof_notebook.tcgdex import (
    fetch_all_standard_cards,
    fetch_cards_for_set,
    fetch_standard_sets,
)


# ── fetch_standard_sets ──


class TestFetchStandardSets:
    def _mock_client(self, sets_summary, set_details):
        """Build a mock client whose .get() returns appropriate responses."""
        client = MagicMock()

        def side_effect(url):
            resp = MagicMock()
            if url.endswith("/en/sets"):
                resp.json.return_value = sets_summary
            else:
                # Match set detail URL to the right detail dict
                set_id = url.rsplit("/", 1)[-1]
                resp.json.return_value = set_details[set_id]
            resp.raise_for_status.return_value = None
            return resp

        client.get.side_effect = side_effect
        return client

    def test_filters_standard_sets(self):
        summary = [{"id": "sv1"}, {"id": "xy1"}]
        details = {
            "sv1": {"id": "sv1", "name": "SV1", "legal": {"standard": True}, "cards": []},
            "xy1": {"id": "xy1", "name": "XY1", "legal": {"standard": False}, "cards": []},
        }
        client = self._mock_client(summary, details)
        result = fetch_standard_sets(client)
        assert len(result) == 1
        assert result[0]["id"] == "sv1"

    def test_non_standard_excluded(self):
        summary = [{"id": "xy1"}, {"id": "bw1"}]
        details = {
            "xy1": {"id": "xy1", "name": "XY1", "legal": {"standard": False}, "cards": []},
            "bw1": {"id": "bw1", "name": "BW1", "legal": {}, "cards": []},
        }
        client = self._mock_client(summary, details)
        result = fetch_standard_sets(client)
        assert result == []


# ── fetch_cards_for_set ──


class TestFetchCardsForSet:
    def test_fetches_all_cards(self):
        client = MagicMock()
        resp = MagicMock()
        resp.json.return_value = {"name": "Pikachu", "id": "sv1-25"}
        resp.raise_for_status.return_value = None
        client.get.return_value = resp

        set_data = {"name": "SV1", "cards": [{"id": "sv1-25"}, {"id": "sv1-26"}]}
        result = fetch_cards_for_set(client, set_data)
        assert len(result) == 2

    def test_tolerates_low_failure_rate(self):
        client = MagicMock()
        call_count = 0

        def side_effect(url):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPError("network error")
            resp = MagicMock()
            resp.json.return_value = {"name": "Card", "id": "x"}
            resp.raise_for_status.return_value = None
            return resp

        client.get.side_effect = side_effect

        # 1 failure out of 10 = 10% < 20% threshold
        set_data = {"name": "SV1", "cards": [{"id": f"c{i}"} for i in range(10)]}
        result = fetch_cards_for_set(client, set_data)
        assert len(result) == 9

    def test_aborts_on_high_failure_rate(self):
        client = MagicMock()
        client.get.side_effect = httpx.HTTPError("network error")

        # All 5 fail → 100% > 20% threshold
        set_data = {"name": "SV1", "cards": [{"id": f"c{i}"} for i in range(5)]}
        with pytest.raises(RuntimeError, match="Too many failures"):
            fetch_cards_for_set(client, set_data)


# ── fetch_all_standard_cards cache behaviour ──


class TestFetchAllStandardCards:
    def _write_cache(self, path, fetched_at: str | None = None, corrupt: bool = False):
        if corrupt:
            path.write_text("{bad json", encoding="utf-8")
        else:
            data = {
                "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(),
                "total_cards": 0,
                "sets_fetched": 0,
                "set_names": [],
                "cards": [],
            }
            path.write_text(json.dumps(data), encoding="utf-8")

    def test_skips_fresh_cache(self, tmp_path):
        cache_file = tmp_path / "cards.json"
        self._write_cache(cache_file)

        with patch("pokeprof_notebook.tcgdex.httpx.Client") as mock_client_cls:
            result = fetch_all_standard_cards(cache_file)

        assert result == cache_file
        mock_client_cls.assert_not_called()

    def test_force_ignores_cache(self, tmp_path):
        cache_file = tmp_path / "cards.json"
        self._write_cache(cache_file)

        mock_client = MagicMock()
        # /en/sets returns empty list so loop body is never entered
        sets_resp = MagicMock()
        sets_resp.json.return_value = []
        sets_resp.raise_for_status.return_value = None
        mock_client.get.return_value = sets_resp

        with patch("pokeprof_notebook.tcgdex.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            fetch_all_standard_cards(cache_file, force=True)

        mock_client_cls.assert_called_once()

    def test_corrupt_cache_triggers_refetch(self, tmp_path):
        cache_file = tmp_path / "cards.json"
        self._write_cache(cache_file, corrupt=True)

        mock_client = MagicMock()
        sets_resp = MagicMock()
        sets_resp.json.return_value = []
        sets_resp.raise_for_status.return_value = None
        mock_client.get.return_value = sets_resp

        with patch("pokeprof_notebook.tcgdex.httpx.Client") as mock_client_cls:
            mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
            fetch_all_standard_cards(cache_file)

        mock_client_cls.assert_called_once()

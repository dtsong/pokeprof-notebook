"""Tests for overlay manifest builder."""

from __future__ import annotations

import json

import pytest

from pokeprof_notebook.overlay import (
    ErrataOverlay,
    OverlayManifest,
    annotate_sections,
    build_overlay,
    load_overlay,
    lookup_card_errata,
    save_overlay,
)
from pokeprof_notebook.types import DocumentType
from conftest import make_node, make_section


def _write_errata_file(path, entries):
    """Helper to write a JSON errata file."""
    path.write_text(json.dumps(entries), encoding="utf-8")


class TestBuildOverlay:
    """Tests for build_overlay()."""

    def test_single_file_populates_manifest(self, tmp_path):
        f = tmp_path / "errata.json"
        _write_errata_file(f, [
            {"card_name": "Charizard ex", "new_text": "new", "old_text": "old"},
        ])

        manifest = build_overlay([f])

        assert "charizard ex" in manifest.card_errata
        assert len(manifest.card_errata["charizard ex"]) == 1
        entry = manifest.card_errata["charizard ex"][0]
        assert entry.card_name == "Charizard ex"
        assert entry.new_text == "new"
        assert entry.old_text == "old"
        assert entry.source == "errata"  # defaults to path.stem

    def test_multiple_files_merged(self, tmp_path):
        f1 = tmp_path / "a.json"
        f2 = tmp_path / "b.json"
        _write_errata_file(f1, [
            {"card_name": "Pikachu", "new_text": "n1", "old_text": "o1"},
        ])
        _write_errata_file(f2, [
            {"card_name": "Pikachu", "new_text": "n2", "old_text": "o2", "source": "set-b"},
        ])

        manifest = build_overlay([f1, f2])

        assert len(manifest.card_errata["pikachu"]) == 2

    def test_corrupt_json_skipped(self, tmp_path):
        good = tmp_path / "good.json"
        bad = tmp_path / "bad.json"
        _write_errata_file(good, [
            {"card_name": "Mewtwo", "new_text": "n", "old_text": "o"},
        ])
        bad.write_text("{invalid json", encoding="utf-8")

        manifest = build_overlay([good, bad])

        assert "mewtwo" in manifest.card_errata

    def test_malformed_entry_skipped(self, tmp_path):
        f = tmp_path / "errata.json"
        _write_errata_file(f, [
            {"new_text": "n", "old_text": "o"},  # missing card_name
            {"card_name": "Valid", "new_text": "n", "old_text": "o"},
        ])

        manifest = build_overlay([f])

        assert len(manifest.card_errata) == 1
        assert "valid" in manifest.card_errata

    def test_keys_are_lowercase(self, tmp_path):
        f = tmp_path / "errata.json"
        _write_errata_file(f, [
            {"card_name": "Gardevoir EX", "new_text": "n", "old_text": "o"},
        ])

        manifest = build_overlay([f])

        assert "gardevoir ex" in manifest.card_errata
        assert "Gardevoir EX" not in manifest.card_errata


class TestSaveAndLoadOverlay:
    """Tests for save_overlay() and load_overlay() round-trip."""

    def test_roundtrip_preserves_data(self, tmp_path):
        manifest = OverlayManifest(card_errata={
            "pikachu": [
                ErrataOverlay(
                    card_name="Pikachu",
                    new_text="new text",
                    old_text="old text",
                    source="errata-v1",
                ),
            ],
        })
        path = tmp_path / "overlay.json"

        save_overlay(manifest, path)
        loaded = load_overlay(path)

        assert "pikachu" in loaded.card_errata
        assert len(loaded.card_errata["pikachu"]) == 1
        entry = loaded.card_errata["pikachu"][0]
        assert entry.card_name == "Pikachu"
        assert entry.new_text == "new text"
        assert entry.old_text == "old text"
        assert entry.source == "errata-v1"

    def test_corrupt_json_returns_empty_manifest(self, tmp_path):
        path = tmp_path / "overlay.json"
        path.write_text("not json", encoding="utf-8")

        manifest = load_overlay(path)

        assert manifest.card_errata == {}

    def test_missing_file_returns_empty_manifest(self, tmp_path):
        path = tmp_path / "does_not_exist.json"

        manifest = load_overlay(path)

        assert manifest.card_errata == {}


class TestLookupCardErrata:
    """Tests for lookup_card_errata()."""

    def _manifest_with(self, *cards):
        manifest = OverlayManifest()
        for name in cards:
            manifest.card_errata[name.lower()] = [
                ErrataOverlay(card_name=name, new_text="n", old_text="o", source="s"),
            ]
        return manifest

    def test_finds_card_in_query(self):
        manifest = self._manifest_with("Charizard ex")
        results = lookup_card_errata(manifest, "What does Charizard ex do?")

        assert len(results) == 1
        assert results[0].card_name == "Charizard ex"

    def test_case_insensitive(self):
        manifest = self._manifest_with("Pikachu VMAX")
        results = lookup_card_errata(manifest, "tell me about pikachu vmax")

        assert len(results) == 1

    def test_no_match_returns_empty(self):
        manifest = self._manifest_with("Charizard ex")
        results = lookup_card_errata(manifest, "How does retreat cost work?")

        assert results == []

    def test_deduplicates_by_card_name(self):
        manifest = OverlayManifest()
        manifest.card_errata["pikachu"] = [
            ErrataOverlay(card_name="Pikachu", new_text="n1", old_text="o1", source="a"),
            ErrataOverlay(card_name="Pikachu", new_text="n2", old_text="o2", source="b"),
        ]
        results = lookup_card_errata(manifest, "pikachu attack damage")

        assert len(results) == 1


class TestAnnotateSections:
    """Tests for annotate_sections()."""

    def _manifest_with_card(self, card_name="Pikachu"):
        manifest = OverlayManifest()
        manifest.card_errata[card_name.lower()] = [
            ErrataOverlay(card_name=card_name, new_text="new", old_text="old", source="s"),
        ]
        return manifest

    def test_annotates_card_database_sections(self):
        node = make_node(document_type=DocumentType.CARD_DATABASE)
        section = make_section(node=node)
        manifest = self._manifest_with_card("Pikachu")

        result = annotate_sections([section], manifest, query="pikachu attack")

        assert len(result[0].errata_context) > 0

    def test_skips_non_card_database_sections(self):
        card_node = make_node(document_type=DocumentType.CARD_DATABASE)
        rule_node = make_node(document_type=DocumentType.RULEBOOK)
        card_section = make_section(node=card_node)
        rule_section = make_section(node=rule_node)
        manifest = self._manifest_with_card("Pikachu")

        annotate_sections([card_section, rule_section], manifest, query="pikachu")

        assert len(card_section.errata_context) > 0
        assert rule_section.errata_context == []

    def test_empty_query_no_annotation(self):
        node = make_node(document_type=DocumentType.CARD_DATABASE)
        section = make_section(node=node)
        manifest = self._manifest_with_card("Pikachu")

        annotate_sections([section], manifest, query="")

        assert section.errata_context == []

    def test_no_matching_errata_sections_unchanged(self):
        node = make_node(document_type=DocumentType.CARD_DATABASE)
        section = make_section(node=node)
        manifest = self._manifest_with_card("Charizard ex")

        annotate_sections([section], manifest, query="how does retreat work")

        assert section.errata_context == []

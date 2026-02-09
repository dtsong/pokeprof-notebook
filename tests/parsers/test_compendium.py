"""Tests for pokeprof_notebook.parsers.compendium — compendium rulings to markdown."""

from __future__ import annotations

import json

from pokeprof_notebook.parsers.compendium import rulings_to_markdown


class TestRulingsToMarkdown:
    def _write_json(self, tmp_path, data):
        source = tmp_path / "compendium_rulings.json"
        source.write_text(json.dumps(data), encoding="utf-8")
        return source

    def test_produces_heading(self, tmp_path):
        source = self._write_json(tmp_path, {"posts": [], "categories": []})
        output = tmp_path / "rulings.md"
        rulings_to_markdown(source, output)
        md = output.read_text(encoding="utf-8")
        assert md.startswith("# Pokemon Rulings Compendium")

    def test_groups_posts_by_category(self, tmp_path):
        data = {
            "posts": [
                {"title": "Rule A", "content": "Text A", "category_name": "Energy"},
                {"title": "Rule B", "content": "Text B", "category_name": "Trainers"},
            ],
            "categories": [],
        }
        source = self._write_json(tmp_path, data)
        output = tmp_path / "rulings.md"
        rulings_to_markdown(source, output)
        md = output.read_text(encoding="utf-8")
        assert "## Energy" in md
        assert "## Trainers" in md
        assert "### Rule A" in md
        assert "### Rule B" in md

    def test_sorts_categories_alphabetically(self, tmp_path):
        data = {
            "posts": [
                {"title": "X", "content": "", "category_name": "Zebra"},
                {"title": "Y", "content": "", "category_name": "Alpha"},
            ],
            "categories": [],
        }
        source = self._write_json(tmp_path, data)
        output = tmp_path / "rulings.md"
        rulings_to_markdown(source, output)
        md = output.read_text(encoding="utf-8")
        alpha_pos = md.index("## Alpha")
        zebra_pos = md.index("## Zebra")
        assert alpha_pos < zebra_pos

    def test_includes_date_in_output(self, tmp_path):
        data = {
            "posts": [
                {
                    "title": "Dated Rule",
                    "content": "Some ruling.",
                    "category_name": "General",
                    "date": "2024-06-15T12:00:00",
                },
            ],
            "categories": [],
        }
        source = self._write_json(tmp_path, data)
        output = tmp_path / "rulings.md"
        rulings_to_markdown(source, output)
        md = output.read_text(encoding="utf-8")
        assert "Source: compendium.pokegym.net | Date: 2024-06-15" in md

    def test_empty_posts_produces_just_heading(self, tmp_path):
        source = self._write_json(tmp_path, {"posts": [], "categories": []})
        output = tmp_path / "rulings.md"
        rulings_to_markdown(source, output)
        md = output.read_text(encoding="utf-8")
        lines = [l for l in md.strip().split("\n") if l.strip()]
        assert len(lines) == 1
        assert lines[0] == "# Pokemon Rulings Compendium"

    def test_writes_output_file(self, tmp_path):
        data = {
            "posts": [
                {"title": "Rule", "content": "Content", "category_name": "Cat"},
            ],
            "categories": [],
        }
        source = self._write_json(tmp_path, data)
        output = tmp_path / "out" / "rulings.md"
        result = rulings_to_markdown(source, output)
        assert result == output
        assert output.exists()

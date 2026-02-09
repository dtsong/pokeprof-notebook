"""Tests for pokeprof_notebook.parsers.html — HTML parsing and markdown conversion."""

from __future__ import annotations

from bs4 import BeautifulSoup

from pokeprof_notebook.parsers.html import (
    _find_main_content,
    _html_to_markdown,
    _list_to_markdown,
    _table_to_markdown,
    parse_html,
)


# ── Finding main content ──


class TestFindMainContent:
    def _soup(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "html.parser")

    def test_finds_main_tag(self):
        soup = self._soup("<html><body><main><p>Hello</p></main></body></html>")
        result = _find_main_content(soup)
        assert result.name == "main"

    def test_finds_article_tag(self):
        soup = self._soup("<html><body><article><p>Hello</p></article></body></html>")
        result = _find_main_content(soup)
        assert result.name == "article"

    def test_falls_back_to_body(self):
        soup = self._soup("<html><body><div><p>Hello</p></div></body></html>")
        result = _find_main_content(soup)
        assert result.name == "body"


# ── HTML to markdown conversion ──


class TestHtmlToMarkdown:
    def _element(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        return soup.find(True)  # first tag

    def test_heading_conversion(self):
        el = self._element("<div><h1>Title</h1><h3>Subtitle</h3></div>")
        lines = _html_to_markdown(el)
        assert "# Title" in lines
        assert "### Subtitle" in lines

    def test_paragraph_conversion(self):
        el = self._element("<div><p>Some paragraph text.</p></div>")
        lines = _html_to_markdown(el)
        assert "Some paragraph text." in lines

    def test_unordered_list(self):
        el = self._element("<div><ul><li>Alpha</li><li>Beta</li></ul></div>")
        lines = _html_to_markdown(el)
        text = "\n".join(lines)
        assert "- Alpha" in text
        assert "- Beta" in text

    def test_ordered_list(self):
        el = self._element("<div><ol><li>First</li><li>Second</li></ol></div>")
        lines = _html_to_markdown(el)
        text = "\n".join(lines)
        assert "1. First" in text
        assert "2. Second" in text

    def test_nested_list(self):
        el = self._element(
            "<div><ul>"
            "<li>Parent<ul><li>Child</li></ul></li>"
            "</ul></div>"
        )
        lines = _html_to_markdown(el)
        text = "\n".join(lines)
        assert "- Parent" in text
        assert "  - Child" in text

    def test_table_with_header_separator(self):
        el = self._element(
            "<div><table>"
            "<tr><th>Name</th><th>Type</th></tr>"
            "<tr><td>Pikachu</td><td>Electric</td></tr>"
            "</table></div>"
        )
        lines = _html_to_markdown(el)
        text = "\n".join(lines)
        assert "| Name | Type |" in text
        assert "| --- | --- |" in text
        assert "| Pikachu | Electric |" in text

    def test_script_and_style_removed_via_parse_html(self, tmp_path):
        html = (
            "<html><body><main>"
            "<script>alert('xss')</script>"
            "<style>.x{color:red}</style>"
            "<p>Real content</p>"
            "</main></body></html>"
        )
        source = tmp_path / "page.html"
        source.write_text(html, encoding="utf-8")
        output = tmp_path / "page.md"
        parse_html(source, output)
        md = output.read_text(encoding="utf-8")
        assert "alert" not in md
        assert "color:red" not in md
        assert "Real content" in md

    def test_div_recursion(self):
        el = self._element(
            "<div><div><p>Nested paragraph</p></div></div>"
        )
        lines = _html_to_markdown(el)
        assert "Nested paragraph" in lines


# ── End-to-end ──


class TestParseHtml:
    def test_creates_output_file(self, tmp_path):
        html = (
            "<html><body><main>"
            "<h1>Pokemon Rules</h1>"
            "<p>Turn order matters.</p>"
            "</main></body></html>"
        )
        source = tmp_path / "rules.html"
        source.write_text(html, encoding="utf-8")
        output = tmp_path / "out" / "rules.md"

        result = parse_html(source, output)

        assert result == output
        assert output.exists()
        md = output.read_text(encoding="utf-8")
        assert "# Pokemon Rules" in md
        assert "Turn order matters." in md

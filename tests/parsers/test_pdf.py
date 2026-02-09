"""Tests for pokeprof_notebook.parsers.pdf — PDF parsing and markdown cleanup."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from pokeprof_notebook.parsers.pdf import _clean_markdown, parse_pdf


# ── Markdown cleanup ──


class TestCleanMarkdown:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("-----\nsome text\n-----", "some text"),
            ("THE POKÉMON TRADING CARD GAME", ""),
            ("**THE POKEMON TRADING CARD GAME**", ""),
            ("### 2", ""),
            ("### 2.1 Title", "### 2.1 Title"),
            ("42", ""),
            ("Some normal text", "Some normal text"),
            ("**.**", ""),
            ("[:]", ""),
        ],
        ids=[
            "removes_page_breaks",
            "removes_header_with_accent",
            "removes_bold_header",
            "removes_page_number_heading",
            "preserves_real_heading",
            "removes_standalone_page_number",
            "preserves_normal_text",
            "removes_bold_dot_artifact",
            "removes_colon_artifact",
        ],
    )
    def test_clean_markdown(self, raw, expected):
        result = _clean_markdown(raw)
        # Strip leading/trailing blank lines for comparison
        assert result.strip() == expected


# ── PDF parsing ──


class TestParsePdf:
    def test_calls_pymupdf_and_writes_output(self, tmp_path):
        source = tmp_path / "input.pdf"
        source.write_bytes(b"fake pdf content")
        output = tmp_path / "out" / "output.md"

        mock_pymupdf = MagicMock()
        mock_pymupdf.to_markdown.return_value = "# Heading\nSome text\n"

        with patch.dict(sys.modules, {"pymupdf4llm": mock_pymupdf}):
            result = parse_pdf(source, output)

        mock_pymupdf.to_markdown.assert_called_once_with(
            str(source), show_progress=False
        )
        assert result == output
        assert output.exists()
        assert "# Heading" in output.read_text(encoding="utf-8")

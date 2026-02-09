"""Tests for pokeprof_notebook.indexer — PageIndex tree building, persistence, validation."""

from __future__ import annotations

import json

import pytest

from pokeprof_notebook.indexer import (
    _count_tokens,
    file_hash,
    index_document,
    load_tree,
    save_tree,
    validate_tree,
)
from pokeprof_notebook.types import DocumentType, NodeMetadata, TreeNode

from conftest import make_index, make_node


# ── Token counting ──


class TestCountTokens:
    def test_empty_string_returns_zero(self):
        assert _count_tokens("") == 0

    def test_simple_text_returns_positive(self):
        result = _count_tokens("The quick brown fox jumps over the lazy dog.")
        assert result > 0

    def test_unicode_text_returns_positive(self):
        result = _count_tokens("Pokémon Trading Card Game")
        assert result > 0


# ── File hashing ──


class TestFileHash:
    def test_deterministic_for_same_content(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("same content")
        f2.write_text("same content")
        assert file_hash(f1) == file_hash(f2)

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content A")
        f2.write_text("content B")
        assert file_hash(f1) != file_hash(f2)


# ── Document indexing ──


class TestIndexDocument:
    def test_single_heading_one_child(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# Introduction\nSome text here.\n")
        idx = index_document(md, "test", DocumentType.RULEBOOK)
        assert len(idx.root.children) == 1
        assert idx.root.children[0].metadata.title == "Introduction"

    def test_nested_headings_proper_hierarchy(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text(
            "## Chapter\nChapter text.\n"
            "### Section\nSection text.\n"
            "#### Subsection\nSubsection text.\n"
        )
        idx = index_document(md, "test", DocumentType.RULEBOOK)
        root = idx.root
        assert len(root.children) == 1
        chapter = root.children[0]
        assert chapter.metadata.title == "Chapter"
        assert len(chapter.children) == 1
        section = chapter.children[0]
        assert section.metadata.title == "Section"
        assert len(section.children) == 1
        subsection = section.children[0]
        assert subsection.metadata.title == "Subsection"

    @pytest.mark.parametrize(
        "heading, expected_num, expected_title",
        [
            ("## 1.2 Title", "1.2", "Title"),
            ("## 3 Overview", "3", "Overview"),
            ("## 1.2.a Energy Rules", "1.2.a", "Energy Rules"),
        ],
    )
    def test_section_number_parsing(
        self, tmp_path, heading, expected_num, expected_title
    ):
        md = tmp_path / "doc.md"
        md.write_text(f"{heading}\nContent.\n")
        idx = index_document(md, "test", DocumentType.PENALTY_GUIDELINES)
        child = idx.root.children[0]
        assert child.metadata.section_number == expected_num
        assert child.metadata.title == expected_title

    def test_duplicate_headings_get_unique_ids(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("## Overview\nFirst.\n## Overview\nSecond.\n## Overview\nThird.\n")
        idx = index_document(md, "test", DocumentType.RULEBOOK)
        ids = [c.id for c in idx.root.children]
        assert len(ids) == 3
        assert len(set(ids)) == 3  # all unique

    def test_blank_lines_preserved_between_paragraphs(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# Section\nParagraph one.\n\nParagraph two.\n")
        idx = index_document(md, "test", DocumentType.RULEBOOK)
        content = idx.root.children[0].content
        assert "Paragraph one." in content
        assert "Paragraph two." in content
        assert "\n\n" in content

    def test_node_token_counts_positive(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# Title\nSome content with several words in it.\n")
        idx = index_document(md, "test", DocumentType.RULEBOOK)
        child = idx.root.children[0]
        assert child.token_count > 0

    def test_empty_markdown_no_children(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("")
        idx = index_document(md, "test", DocumentType.RULEBOOK)
        assert len(idx.root.children) == 0

    def test_total_tokens_equals_sum(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# A\nText A.\n## B\nText B.\n")
        idx = index_document(md, "test", DocumentType.RULEBOOK)
        expected = sum(n.token_count for n in idx.root.walk())
        assert idx.total_tokens == expected

    def test_document_metadata(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# Heading\nBody.\n")
        idx = index_document(md, "my_doc", DocumentType.LEGAL_CARD_LIST)
        assert idx.document_name == "my_doc"
        assert idx.document_type == DocumentType.LEGAL_CARD_LIST

    def test_content_without_heading_goes_to_root(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("Just some text without any heading.\n")
        idx = index_document(md, "test", DocumentType.RULEBOOK)
        assert len(idx.root.children) == 0
        assert idx.root.content != ""


# ── Save / Load roundtrip ──


class TestSaveAndLoadTree:
    def test_roundtrip_preserves_data(self, tmp_path):
        idx = make_index(document_name="rulebook", source_hash="deadbeef")
        path = tmp_path / "index.json"
        save_tree(idx, path)
        loaded = load_tree(path)
        assert loaded.document_name == idx.document_name
        assert loaded.document_type == idx.document_type
        assert loaded.total_tokens == idx.total_tokens
        assert loaded.source_hash == idx.source_hash

    def test_preserves_children_hierarchy(self, tmp_path):
        grandchild = make_node(id="gc", content="gc content", title="GC", token_count=2)
        child = make_node(
            id="child", content="child content", title="Child",
            children=[grandchild], token_count=3,
        )
        root = make_node(id="root", content="", title="Root", children=[child])
        idx = make_index(root=root, total_tokens=5)
        path = tmp_path / "index.json"
        save_tree(idx, path)
        loaded = load_tree(path)
        assert len(loaded.root.children) == 1
        assert loaded.root.children[0].id == "child"
        assert len(loaded.root.children[0].children) == 1
        assert loaded.root.children[0].children[0].id == "gc"

    def test_missing_file_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_tree(tmp_path / "nonexistent.json")

    def test_corrupt_json_raises_value_error(self, tmp_path):
        path = tmp_path / "corrupt.json"
        path.write_text("{bad json!!")
        with pytest.raises(ValueError, match="Corrupt index file"):
            load_tree(path)

    def test_invalid_structure_raises_value_error(self, tmp_path):
        path = tmp_path / "bad_struct.json"
        path.write_text(json.dumps({"document_name": "x", "document_type": "rulebook"}))
        with pytest.raises((ValueError, KeyError)):
            load_tree(path)


# ── Validate tree ──


class TestValidateTree:
    def test_valid_tree_returns_empty(self):
        idx = make_index()
        issues = validate_tree(idx)
        assert issues == []

    def test_duplicate_id_detected(self):
        dup1 = make_node(id="same", content="a", title="A")
        dup2 = make_node(id="same", content="b", title="B")
        root = make_node(id="root", content="", title="Root", children=[dup1, dup2])
        idx = make_index(root=root)
        issues = validate_tree(idx)
        assert any("Duplicate" in i for i in issues)

    def test_section_pattern_mismatch_detected(self):
        child = make_node(
            id="bad", content="x", section_number="abc", title="Bad"
        )
        root = make_node(id="root", content="", title="Root", children=[child])
        idx = make_index(root=root)
        issues = validate_tree(idx, expected_pattern=r"^\d+\.\d+$")
        assert any("doesn't match pattern" in i for i in issues)

    def test_no_pattern_skips_section_check(self):
        child = make_node(
            id="node", content="x", section_number="anything_goes", title="Node"
        )
        root = make_node(id="root", content="", title="Root", children=[child])
        idx = make_index(root=root)
        issues = validate_tree(idx)
        assert issues == []

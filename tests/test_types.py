"""Tests for pokeprof_notebook.types — domain models."""

from __future__ import annotations

import pytest

from pokeprof_notebook.types import DocumentType, DomainConfig, NodeMetadata, TreeNode


class TestTreeNode:
    """TreeNode.walk() traversal tests."""

    def test_walk_leaf_returns_single_item(self):
        meta = NodeMetadata(document_type=DocumentType.RULEBOOK)
        leaf = TreeNode(id="leaf", content="Leaf content", metadata=meta)
        result = leaf.walk()
        assert len(result) == 1
        assert result[0] is leaf

    def test_walk_dfs_order(self, sample_tree):
        nodes = sample_tree.walk()
        ids = [n.id for n in nodes]
        assert ids == ["root", "1", "1.1", "1.2", "2", "2.1", "2.2"]

    def test_walk_count_matches_tree_size(self, sample_tree):
        assert len(sample_tree.walk()) == 7

    def test_leaf_has_empty_children(self):
        meta = NodeMetadata(document_type=DocumentType.RULEBOOK)
        leaf = TreeNode(id="leaf", content="", metadata=meta)
        assert leaf.children == []


class TestDomainConfig:
    """DomainConfig.from_yaml() loading tests."""

    def test_from_yaml_happy_path(self, tmp_path):
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "domain_name: pokemon_tcg\n"
            "routing_hints:\n"
            "  rulebook:\n"
            "    - rule\n"
            "    - energy\n"
        )
        config = DomainConfig.from_yaml(cfg_file)
        assert config.domain_name == "pokemon_tcg"
        assert config.routing_hints == {"rulebook": ["rule", "energy"]}

    def test_from_yaml_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            DomainConfig.from_yaml(tmp_path / "nonexistent.yaml")

    def test_from_yaml_missing_domain_name_raises(self, tmp_path):
        cfg_file = tmp_path / "bad.yaml"
        cfg_file.write_text("routing_hints: {}\n")
        with pytest.raises(KeyError):
            DomainConfig.from_yaml(cfg_file)


class TestDocumentType:
    """DocumentType enum completeness tests."""

    @pytest.mark.parametrize(
        "member, value",
        [
            (DocumentType.RULEBOOK, "rulebook"),
            (DocumentType.PENALTY_GUIDELINES, "penalty_guidelines"),
            (DocumentType.LEGAL_CARD_LIST, "legal_card_list"),
            (DocumentType.RULINGS_COMPENDIUM, "rulings_compendium"),
            (DocumentType.CARD_DATABASE, "card_database"),
        ],
    )
    def test_enum_value(self, member, value):
        assert member.value == value

    def test_enum_has_exactly_five_members(self):
        assert len(DocumentType) == 5

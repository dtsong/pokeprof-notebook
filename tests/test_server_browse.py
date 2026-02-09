"""Tests for browse API endpoints (GET /api/indexes, tree, node)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from conftest import make_index, make_node


@pytest.fixture
def indexes_dir(tmp_path):
    """Create a temp directory with test index files."""
    from pokeprof_notebook.indexer import save_tree
    from pokeprof_notebook.types import DocumentType

    # Create a proper index with hierarchy
    root = make_node(id="root", title="Test Rulebook", children=[
        make_node(
            id="1",
            content="Section 1 content about basic rules.",
            section_number="1",
            title="Basic Rules",
            token_count=8,
            children=[
                make_node(
                    id="1.1",
                    content="Subsection about energy cards.",
                    section_number="1.1",
                    title="Energy",
                    token_count=5,
                ),
            ],
        ),
        make_node(
            id="2",
            content="Section 2 content about battles.",
            section_number="2",
            title="Battles",
            token_count=6,
        ),
    ])

    idx = make_index(
        document_name="rulebook",
        root=root,
        total_tokens=19,
    )
    save_tree(idx, tmp_path / "rulebook.json")

    # Create a second index
    small_root = make_node(id="root", title="Penalties", children=[
        make_node(
            id="pg1",
            content="Minor infraction rules.",
            section_number="1",
            title="Minor Infractions",
            token_count=4,
        ),
    ])
    pg_idx = make_index(
        document_name="penalty_guidelines",
        document_type=DocumentType.PENALTY_GUIDELINES,
        root=small_root,
        total_tokens=4,
    )
    save_tree(pg_idx, tmp_path / "penalty_guidelines.json")

    # Create non-index files that should be excluded
    (tmp_path / "overlay_manifest.json").write_text("{}")
    (tmp_path / "card_name_index.json").write_text("{}")

    return tmp_path


@pytest.fixture
def client(indexes_dir):
    """FastAPI test client with mocked indexes directory."""
    with patch("pokeprof_notebook.server._INDEXES_DIR", indexes_dir), \
         patch("pokeprof_notebook.server._SPA_DIR", Path("/nonexistent")):
        from pokeprof_notebook.server import app
        yield TestClient(app)


class TestListIndexes:
    def test_returns_list(self, client):
        resp = client.get("/api/indexes")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 2

    def test_contains_expected_fields(self, client):
        resp = client.get("/api/indexes")
        data = resp.json()
        names = {item["name"] for item in data}
        assert "rulebook" in names
        assert "penalty_guidelines" in names

        rulebook = next(item for item in data if item["name"] == "rulebook")
        assert "document_type" in rulebook
        assert "node_count" in rulebook
        assert "total_tokens" in rulebook
        assert rulebook["total_tokens"] == 19
        # root + 1 + 1.1 + 2 = 4 nodes
        assert rulebook["node_count"] == 4

    def test_excludes_non_index_files(self, client):
        resp = client.get("/api/indexes")
        data = resp.json()
        names = {item["name"] for item in data}
        assert "overlay_manifest" not in names
        assert "card_name_index" not in names


class TestGetTree:
    def test_returns_tree_without_content(self, client):
        resp = client.get("/api/indexes/rulebook/tree")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "root"
        assert "children" in data
        assert "content" not in data

    def test_tree_has_metadata(self, client):
        resp = client.get("/api/indexes/rulebook/tree")
        data = resp.json()
        child = data["children"][0]
        assert child["metadata"]["section_number"] == "1"
        assert child["metadata"]["title"] == "Basic Rules"
        assert child["token_count"] == 8

    def test_tree_preserves_hierarchy(self, client):
        resp = client.get("/api/indexes/rulebook/tree")
        data = resp.json()
        section1 = data["children"][0]
        assert len(section1["children"]) == 1
        assert section1["children"][0]["id"] == "1.1"

    def test_404_for_nonexistent_index(self, client):
        resp = client.get("/api/indexes/nonexistent/tree")
        assert resp.status_code == 404

    def test_404_for_excluded_files(self, client):
        resp = client.get("/api/indexes/overlay_manifest/tree")
        assert resp.status_code == 404


class TestGetNode:
    def test_returns_node_with_content(self, client):
        resp = client.get("/api/indexes/rulebook/node/1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "1"
        assert "content" in data
        assert "Section 1 content" in data["content"]
        assert data["metadata"]["title"] == "Basic Rules"

    def test_returns_nested_node(self, client):
        resp = client.get("/api/indexes/rulebook/node/1.1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "1.1"
        assert "energy cards" in data["content"]

    def test_returns_children_summary(self, client):
        resp = client.get("/api/indexes/rulebook/node/1")
        data = resp.json()
        assert "children" in data
        assert len(data["children"]) == 1
        assert data["children"][0]["id"] == "1.1"

    def test_404_for_nonexistent_node(self, client):
        resp = client.get("/api/indexes/rulebook/node/nonexistent")
        assert resp.status_code == 404

    def test_404_for_nonexistent_index(self, client):
        resp = client.get("/api/indexes/nonexistent/node/1")
        assert resp.status_code == 404

"""PageIndex indexer for PokéProf Notebook.

Builds tree-structured indexes from intermediate markdown documents.
Each document is parsed into a hierarchy of TreeNodes preserving the
heading/section structure.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import tiktoken

from pokeprof_notebook.types import DocumentIndex, DocumentType, NodeMetadata, TreeNode

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
_SECTION_NUM_RE = re.compile(
    r"^(\d{1,3}(?:\.\d+)*(?:\.[a-z](?:\.\d+)*)?)[.\s]\s*(.*)"
)

_ENC = tiktoken.encoding_for_model("gpt-4o-mini")


def file_hash(path: Path) -> str:
    """Compute SHA-256 hash of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    return len(_ENC.encode(text))


def index_document(
    markdown_path: str | Path,
    document_name: str,
    document_type: DocumentType,
) -> DocumentIndex:
    """Build a PageIndex tree from an intermediate markdown file.

    Parses markdown headings into a tree of TreeNodes. Heading levels
    determine parent-child relationships: an h3 becomes a child of the
    preceding h2.
    """
    md = Path(markdown_path).read_text(encoding="utf-8")
    lines = md.split("\n")

    root_meta = NodeMetadata(document_type=document_type, title=document_name)
    root = TreeNode(id="root", content="", metadata=root_meta)

    # Stack of (level, node) for building the tree
    stack: list[tuple[int, TreeNode]] = [(0, root)]
    current_node = root
    content_parts: list[str] = []
    seen_ids: set[str] = set()

    def _unique_id(base: str) -> str:
        """Generate a unique ID, appending a counter suffix if needed."""
        if base not in seen_ids:
            seen_ids.add(base)
            return base
        counter = 1
        while f"{base}_{counter}" in seen_ids:
            counter += 1
        result = f"{base}_{counter}"
        seen_ids.add(result)
        return result

    def _flush_content():
        nonlocal content_parts
        if content_parts and current_node:
            current_node.content = "\n".join(content_parts).strip()
            current_node.token_count = _count_tokens(current_node.content)
        content_parts = []

    for line in lines:
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            _flush_content()
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()

            # Extract section number from title
            section_match = _SECTION_NUM_RE.match(title)
            if section_match:
                section_num = section_match.group(1)
                section_title = section_match.group(2).strip()
            else:
                section_num = ""
                section_title = title

            base_id = section_num or title.lower().replace(" ", "_")[:40]
            node_id = _unique_id(base_id)
            meta = NodeMetadata(
                document_type=document_type,
                section_number=section_num,
                title=section_title or title,
            )
            new_node = TreeNode(id=node_id, content="", metadata=meta)

            # Find parent: pop stack until we find a node with lower level
            while len(stack) > 1 and stack[-1][0] >= level:
                stack.pop()

            parent = stack[-1][1]
            parent.children.append(new_node)
            stack.append((level, new_node))
            current_node = new_node
            content_parts = []
        else:
            # Preserve blank lines between paragraphs (but skip leading blanks)
            if line.strip():
                content_parts.append(line)
            elif content_parts:
                content_parts.append("")

    _flush_content()

    # Calculate total tokens
    total_tokens = sum(node.token_count for node in root.walk())

    return DocumentIndex(
        document_name=document_name,
        document_type=document_type,
        root=root,
        total_tokens=total_tokens,
    )


def save_tree(index: DocumentIndex, output_path: str | Path) -> None:
    """Serialize a DocumentIndex to JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def _node_to_dict(node: TreeNode) -> dict:
        return {
            "id": node.id,
            "content": node.content,
            "metadata": {
                "document_type": node.metadata.document_type.value,
                "section_number": node.metadata.section_number,
                "title": node.metadata.title,
            },
            "token_count": node.token_count,
            "children": [_node_to_dict(c) for c in node.children],
        }

    data = {
        "document_name": index.document_name,
        "document_type": index.document_type.value,
        "total_tokens": index.total_tokens,
        "source_hash": index.source_hash,
        "root": _node_to_dict(index.root),
    }

    # Atomic write: write to temp file then rename to prevent corruption
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        Path(tmp_path).replace(path)
    except BaseException:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def load_tree(input_path: str | Path) -> DocumentIndex:
    """Deserialize a DocumentIndex from JSON, reconstructing the tree.

    Raises:
        FileNotFoundError: If the index file doesn't exist.
        ValueError: If the JSON is malformed or has an invalid structure.
    """
    path = Path(input_path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Corrupt index file {path.name}: {e}") from e

    def _dict_to_node(d: dict) -> TreeNode:
        meta = NodeMetadata(
            document_type=DocumentType(d["metadata"]["document_type"]),
            section_number=d["metadata"]["section_number"],
            title=d["metadata"]["title"],
        )
        node = TreeNode(
            id=d["id"],
            content=d["content"],
            metadata=meta,
            token_count=d["token_count"],
            children=[_dict_to_node(c) for c in d.get("children", [])],
        )
        return node

    try:
        root = _dict_to_node(data["root"])
    except (KeyError, TypeError) as e:
        raise ValueError(f"Invalid index structure in {path.name}: {e}") from e

    return DocumentIndex(
        document_name=data["document_name"],
        document_type=DocumentType(data["document_type"]),
        root=root,
        total_tokens=data["total_tokens"],
        source_hash=data.get("source_hash", ""),
    )


def validate_tree(index: DocumentIndex, expected_pattern: str = "") -> list[str]:
    """Validate the tree structure, returning a list of issues found."""
    issues: list[str] = []
    seen_ids: set[str] = set()
    pattern = re.compile(expected_pattern) if expected_pattern else None

    for node in index.root.walk():
        if node.id in seen_ids:
            issues.append(f"Duplicate node ID: {node.id}")
        seen_ids.add(node.id)

        if (
            pattern
            and node.metadata.section_number
            and not pattern.match(node.metadata.section_number)
        ):
            issues.append(
                f"Section number '{node.metadata.section_number}' "
                f"doesn't match pattern '{expected_pattern}'"
            )

    return issues

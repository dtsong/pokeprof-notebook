"""FastAPI server for PokéProf Notebook.

Provides /api/query (SSE streaming), /api/health, and serves the
minimal static HTML viewer.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from anthropic import APIConnectionError, APIStatusError, AuthenticationError
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from fastapi.middleware.cors import CORSMiddleware

from pokeprof_notebook.config import get_project_root, load_config
from pokeprof_notebook.indexer import load_tree
from pokeprof_notebook.overlay import annotate_sections, load_overlay
from pokeprof_notebook.retriever import search, search_multi
from pokeprof_notebook.router import route
from pokeprof_notebook.synthesizer import synthesize_stream

load_dotenv()

logger = logging.getLogger(__name__)

_ROOT = get_project_root()
_INDEXES_DIR = _ROOT / "data" / "indexes"
_STATIC_DIR = Path(__file__).parent / "static"

_ALLOWED_MODELS = {
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5-20250929",
    "claude-opus-4-6",
}

app = FastAPI(title="PokéProf Notebook", version="0.1.0")

# CORS for dev mode (Vite on :5173 → FastAPI on :8000)
if os.environ.get("POKEPROF_DEV"):
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    index_files = list(_INDEXES_DIR.glob("*.json"))
    return {
        "status": "ok",
        "indexes_available": len(index_files),
        "index_names": [f.stem for f in index_files if f.stem != "overlay_manifest"],
    }


@app.get("/api/query")
async def query_endpoint(
    q: str = Query(..., max_length=500, description="The question to ask"),
    persona: str = Query("judge", description="Persona: judge, professor, player"),
    model: str = Query("claude-haiku-4-5-20251001", description="LLM model"),
):
    """Query endpoint with SSE streaming response."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    if model not in _ALLOWED_MODELS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid model. Allowed: {', '.join(sorted(_ALLOWED_MODELS))}",
        )

    if persona not in {"judge", "professor", "player"}:
        raise HTTPException(
            status_code=422, detail="Invalid persona. Allowed: judge, professor, player"
        )

    try:
        config = load_config()
    except Exception as e:
        logger.error("Failed to load config", exc_info=True)
        return EventSourceResponse(
            _error_stream("Server configuration error"),
            media_type="text/event-stream",
        )

    async def event_generator():
        try:
            # Route
            route_decision = await asyncio.to_thread(route, q, config, persona)
            yield {
                "event": "route",
                "data": json.dumps({
                    "documents": route_decision.documents,
                    "confidence": route_decision.confidence,
                    "reasoning": route_decision.reasoning,
                }),
            }

            # Load indexes
            indexes = {}
            for doc_name in route_decision.documents:
                index_path = _INDEXES_DIR / f"{doc_name}.json"
                if index_path.exists():
                    indexes[doc_name] = load_tree(index_path)
                else:
                    logger.warning("Index not found for routed document: %s", doc_name)

            if not indexes:
                yield {
                    "event": "error",
                    "data": "No indexes available. Run 'pokeprof ingest' first.",
                }
                return

            # Retrieve
            card_names = route_decision.card_names
            if len(indexes) > 1:
                all_sections = await asyncio.to_thread(
                    search_multi,
                    q, indexes, 10, model, True, None, card_names,
                )
            else:
                doc_name, index = next(iter(indexes.items()))
                all_sections = await asyncio.to_thread(
                    search, q, index, 5, model,
                )

            if not all_sections:
                yield {
                    "event": "error",
                    "data": "No relevant sections found. Try rephrasing your query.",
                }
                return

            # Overlay
            overlay_path = _INDEXES_DIR / "overlay_manifest.json"
            if overlay_path.exists():
                manifest = load_overlay(overlay_path)
                all_sections = annotate_sections(all_sections, manifest, q)

            # Send section metadata
            yield {
                "event": "sections",
                "data": json.dumps([
                    {
                        "section_number": s.node.metadata.section_number,
                        "title": s.node.metadata.title,
                        "score": round(s.score, 3),
                        "document_name": s.document_name,
                    }
                    for s in all_sections
                ]),
            }

            # Stream answer via thread to avoid blocking the event loop
            stream = synthesize_stream(q, all_sections, persona=persona, model=model)
            async for chunk in _async_iter_in_thread(stream):
                yield {"event": "token", "data": chunk}

            yield {"event": "done", "data": ""}

        except AuthenticationError as e:
            logger.error("Authentication failed: %s", e)
            yield {"event": "error", "data": "Authentication failed. Check API key."}
        except (APIConnectionError, APIStatusError) as e:
            logger.error("API error during query: %s", e)
            yield {"event": "error", "data": "The AI service is temporarily unavailable. Please try again."}
        except Exception:
            logger.error("Query pipeline error", exc_info=True)
            yield {"event": "error", "data": "An internal error occurred."}

    return EventSourceResponse(event_generator(), media_type="text/event-stream")


async def _async_iter_in_thread(sync_gen):
    """Run a synchronous generator in a thread, yielding items asynchronously.

    Supports cancellation: if the consumer stops iterating, the producer
    thread is signalled to stop via a threading.Event.
    """
    import threading

    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()
    _DONE = object()
    cancel = threading.Event()

    def _producer():
        try:
            for item in sync_gen:
                if cancel.is_set():
                    break
                loop.call_soon_threadsafe(queue.put_nowait, item)
        except Exception as exc:
            if not cancel.is_set():
                loop.call_soon_threadsafe(queue.put_nowait, exc)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, _DONE)

    fut = loop.run_in_executor(None, _producer)
    try:
        while True:
            item = await queue.get()
            if item is _DONE:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        cancel.set()
    await fut


async def _error_stream(message: str):
    """Generate an error SSE event."""
    yield {"event": "error", "data": message}


_NON_INDEX_FILES = {"overlay_manifest", "card_name_index"}


@app.get("/api/indexes")
async def list_indexes():
    """List available document indexes with metadata."""
    result = []
    for path in sorted(_INDEXES_DIR.glob("*.json")):
        if path.stem in _NON_INDEX_FILES:
            continue
        try:
            idx = load_tree(path)
            node_count = len(idx.root.walk())
            result.append({
                "name": idx.document_name,
                "document_type": idx.document_type.value,
                "node_count": node_count,
                "total_tokens": idx.total_tokens,
            })
        except Exception:
            logger.warning("Failed to load index %s", path.stem, exc_info=True)
    return result


@app.get("/api/indexes/{name}/tree")
async def get_index_tree(name: str):
    """Return tree structure without content for a given index."""
    path = _INDEXES_DIR / f"{name}.json"
    if not path.exists() or name in _NON_INDEX_FILES:
        raise HTTPException(status_code=404, detail=f"Index '{name}' not found")

    idx = load_tree(path)

    def strip_content(node):
        return {
            "id": node.id,
            "metadata": {
                "document_type": node.metadata.document_type.value,
                "section_number": node.metadata.section_number,
                "title": node.metadata.title,
            },
            "token_count": node.token_count,
            "children": [strip_content(c) for c in node.children],
        }

    return strip_content(idx.root)


@app.get("/api/indexes/{name}/node/{node_id:path}")
async def get_index_node(name: str, node_id: str):
    """Return a single node with full content."""
    path = _INDEXES_DIR / f"{name}.json"
    if not path.exists() or name in _NON_INDEX_FILES:
        raise HTTPException(status_code=404, detail=f"Index '{name}' not found")

    idx = load_tree(path)
    for node in idx.root.walk():
        if node.id == node_id:
            return {
                "id": node.id,
                "content": node.content,
                "metadata": {
                    "document_type": node.metadata.document_type.value,
                    "section_number": node.metadata.section_number,
                    "title": node.metadata.title,
                },
                "token_count": node.token_count,
                "children": [
                    {"id": c.id, "metadata": {"title": c.metadata.title}}
                    for c in node.children
                ],
            }

    raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found in '{name}'")


# Serve frontend
_SPA_DIR = _ROOT / "frontend" / "build"

if _SPA_DIR.exists():
    # SvelteKit SPA build — serves index.html as fallback for client-side routing
    app.mount("/", StaticFiles(directory=str(_SPA_DIR), html=True), name="spa")
else:
    # Legacy static viewer fallback
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Serve the minimal web viewer."""
        index_path = _STATIC_DIR / "index.html"
        if index_path.exists():
            return HTMLResponse(index_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>PokéProf Notebook</h1><p>Static files not found.</p>")

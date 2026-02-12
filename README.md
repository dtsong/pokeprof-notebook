# PokéProf Notebook

AI-powered **Pokemon TCG** judge companion — retrieves and synthesizes rulings from official documents using tree-indexed retrieval.

Built for judges at tournament tables, professors studying for certification, and players learning the rules.

## Quick Start

```bash
# Clone and install
git clone https://github.com/dtsong/pokeprof-notebook.git
cd pokeprof-notebook
python -m venv .venv && source .venv/bin/activate
pip install -e .

# Set your Anthropic API key
echo "ANTHROPIC_API_KEY=sk-..." > .env

# Fetch data and build indexes
pokeprof fetch-cards          # ~6 min, downloads 3,600+ cards from TCGDex
pokeprof fetch-compendium     # ~10 sec, scrapes rulings compendium
pokeprof ingest               # ~30 sec, builds all 7 indexes

# Ask a question
pokeprof query "Can I use Rare Candy on my first turn?"

# Start the web viewer
pokeprof serve
```

## How It Works

PokéProf uses **PageIndex tree-indexed retrieval** — no vector database or embeddings. Documents are parsed into hierarchical trees (headings become nodes), and an LLM navigates the tree to find relevant sections.

```
Query → Router → Retriever (tree descent) → Overlay (errata) → Synthesizer → Answer
```

1. **Router** — keyword-based routing decides which documents to search; detects card names
2. **Retriever** — LLM-guided descent through PageIndex trees to find relevant sections
3. **Overlay** — annotates results with errata corrections
4. **Synthesizer** — generates a persona-appropriate answer from retrieved sections

## CLI Commands

### `pokeprof fetch-cards`

Download standard-legal card data from the [TCGDex API](https://tcgdex.dev). Caches for 7 days.

```bash
pokeprof fetch-cards           # fetch if cache is stale
pokeprof fetch-cards --force   # force re-fetch
```

### `pokeprof fetch-compendium`

Scrape rulings from the [Pokemon Rulings Compendium](https://compendium.pokegym.net). Caches for 7 days.

```bash
pokeprof fetch-compendium
```

### `pokeprof ingest`

Parse source documents into intermediate markdown, then build PageIndex trees.

```bash
pokeprof ingest                # ingest all documents
pokeprof ingest rulebook       # ingest a specific document
pokeprof ingest --force        # re-parse and re-index everything
```

### `pokeprof query`

Ask a question. Requires `ANTHROPIC_API_KEY` (or use `--no-llm` for keyword-only search).

```bash
pokeprof query "How many Prize cards at the start of a game?"
pokeprof query "What does Charizard ex do?" --persona professor
pokeprof query "Rare Candy on first turn?" --verbose
pokeprof query "energy attachment" --no-llm --format json
```

**Options:**
- `--persona {judge|professor|player}` — answer style (default: judge)
- `--verbose` — show routing decisions and retrieved sections
- `--no-llm` — keyword search only, no API calls
- `--format {text|markdown|json}` — output format
- `--model` — override the LLM model

### `pokeprof serve`

Start the FastAPI web server with SSE streaming and a minimal web viewer.

```bash
pokeprof serve                     # http://127.0.0.1:8000
pokeprof serve --port 3000         # custom port
pokeprof serve --reload            # auto-reload for development
```

## Documents

| Document | Source | Nodes | Tokens |
|----------|--------|------:|-------:|
| Rulebook | Play! Pokemon Rules PDF | 69 | 12,194 |
| Penalty Guidelines | Play! Pokemon Penalty Guidelines PDF | 64 | 15,972 |
| Legal Card List | PokeGym Standard Legal Card List HTML | 9 | 5,761 |
| Card DB (Pokemon) | TCGDex API — 3,633 SV-era cards | 1,192 | 94,481 |
| Card DB (Trainers) | TCGDex API | 260 | 9,725 |
| Card DB (Energy) | TCGDex API | 25 | 867 |
| Rulings Compendium | compendium.pokegym.net — 1,381 rulings | 1,391 | 163,693 |

## Development

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
python -m pytest tests/ -q

# Project structure
src/pokeprof_notebook/
├── cli.py              # Click CLI entry point
├── config.py           # Config loading
├── tcgdex.py           # TCGDex API client
├── compendium.py       # Compendium HTML scraper
├── types.py            # Domain models (TreeNode, DocumentIndex, etc.)
├── indexer.py          # Markdown → PageIndex tree builder
├── retriever.py        # LLM-guided tree descent
├── router.py           # Query routing and card detection
├── synthesizer.py      # Answer generation with personas
├── overlay.py          # Errata annotation system
├── server.py           # FastAPI + SSE streaming
├── parsers/
│   ├── pdf.py          # PDF → markdown (pymupdf4llm)
│   ├── html.py         # HTML → markdown (BeautifulSoup)
│   ├── tcgdex.py       # Card JSON → 3 markdown files + name index
│   └── compendium.py   # Rulings JSON → markdown
└── static/             # Web viewer (HTML/CSS/JS)
```

### Auth (Cloud Run V1)

The web app is invite-only.

- Frontend uses Firebase Auth (Google + Email/Password) on `/invite`.
- Backend enforces an allowlist stored in Firestore (`allowlist/{email}` with `enabled=true`).
- SSE `/api/query` is authenticated via an HttpOnly session cookie created by `POST /api/session`.

Local dev shortcuts:
- Set `POKEPROF_DEV=1` and `POKEPROF_AUTH_DISABLED=1` to bypass auth for local testing.

Config:
- Backend env vars: see `.env.example`
- Frontend env vars: see `frontend/.env.example`

## Roadmap

See [Issue #1](https://github.com/dtsong/pokeprof-notebook/issues/1) for the full implementation plan.

## Deployment

- Cloud Run (us-central1): `docs/deploy/cloud-run.md`

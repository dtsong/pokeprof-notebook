# PokéProf Notebook

Document companion for **Pokémon TCG** — helps judges, organizers, and players navigate Pokémon TCG rule documents using tree-indexed retrieval.

## Status

**Scaffold** — Awaiting Pokémon TCG source documents. Project structure is in place and ready for implementation once documents are provided.

## Architecture

Uses the same PageIndex tree-indexed retrieval approach as the sibling projects (Pathfinder, Tribunal), but maintains its own implementation for flexibility as the domain-specific needs evolve.

## Configuration

- `config/domain_config.yaml` — Document definitions and domain configuration (placeholder)
- `config/prompts/` — Persona-specific system prompts (TBD)
- `data/sources/` — Source documents (to be added)
- `data/indexes/` — Generated PageIndex trees (gitignored)

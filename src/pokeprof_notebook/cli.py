"""PokéProf Notebook CLI — Pokémon TCG rules assistant.

Pipeline: parse sources → build indexes → route → retrieve → synthesize.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from pokeprof_notebook.config import get_project_root, load_config
from pokeprof_notebook.indexer import file_hash, index_document, load_tree, save_tree, validate_tree
from pokeprof_notebook.overlay import annotate_sections, load_overlay
from pokeprof_notebook.retriever import search, search_multi
from pokeprof_notebook.router import route
from pokeprof_notebook.synthesizer import synthesize
from pokeprof_notebook.types import DocumentType

load_dotenv()

_ROOT = get_project_root()
_SOURCES_DIR = _ROOT / "data" / "sources"
_INTERMEDIATE_DIR = _ROOT / "data" / "intermediate"
_INDEXES_DIR = _ROOT / "data" / "indexes"

# Map document names to (source filename, intermediate filename, DocumentType, parser_type)
# parser_type: "pdf", "html", "tcgdex", "compendium"
_DOCUMENT_SOURCES: dict[str, tuple[str, str, DocumentType, str]] = {
    "rulebook": (
        "pfl_rulebook_en.pdf",
        "rulebook.md",
        DocumentType.RULEBOOK,
        "pdf",
    ),
    "penalty_guidelines": (
        "play-pokemon-penalty-guidelines-en.pdf",
        "penalty_guidelines.md",
        DocumentType.PENALTY_GUIDELINES,
        "pdf",
    ),
    "legal_card_list": (
        "Current Standard Legal Card List \u2013 The PokeGym.html",
        "legal_card_list.md",
        DocumentType.LEGAL_CARD_LIST,
        "html",
    ),
    "card_db_pokemon": (
        "tcgdex_cards.json",
        "card_db_pokemon.md",
        DocumentType.CARD_DATABASE,
        "tcgdex",
    ),
    "card_db_trainers": (
        "tcgdex_cards.json",
        "card_db_trainers.md",
        DocumentType.CARD_DATABASE,
        "tcgdex",
    ),
    "card_db_energy": (
        "tcgdex_cards.json",
        "card_db_energy.md",
        DocumentType.CARD_DATABASE,
        "tcgdex",
    ),
    "rulings_compendium": (
        "compendium_rulings.json",
        "rulings_compendium.md",
        DocumentType.RULINGS_COMPENDIUM,
        "compendium",
    ),
}

# TCGDex card DB docs all share one source — parse once, produce three outputs
_TCGDEX_DOCS = {"card_db_pokemon", "card_db_trainers", "card_db_energy"}

console = Console()


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """PokéProf Notebook — Pokémon TCG rules assistant."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _parse_tcgdex(source_path: Path, force: bool) -> None:
    """Parse TCGDex card JSON into three markdown files + card name index."""
    from pokeprof_notebook.parsers.tcgdex import cards_to_markdown

    # Check if any output is missing or force
    outputs_exist = all(
        (_INTERMEDIATE_DIR / f"card_db_{t}.md").exists()
        for t in ("pokemon", "trainers", "energy")
    )
    index_exists = (_INDEXES_DIR / "card_name_index.json").exists()

    if not force and outputs_exist and index_exists:
        console.print("  [dim]Skipping TCGDex parse (already exists)[/dim]")
        return

    console.print("Parsing [bold]tcgdex_cards.json[/bold] → 3 card markdown files...")
    cards_to_markdown(
        source_path=source_path,
        output_dir=_INTERMEDIATE_DIR,
        index_output_path=_INDEXES_DIR / "card_name_index.json",
    )
    console.print("  [green]Parsed:[/green] card_db_pokemon.md, card_db_trainers.md, card_db_energy.md")


def _parse_compendium(source_path: Path, md_path: Path, force: bool) -> None:
    """Parse Compendium JSON into markdown."""
    from pokeprof_notebook.parsers.compendium import rulings_to_markdown

    if not force and md_path.exists():
        console.print(f"  [dim]Skipping parse (already exists):[/dim] {md_path.name}")
        return

    console.print("Parsing [bold]compendium_rulings.json[/bold]...")
    rulings_to_markdown(source_path, md_path)
    console.print(f"  [green]Parsed:[/green] {md_path.name}")


@main.command()
@click.argument("document_name", required=False)
@click.option("--force", is_flag=True, help="Re-parse and re-index even if unchanged.")
def ingest(document_name: str | None, force: bool) -> None:
    """Parse source documents and build PageIndex trees.

    If DOCUMENT_NAME is provided, ingest only that document.
    Otherwise, ingest all known documents.
    """
    docs = [document_name] if document_name else list(_DOCUMENT_SOURCES.keys())

    _INTERMEDIATE_DIR.mkdir(parents=True, exist_ok=True)
    _INDEXES_DIR.mkdir(parents=True, exist_ok=True)

    # Track whether we've already parsed the shared TCGDex source
    tcgdex_parsed = False

    for doc_name in docs:
        if doc_name not in _DOCUMENT_SOURCES:
            console.print(f"[red]Error:[/red] Unknown document '{doc_name}'.")
            console.print(f"Known documents: {', '.join(_DOCUMENT_SOURCES.keys())}")
            continue

        source_file, md_file, doc_type, parser_type = _DOCUMENT_SOURCES[doc_name]
        source_path = _SOURCES_DIR / source_file
        md_path = _INTERMEDIATE_DIR / md_file
        index_path = _INDEXES_DIR / f"{doc_name}.json"

        if not source_path.exists():
            console.print(
                f"[red]Error:[/red] Source file not found: {source_path.name}\n"
                f"  Run [bold]pokeprof fetch-cards[/bold] or [bold]pokeprof fetch-compendium[/bold] first."
            )
            continue

        # Step 1: Parse source to intermediate markdown
        if parser_type == "tcgdex":
            if not tcgdex_parsed:
                _parse_tcgdex(source_path, force)
                tcgdex_parsed = True
        elif parser_type == "compendium":
            _parse_compendium(source_path, md_path, force)
        elif force or not md_path.exists():
            console.print(f"Parsing [bold]{source_file}[/bold]...")
            if parser_type == "pdf":
                from pokeprof_notebook.parsers.pdf import parse_pdf
                parse_pdf(source_path, md_path)
            elif parser_type == "html":
                from pokeprof_notebook.parsers.html import parse_html
                parse_html(source_path, md_path)
            else:
                console.print(f"[red]Error:[/red] Unknown parser type: {parser_type}")
                continue
            console.print(f"  [green]Parsed:[/green] {md_path.name}")
        else:
            console.print(f"  [dim]Skipping parse (already exists):[/dim] {md_path.name}")

        # Step 2: Build PageIndex tree from markdown
        if not md_path.exists():
            console.print(f"  [yellow]Warning:[/yellow] Intermediate file not found: {md_path.name}")
            continue

        if not force and index_path.exists():
            try:
                existing = load_tree(index_path)
                current_hash = file_hash(md_path)
                if existing.source_hash == current_hash:
                    console.print(f"  [green]Up to date:[/green] {doc_name}")
                    continue
            except (ValueError, KeyError):
                console.print(f"  [yellow]Warning:[/yellow] Corrupt index for {doc_name}, re-indexing...")

        console.print(f"Indexing [bold]{doc_name}[/bold]...")
        idx = index_document(md_path, doc_name, doc_type)
        idx.source_hash = file_hash(md_path)
        save_tree(idx, index_path)

        issues = validate_tree(idx)
        if issues:
            console.print(f"  [yellow]Warnings:[/yellow] {len(issues)} issues")
            for issue in issues[:5]:
                console.print(f"    - {issue}")

        console.print(
            f"  [green]Done:[/green] {len(idx.root.walk())} nodes, "
            f"{idx.total_tokens} tokens → {index_path}"
        )


@main.command("fetch-cards")
@click.option("--force", is_flag=True, help="Re-fetch even if cache is fresh.")
def fetch_cards(force: bool) -> None:
    """Fetch standard-legal card data from TCGDex API."""
    from pokeprof_notebook.tcgdex import fetch_all_standard_cards

    output_path = _SOURCES_DIR / "tcgdex_cards.json"
    console.print("Fetching standard-legal cards from TCGDex API...")
    console.print("  This may take several minutes for the initial fetch.")

    try:
        result_path = fetch_all_standard_cards(output_path, force=force)
        console.print(f"  [green]Done:[/green] {result_path}")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to fetch cards: {e}")
        sys.exit(1)


@main.command("fetch-compendium")
@click.option("--force", is_flag=True, help="Re-fetch even if cache is fresh.")
def fetch_compendium(force: bool) -> None:
    """Fetch rulings from the Pokémon Rulings Compendium."""
    from pokeprof_notebook.compendium import fetch_all_rulings

    output_path = _SOURCES_DIR / "compendium_rulings.json"
    console.print("Fetching rulings from compendium.pokegym.net...")

    try:
        result_path = fetch_all_rulings(output_path, force=force)
        console.print(f"  [green]Done:[/green] {result_path}")
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to fetch rulings: {e}")
        sys.exit(1)


@main.command()
@click.argument("query_text")
@click.option(
    "--persona",
    type=click.Choice(["judge", "professor", "player"]),
    default="judge",
    help="Persona for answer synthesis.",
)
@click.option("--verbose", "-v", is_flag=True, help="Show routing and retrieval details.")
@click.option("--model", default="claude-haiku-4-5-20251001", help="Override the LLM model.")
@click.option("--no-llm", is_flag=True, help="Use keyword search only (no API calls for retrieval).")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "markdown", "json"]),
    default="text",
    help="Output format.",
)
def query(
    query_text: str,
    persona: str,
    verbose: bool,
    model: str,
    no_llm: bool,
    output_format: str,
) -> None:
    """Ask a question about Pokémon TCG rules."""
    if not os.environ.get("ANTHROPIC_API_KEY") and not no_llm:
        console.print("[red]Error:[/red] ANTHROPIC_API_KEY environment variable not set.")
        console.print("Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        console.print("Or use --no-llm for keyword-only search.")
        sys.exit(1)

    try:
        config = load_config()
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to load config: {e}")
        console.print("Make sure config/domain_config.yaml exists and is valid YAML.")
        sys.exit(1)

    # Route the query
    route_decision = route(query_text, config, persona)

    if verbose:
        console.print(
            Panel(
                f"[bold]Routing:[/bold] {route_decision.reasoning}\n"
                f"[bold]Documents:[/bold] {', '.join(route_decision.documents)}\n"
                f"[bold]Confidence:[/bold] {route_decision.confidence}",
                title="Route Decision",
            )
        )

    # Load indexes
    indexes = {}
    for doc_name in route_decision.documents:
        index_path = _INDEXES_DIR / f"{doc_name}.json"
        if not index_path.exists():
            console.print(
                f"[yellow]Warning:[/yellow] Index not found for '{doc_name}'. "
                f"Run [bold]pokeprof ingest {doc_name}[/bold] first."
            )
            continue
        indexes[doc_name] = load_tree(index_path)

    # Retrieve sections
    use_llm = not no_llm
    card_names = route_decision.card_names
    if len(indexes) > 1:
        all_sections = search_multi(
            query_text, indexes, max_sections=10, model=model, use_llm=use_llm,
            card_names=card_names,
        )
    elif indexes:
        doc_name, index = next(iter(indexes.items()))
        all_sections = search(
            query_text, index, max_sections=5, model=model, use_llm=use_llm
        )
    else:
        all_sections = []

    if not all_sections:
        if not indexes:
            available = ", ".join(_DOCUMENT_SOURCES.keys())
            console.print(
                "[yellow]No indexes found.[/yellow] Build indexes first with:\n"
                f"  [bold]pokeprof ingest[/bold]  (indexes all: {available})"
            )
        else:
            console.print(
                "[yellow]No relevant sections found.[/yellow] "
                "Try rephrasing your query or using a different persona."
            )
        sys.exit(1)

    # Annotate with overlay data if manifest exists
    overlay_path = _INDEXES_DIR / "overlay_manifest.json"
    if overlay_path.exists():
        manifest = load_overlay(overlay_path)
        all_sections = annotate_sections(all_sections, manifest, query_text)

    if verbose:
        console.print(
            Panel(
                "\n".join(
                    f"[{s.node.metadata.section_number}] {s.node.metadata.title} "
                    f"(score={s.score:.2f})"
                    + (" [errata]" if s.errata_context else "")
                    for s in all_sections
                ),
                title="Retrieved Sections",
            )
        )

    # Synthesize answer
    if no_llm:
        # Show raw retrieved sections without LLM synthesis
        for s in all_sections:
            section_num = s.node.metadata.section_number
            title = s.node.metadata.title
            console.print(f"\n[bold][{section_num}] {title}[/bold] (score={s.score:.2f})")
            console.print(s.node.content[:500])
        return

    try:
        answer = synthesize(query_text, all_sections, persona=persona, model=model)
    except Exception as e:
        console.print(f"[red]Error:[/red] Failed to generate answer: {e}")
        sys.exit(1)

    # Output
    if output_format == "json":
        result = {
            "query": query_text,
            "persona": persona,
            "answer": answer,
            "sections": [
                {
                    "section_number": s.node.metadata.section_number,
                    "title": s.node.metadata.title,
                    "score": round(s.score, 3),
                    "document_name": s.document_name,
                }
                for s in all_sections
            ],
            "routing": {
                "documents": route_decision.documents,
                "confidence": route_decision.confidence,
                "reasoning": route_decision.reasoning,
            },
        }
        click.echo(json.dumps(result, indent=2, ensure_ascii=False))
    elif output_format == "markdown":
        sections_header = ", ".join(
            f"{s.node.metadata.section_number or s.node.metadata.title}"
            for s in all_sections[:5]
        )
        click.echo(f"*Sections: {sections_header}*\n")
        click.echo(answer)
    else:
        console.print()
        console.print(Panel(answer, title=f"PokéProf ({persona.title()})"))


@main.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to.")
@click.option("--port", default=8000, type=int, help="Port to bind to.")
@click.option("--reload", "do_reload", is_flag=True, help="Enable auto-reload for development.")
def serve(host: str, port: int, do_reload: bool) -> None:
    """Start the web server with API and minimal viewer."""
    import uvicorn

    console.print(
        f"Starting PokéProf server at [bold]http://{host}:{port}/[/bold]"
    )
    uvicorn.run(
        "pokeprof_notebook.server:app",
        host=host,
        port=port,
        reload=do_reload,
    )


if __name__ == "__main__":
    main()

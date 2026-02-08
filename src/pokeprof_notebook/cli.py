"""PokéProf Notebook CLI — entry point stub."""

from __future__ import annotations

import click


@click.command()
@click.argument("query")
def main(query: str) -> None:
    """Ask PokéProf Notebook a question about Pokémon TCG rules."""
    raise NotImplementedError(
        "PokéProf Notebook CLI pending — awaiting source documents"
    )


if __name__ == "__main__":
    main()

"""TCGDex card data parser for PokéProf Notebook.

Converts tcgdex_cards.json into three intermediate markdown files
(Pokemon, Trainers, Energy) and a card name index for the router.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _format_attack_cost(attack: dict[str, Any]) -> str:
    """Format attack energy cost as a compact string."""
    cost = attack.get("cost")
    if not cost:
        return "0"
    return " ".join(cost)


def _format_attack(attack: dict[str, Any]) -> str:
    """Format a single attack as markdown."""
    name = attack.get("name", "Unknown")
    cost = _format_attack_cost(attack)
    damage = attack.get("damage")
    effect = attack.get("effect", "")

    parts = [f"**Attack — {name}** ({cost})"]
    if damage:
        parts[0] += f": {damage} damage."
    if effect:
        parts.append(effect)
    return " ".join(parts)


def _format_ability(ability: dict[str, Any]) -> str:
    """Format a single ability as markdown."""
    name = ability.get("name", "Unknown")
    atype = ability.get("type", "Ability")
    effect = ability.get("effect", "")
    return f"**{atype} — {name}:** {effect}"


def _format_pokemon_card(card: dict[str, Any]) -> str:
    """Format a Pokemon card as markdown."""
    name = card.get("name", "Unknown")
    hp = card.get("hp")
    stage = card.get("stage")
    types = card.get("types") or []
    type_str = "/".join(types) if types else "Colorless"

    lines = [f"### {name}"]
    meta_parts = []
    if hp:
        meta_parts.append(f"HP: {hp}")
    if stage:
        meta_parts.append(f"Stage: {stage}")
    meta_parts.append(f"Type: {type_str}")
    lines.append(" | ".join(meta_parts))

    evolves_from = card.get("evolvesFrom")
    if evolves_from:
        lines.append(f"Evolves from: {evolves_from}")

    # Abilities
    for ability in card.get("abilities") or []:
        lines.append(_format_ability(ability))

    # Attacks
    for attack in card.get("attacks") or []:
        lines.append(_format_attack(attack))

    # Rules (ex rule, VSTAR rule, etc.)
    for rule in card.get("rules") or []:
        lines.append(f"*Rule: {rule}*")

    # Footer info
    footer_parts = []
    weaknesses = card.get("weaknesses") or []
    for w in weaknesses:
        footer_parts.append(f"Weakness: {w.get('type', '?')}")
    resistances = card.get("resistances") or []
    for r in resistances:
        footer_parts.append(f"Resistance: {r.get('type', '?')}")
    retreat = card.get("retreat")
    if retreat is not None:
        footer_parts.append(f"Retreat: {retreat}")

    set_data = card.get("set", {})
    set_name = set_data.get("name", "")
    if set_name:
        footer_parts.append(f"Set: {set_name}")
    reg_mark = card.get("regulationMark")
    if reg_mark:
        footer_parts.append(f"Reg: {reg_mark}")

    if footer_parts:
        lines.append(" | ".join(footer_parts))

    return "\n".join(lines)


def _format_trainer_card(card: dict[str, Any]) -> str:
    """Format a Trainer card as markdown."""
    name = card.get("name", "Unknown")
    effect = card.get("effect", "")

    lines = [f"### {name}"]
    if effect:
        lines.append(effect)

    for rule in card.get("rules") or []:
        lines.append(f"*Rule: {rule}*")

    set_data = card.get("set", {})
    set_name = set_data.get("name", "")
    if set_name:
        lines.append(f"Set: {set_name}")

    return "\n".join(lines)


def _format_energy_card(card: dict[str, Any]) -> str:
    """Format an Energy card as markdown."""
    name = card.get("name", "Unknown")
    effect = card.get("effect", "")

    lines = [f"### {name}"]
    if effect:
        lines.append(effect)

    for rule in card.get("rules") or []:
        lines.append(f"*Rule: {rule}*")

    set_data = card.get("set", {})
    set_name = set_data.get("name", "")
    if set_name:
        lines.append(f"Set: {set_name}")

    return "\n".join(lines)


def _get_trainer_subtype(card: dict[str, Any]) -> str:
    """Determine the trainer subtype for grouping."""
    trainer_type = card.get("trainerType")
    if trainer_type:
        return trainer_type
    # Fallback: check suffix
    suffix = card.get("suffix")
    if suffix:
        return suffix
    return "Item"


def _get_pokemon_type_group(card: dict[str, Any]) -> str:
    """Get the primary type for grouping Pokemon cards."""
    types = card.get("types")
    if types:
        return types[0]
    return "Colorless"


def cards_to_markdown(
    source_path: str | Path,
    output_dir: str | Path,
    index_output_path: str | Path,
) -> dict[str, Path]:
    """Convert tcgdex_cards.json to three markdown files + card name index.

    Args:
        source_path: Path to tcgdex_cards.json.
        output_dir: Directory for intermediate markdown files.
        index_output_path: Path for card_name_index.json.

    Returns:
        Dict mapping doc name -> output markdown path.
    """
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    index_output_path = Path(index_output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    index_output_path.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(source_path.read_text(encoding="utf-8"))
    cards = data.get("cards", [])
    logger.info("Processing %d cards from %s", len(cards), source_path.name)

    # Categorize cards
    pokemon_by_type: dict[str, list[dict]] = {}
    trainers_by_subtype: dict[str, list[dict]] = {}
    energy_cards: list[dict] = []
    card_name_index: dict[str, str] = {}

    # Deduplicate by card name (keep first printing)
    seen_names: dict[str, bool] = {}

    for card in cards:
        name = card.get("name", "")
        if not name:
            continue

        name_lower = name.lower()
        category = card.get("category", "").lower()

        if category == "pokemon":
            if name_lower not in seen_names:
                seen_names[name_lower] = True
                type_group = _get_pokemon_type_group(card)
                pokemon_by_type.setdefault(type_group, []).append(card)
                card_name_index[name_lower] = "card_db_pokemon"
        elif category == "trainer":
            if name_lower not in seen_names:
                seen_names[name_lower] = True
                subtype = _get_trainer_subtype(card)
                trainers_by_subtype.setdefault(subtype, []).append(card)
                card_name_index[name_lower] = "card_db_trainers"
        elif category == "energy":
            if name_lower not in seen_names:
                seen_names[name_lower] = True
                energy_cards.append(card)
                card_name_index[name_lower] = "card_db_energy"

    outputs: dict[str, Path] = {}

    # Pokemon markdown
    pokemon_path = output_dir / "card_db_pokemon.md"
    pokemon_lines = ["# Pokemon Card Database", ""]
    for type_name in sorted(pokemon_by_type.keys()):
        pokemon_lines.append(f"## {type_name} Type")
        pokemon_lines.append("")
        for card in sorted(pokemon_by_type[type_name], key=lambda c: c.get("name", "")):
            pokemon_lines.append(_format_pokemon_card(card))
            pokemon_lines.append("")
    pokemon_path.write_text("\n".join(pokemon_lines), encoding="utf-8")
    outputs["card_db_pokemon"] = pokemon_path
    logger.info("Wrote %s (%d unique Pokemon)", pokemon_path.name, sum(len(v) for v in pokemon_by_type.values()))

    # Trainers markdown
    trainers_path = output_dir / "card_db_trainers.md"
    trainer_lines = ["# Trainer Card Database", ""]
    for subtype in sorted(trainers_by_subtype.keys()):
        trainer_lines.append(f"## {subtype}")
        trainer_lines.append("")
        for card in sorted(trainers_by_subtype[subtype], key=lambda c: c.get("name", "")):
            trainer_lines.append(_format_trainer_card(card))
            trainer_lines.append("")
    trainers_path.write_text("\n".join(trainer_lines), encoding="utf-8")
    outputs["card_db_trainers"] = trainers_path
    logger.info("Wrote %s (%d unique Trainers)", trainers_path.name, sum(len(v) for v in trainers_by_subtype.values()))

    # Energy markdown
    energy_path = output_dir / "card_db_energy.md"
    energy_lines = ["# Energy Card Database", ""]
    energy_lines.append("## Energy Cards")
    energy_lines.append("")
    for card in sorted(energy_cards, key=lambda c: c.get("name", "")):
        energy_lines.append(_format_energy_card(card))
        energy_lines.append("")
    energy_path.write_text("\n".join(energy_lines), encoding="utf-8")
    outputs["card_db_energy"] = energy_path
    logger.info("Wrote %s (%d unique Energy cards)", energy_path.name, len(energy_cards))

    # Card name index
    index_output_path.write_text(
        json.dumps(card_name_index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Wrote card name index: %d entries", len(card_name_index))

    return outputs

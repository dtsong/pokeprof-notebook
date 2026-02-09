"""Tests for pokeprof_notebook.parsers.tcgdex — TCGDex card data parsing."""

from __future__ import annotations

import json

import pytest

from pokeprof_notebook.parsers.tcgdex import (
    _format_ability,
    _format_attack,
    _format_attack_cost,
    _format_pokemon_card,
    _format_trainer_card,
    cards_to_markdown,
)


# ── Attack cost formatting ──


class TestFormatAttackCost:
    def test_no_cost_returns_zero(self):
        assert _format_attack_cost({}) == "0"

    def test_single_cost(self):
        assert _format_attack_cost({"cost": ["Lightning"]}) == "Lightning"

    def test_multi_cost(self):
        assert _format_attack_cost({"cost": ["Lightning", "Colorless"]}) == "Lightning Colorless"


# ── Attack formatting ──


class TestFormatAttack:
    def test_full_attack_with_damage_and_effect(self):
        attack = {
            "name": "Thunderbolt",
            "cost": ["Lightning", "Lightning"],
            "damage": "120",
            "effect": "Discard all Energy from this Pokemon.",
        }
        result = _format_attack(attack)
        assert result == (
            "**Attack — Thunderbolt** (Lightning Lightning): 120 damage. "
            "Discard all Energy from this Pokemon."
        )

    def test_attack_without_damage(self):
        attack = {"name": "Tail Whip", "cost": ["Colorless"], "effect": "Flip a coin."}
        result = _format_attack(attack)
        assert result == "**Attack — Tail Whip** (Colorless) Flip a coin."

    def test_attack_with_damage_no_effect(self):
        attack = {"name": "Scratch", "cost": ["Colorless"], "damage": "20"}
        result = _format_attack(attack)
        assert result == "**Attack — Scratch** (Colorless): 20 damage."


# ── Ability formatting ──


class TestFormatAbility:
    def test_formats_ability(self):
        ability = {"name": "Volt Absorb", "type": "Ability", "effect": "Heal 30 damage."}
        result = _format_ability(ability)
        assert result == "**Ability — Volt Absorb:** Heal 30 damage."


# ── Pokemon card formatting ──


class TestFormatPokemonCard:
    def test_full_card(self):
        card = {
            "name": "Pikachu",
            "hp": 60,
            "stage": "Basic",
            "types": ["Lightning"],
            "attacks": [
                {"name": "Thunder Shock", "cost": ["Lightning"], "damage": "20", "effect": "Flip a coin."},
            ],
            "weaknesses": [{"type": "Fighting"}],
            "resistances": [{"type": "Metal"}],
            "retreat": 1,
            "set": {"name": "Scarlet & Violet"},
            "regulationMark": "G",
        }
        result = _format_pokemon_card(card)
        assert "### Pikachu" in result
        assert "HP: 60" in result
        assert "Stage: Basic" in result
        assert "Type: Lightning" in result
        assert "**Attack — Thunder Shock**" in result
        assert "Weakness: Fighting" in result
        assert "Resistance: Metal" in result
        assert "Retreat: 1" in result
        assert "Set: Scarlet & Violet" in result
        assert "Reg: G" in result

    def test_minimal_card(self):
        result = _format_pokemon_card({"name": "Ditto"})
        assert result.startswith("### Ditto")
        assert "Type: Colorless" in result

    def test_evolves_from(self):
        card = {"name": "Raichu", "evolvesFrom": "Pikachu"}
        result = _format_pokemon_card(card)
        assert "Evolves from: Pikachu" in result

    def test_rules_included(self):
        card = {"name": "Charizard ex", "rules": ["ex rule: When this Pokemon is Knocked Out..."]}
        result = _format_pokemon_card(card)
        assert "*Rule: ex rule: When this Pokemon is Knocked Out...*" in result


# ── Trainer card formatting ──


class TestFormatTrainerCard:
    def test_with_effect(self):
        card = {"name": "Professor's Research", "effect": "Draw 7 cards."}
        result = _format_trainer_card(card)
        assert "### Professor's Research" in result
        assert "Draw 7 cards." in result

    def test_with_set_name(self):
        card = {"name": "Nest Ball", "set": {"name": "Scarlet & Violet"}}
        result = _format_trainer_card(card)
        assert "Set: Scarlet & Violet" in result


# ── cards_to_markdown integration ──


class TestCardsToMarkdown:
    def _write_cards_json(self, path, cards):
        path.write_text(json.dumps({"cards": cards}), encoding="utf-8")

    def test_categorizes_pokemon_trainer_energy(self, tmp_path):
        cards = [
            {"name": "Pikachu", "category": "Pokemon", "types": ["Lightning"]},
            {"name": "Boss's Orders", "category": "Trainer", "effect": "Switch."},
            {"name": "Basic Lightning Energy", "category": "Energy"},
        ]
        source = tmp_path / "tcgdex_cards.json"
        self._write_cards_json(source, cards)
        output_dir = tmp_path / "out"
        index_path = tmp_path / "index" / "card_name_index.json"

        outputs = cards_to_markdown(source, output_dir, index_path)

        assert "card_db_pokemon" in outputs
        assert "card_db_trainers" in outputs
        assert "card_db_energy" in outputs
        assert (output_dir / "card_db_pokemon.md").exists()
        assert (output_dir / "card_db_trainers.md").exists()
        assert (output_dir / "card_db_energy.md").exists()

        pokemon_md = (output_dir / "card_db_pokemon.md").read_text(encoding="utf-8")
        assert "Pikachu" in pokemon_md

        trainers_md = (output_dir / "card_db_trainers.md").read_text(encoding="utf-8")
        assert "Boss's Orders" in trainers_md

        energy_md = (output_dir / "card_db_energy.md").read_text(encoding="utf-8")
        assert "Basic Lightning Energy" in energy_md

    def test_deduplicates_by_name(self, tmp_path):
        cards = [
            {"name": "Pikachu", "category": "Pokemon", "types": ["Lightning"], "set": {"name": "Base Set"}},
            {"name": "Pikachu", "category": "Pokemon", "types": ["Lightning"], "set": {"name": "Jungle"}},
        ]
        source = tmp_path / "tcgdex_cards.json"
        self._write_cards_json(source, cards)
        output_dir = tmp_path / "out"
        index_path = tmp_path / "card_name_index.json"

        cards_to_markdown(source, output_dir, index_path)

        pokemon_md = (output_dir / "card_db_pokemon.md").read_text(encoding="utf-8")
        assert pokemon_md.count("### Pikachu") == 1
        # First printing (Base Set) is kept
        assert "Set: Base Set" in pokemon_md
        assert "Set: Jungle" not in pokemon_md

    def test_writes_card_name_index(self, tmp_path):
        cards = [
            {"name": "Pikachu", "category": "Pokemon", "types": ["Lightning"]},
            {"name": "Boss's Orders", "category": "Trainer"},
            {"name": "Basic Fire Energy", "category": "Energy"},
        ]
        source = tmp_path / "tcgdex_cards.json"
        self._write_cards_json(source, cards)
        output_dir = tmp_path / "out"
        index_path = tmp_path / "card_name_index.json"

        cards_to_markdown(source, output_dir, index_path)

        index = json.loads(index_path.read_text(encoding="utf-8"))
        assert index["pikachu"] == "card_db_pokemon"
        assert index["boss's orders"] == "card_db_trainers"
        assert index["basic fire energy"] == "card_db_energy"

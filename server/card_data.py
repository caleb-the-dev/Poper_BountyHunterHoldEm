"""
Card data loader for Poper: Bounty Hunter Hold'em (Classic mode).
Only this module reads raw CSVs — all other systems consume CardSet.
"""

import csv
import os
from dataclasses import dataclass, field


@dataclass
class WeaponCard:
    name: str
    damage_types: list[tuple[int, str]]
    copies: int = 1


@dataclass
class ItemCard:
    name: str
    bonus_value: int
    damage_type: str
    copies: int = 1


@dataclass
class InfusionCard:
    name: str
    infusion_type: str
    copies: int = 1


@dataclass
class BountyCard:
    name: str
    vulnerability: str
    resistance: str


@dataclass
class TerrainCard:
    name: str
    adds_vulnerability: str


@dataclass
class BountyModCard:
    affected_type: str
    modifier: int   # +1 (Vulnerable to) or -1 (Deflects)
    copies: int = 1


@dataclass
class ClassCard:
    name: str
    damage_formulas: list[tuple[str, str]]  # [(formula_str, damage_type), ...]


@dataclass
class CardSet:
    weapons: list[WeaponCard] = field(default_factory=list)
    items: list[ItemCard] = field(default_factory=list)
    infusions: list[InfusionCard] = field(default_factory=list)
    bounties: list[BountyCard] = field(default_factory=list)
    terrains: list[TerrainCard] = field(default_factory=list)
    bounty_mods: list[BountyModCard] = field(default_factory=list)
    classes: list[ClassCard] = field(default_factory=list)


def _csv_path(data_dir: str, sheet: str) -> str:
    return os.path.join(data_dir, f"Bounty Hunter Holdem - {sheet}.csv")


def _read_csv(data_dir: str, sheet: str) -> list[dict]:
    path = _csv_path(data_dir, sheet)
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _parse_damage(raw: str) -> tuple[int, str]:
    """Parse '3 slashing' → (3, 'slashing')."""
    parts = raw.strip().split(" ", 1)
    return (int(parts[0]), parts[1].strip())


def _load_weapons(data_dir: str) -> list[WeaponCard]:
    cards: dict[str, WeaponCard] = {}
    for row in _read_csv(data_dir, "player_weapons"):
        name = row["weapon_name"].strip()
        damage_types = [_parse_damage(row["damage_dealt"])]
        if row["additional_damage"].strip():
            damage_types.append(_parse_damage(row["additional_damage"]))
        if name in cards:
            cards[name].copies += 1
        else:
            cards[name] = WeaponCard(name=name, damage_types=damage_types)
    return list(cards.values())


def _load_items(data_dir: str) -> list[ItemCard]:
    cards: dict[str, ItemCard] = {}
    for row in _read_csv(data_dir, "player_items"):
        name = row["item_name"].strip()
        bonus_value, damage_type = _parse_damage(row["short_desc"])
        if name in cards:
            cards[name].copies += 1
        else:
            cards[name] = ItemCard(name=name, bonus_value=bonus_value, damage_type=damage_type)
    return list(cards.values())


def _load_infusions(data_dir: str) -> list[InfusionCard]:
    cards: dict[str, InfusionCard] = {}
    for row in _read_csv(data_dir, "player_infusions"):
        name = row["name"].strip()
        infusion_type = row["short_desc"].strip()
        if name in cards:
            cards[name].copies += 1
        else:
            cards[name] = InfusionCard(name=name, infusion_type=infusion_type)
    return list(cards.values())


def _load_bounties(data_dir: str) -> list[BountyCard]:
    return [
        BountyCard(
            name=row["bounty_name"].strip(),
            vulnerability=row["vulnerable_to"].strip(),
            resistance=row["resistant_to"].strip(),
        )
        for row in _read_csv(data_dir, "bounties")
    ]


def _load_terrains(data_dir: str) -> list[TerrainCard]:
    return [
        TerrainCard(
            name=row["terrain_name"].strip(),
            adds_vulnerability=row["suffix"].strip(),
        )
        for row in _read_csv(data_dir, "terrains")
    ]


def _load_bounty_mods(data_dir: str) -> list[BountyModCard]:
    # Key is (affected_type, modifier) to de-dupe
    cards: dict[tuple[str, int], BountyModCard] = {}
    for row in _read_csv(data_dir, "bounty_mods"):
        prefix = row["prefix"].strip()
        affected_type = row["suffix"].strip()
        # Normalize "Weak to" → +1 modifier; "Deflects" → -1 modifier
        modifier = 1 if prefix == "Weak to" else -1
        key = (affected_type, modifier)
        if key in cards:
            cards[key].copies += 1
        else:
            cards[key] = BountyModCard(affected_type=affected_type, modifier=modifier)
    return list(cards.values())


def _load_classes(data_dir: str) -> list[ClassCard]:
    seen: set[str] = set()
    classes: list[ClassCard] = []

    for row in _read_csv(data_dir, "singleclasses"):
        name = row["class_name"].strip()
        if name in seen:
            continue
        seen.add(name)
        formula = row["short_desc"].strip()
        damage_type = row["type"].strip()
        classes.append(ClassCard(name=name, damage_formulas=[(formula, damage_type)]))

    for row in _read_csv(data_dir, "multiclasses"):
        name = row["class_name"].strip()
        if name in seen:
            continue
        seen.add(name)
        formulas = [
            (row["damage_1"].strip(), row["type_1"].strip()),
            (row["damage_2"].strip(), row["type_2"].strip()),
        ]
        classes.append(ClassCard(name=name, damage_formulas=formulas))

    return classes


def load_all(data_dir: str) -> CardSet:
    return CardSet(
        weapons=_load_weapons(data_dir),
        items=_load_items(data_dir),
        infusions=_load_infusions(data_dir),
        bounties=_load_bounties(data_dir),
        terrains=_load_terrains(data_dir),
        bounty_mods=_load_bounty_mods(data_dir),
        classes=_load_classes(data_dir),
    )

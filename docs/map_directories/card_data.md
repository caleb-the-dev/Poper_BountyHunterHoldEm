# Card Data
**Status:** ✅ Built | **Last updated:** 2026-04-18

## Purpose
Loads all Classic mode card definitions from CSV files and exposes them as typed dataclasses via `load_all()`. This is the foundation layer — no other system should parse raw CSVs directly.

## Source Files
| File | Role |
|---|---|
| `server/card_data.py` | Module — all CSV parsing, de-dupe logic, public API |
| `server/tests/test_card_data.py` | 22 unit tests; run with `cd server && pytest -v` |

## CSV Sources (`docs/csv_data/`)
Actual filenames: `Bounty Hunter Holdem - <sheet>.csv`

| Sheet | Card Type | Unique Cards | Total Copies | Notes |
|---|---|---|---|---|
| `player_weapons` | WeaponCard | 20 | 20 | 1–2 damage types per weapon |
| `player_items` | ItemCard | 10 | 18 | 8 items × 2 copies; Spellscroll + Spellbook × 1 each |
| `player_infusions` | InfusionCard | 7 | 21 | 7 types × 3 copies each |
| `bounties` | BountyCard | 7 | 7 | 1 vulnerability + 1 resistance each |
| `terrains` | TerrainCard | 7 | 7 | Adds 2nd vulnerability to bounty |
| `bounty_mods` | BountyModCard | 8 | 12 | 4 "Weak to" types × 2 copies; 4 "Deflects" types × 1 copy |
| `singleclasses` | ClassCard | 5 | (ignored) | Many duplicate rows — only unique names loaded |
| `multiclasses` | ClassCard | 10 | (ignored) | Many duplicate rows — only unique names loaded |

**Hunter-mode CSVs not loaded:** `feints`, `training`, `potions`, `infused_objects`, `null_runes`, `traps`, `shop`.

**De-duplication rule:** Identical card name (or name+modifier for BountyModCard) → one card entry, `copies` field tracks count.

## Dependencies
| Depends On | Why |
|---|---|
| (none) | Foundation layer — pure Python stdlib only |

## Public API

```python
load_all(data_dir: str) -> CardSet
```

`data_dir` should be the path to the directory containing the `Bounty Hunter Holdem - *.csv` files.

## Data Structures

```python
@dataclass
class WeaponCard:
    name: str
    damage_types: list[tuple[int, str]]  # e.g. [(3,"slashing")] or [(2,"slashing"),(2,"blunt")]
    copies: int

@dataclass
class ItemCard:
    name: str
    bonus_value: int
    damage_type: str
    copies: int

@dataclass
class InfusionCard:
    name: str
    infusion_type: str   # e.g. "Electric", "Fire", "Ice"
    copies: int

@dataclass
class BountyCard:
    name: str
    vulnerability: str   # infusion type
    resistance: str      # infusion type

@dataclass
class TerrainCard:
    name: str
    adds_vulnerability: str  # infusion type

@dataclass
class BountyModCard:
    affected_type: str   # physical damage type (e.g. "Piercing")
    modifier: int        # +1 = Vulnerable to, -1 = Deflects
    copies: int

@dataclass
class ClassCard:
    name: str
    damage_formulas: list[tuple[str, str]]  # [(formula, damage_type), ...]
    # Single: [("2+LV","slashing")]  Multi: [("2+LV","slashing"),("3+LV","magic")]

@dataclass
class CardSet:
    weapons: list[WeaponCard]
    items: list[ItemCard]
    infusions: list[InfusionCard]
    bounties: list[BountyCard]
    terrains: list[TerrainCard]
    bounty_mods: list[BountyModCard]
    classes: list[ClassCard]
```

## Signals / Events
None — this is a pure data layer with no async/event behavior.

## Key Patterns & Gotchas
- CSV `bounty_mods` prefix is `"Weak to"` — normalized to `modifier=+1` in the loaded object. Never stored as a string. Bible uses "Vulnerable to" language.
- Terrain `suffix` column has a trailing space in the raw CSV; `.strip()` is applied.
- Weapons: `total_damage` column is pre-computed and ignored; `damage_dealt` + `additional_damage` are parsed instead.
- Classes: `singleclasses.csv` and `multiclasses.csv` each have many duplicate rows (same 5/10 classes repeated). Only the first occurrence of each name is loaded.
- ClassCard has no `copies` field — classes are not deck cards; each player chooses one at game start.
- BountyModCard de-dupe key is `(affected_type, modifier)` — "Weak to Piercing" and "Deflects Piercing" are two distinct cards.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-18 | Built `server/card_data.py` and `server/tests/test_card_data.py`. 22 tests passing. All 8 Classic CSVs loading correctly with de-dupe and normalization. |
| 2026-04-17 | Bucket stub created. No implementation yet. |

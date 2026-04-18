# Card Data
**Status:** 🔲 Not built | **Last updated:** 2026-04-17

## Purpose
Loads all card definitions from CSV files and exposes them as typed structs/objects for use by the Deck Manager and Damage Calculator. This is the foundation layer — no other system should parse raw CSVs.

## Source Files
_None yet. Engine not chosen._

## Dependencies
| Depends On | Why |
|---|---|
| (none) | Foundation layer |

## CSV Sources (`/data/`)
| File | Card Type | Count | Notes |
|---|---|---|---|
| weapons.csv | Weapon | 20 | 3–6 base dmg, 1–2 physical types |
| items.csv | Item | 18 | +1 to +3 flat bonus per physical type |
| infusions.csv | Infusion | 21 | 3 copies × 7 types; de-dupe to 7 unique cards |
| bounties.csv | Bounty | 7 | 1 vulnerability, 1 resistance each |
| terrains.csv | Terrain | 7 | Adds 2nd vulnerability to Bounty |
| bounty_mods.csv | Bounty Mod | 12 | +1 or −1 per physical type |
| training.csv | Training | — | Placeholder — 39 identical rows; skip until Hunter mode |
| feints.csv | Feint | — | Placeholder — design not finalized; skip until Hunter mode |

**De-duplication rule:** Rows with identical card identity are copies. Load each unique card once; the row count sets how many copies go in the deck.

## Card Data Structures (design-time)
All cards share a base identity: `id`, `name`, `card_type`.

| Card Type | Key Fields |
|---|---|
| Weapon | `damage_value`, `damage_types[]` (1–2 physical types) |
| Item | `bonus_value`, `damage_type` (1 physical type) |
| Infusion | `infusion_type` (Electric/Fire/Ice/Holy/Evil/Acid/Sonic) |
| Bounty | `vulnerability` (infusion type), `resistance` (infusion type) |
| Terrain | `adds_vulnerability` (infusion type) |
| Bounty Mod | `affected_type` (physical), `modifier` (+1 or −1) |
| Class | `damage_types[]`, `formula` (e.g. `2+LV` or `3+LV` per type) |

## Signals / Events
_None yet._

## Public API
_None yet._

## Key Patterns & Gotchas
- CSV `bounty_mods` uses prefix "Weak to" — rename to "Vulnerable to" in final data to match Terrain card language.
- `training.csv` and `feints.csv` are stubs; exclude from Classic mode builds.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-17 | Bucket stub created. No implementation yet. |

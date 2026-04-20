# Damage Calculator
**Status:** ✅ Built | **Last updated:** 2026-04-18

## Purpose
Computes final damage for a player's hand at showdown. Pure logic module — no state, no side effects. Takes a `Hand` + `BoardState` and returns an `int`. Fully engine-agnostic and unit-testable in isolation.

## Source Files
| File | Role |
|---|---|
| `server/damage_calculator.py` | Module — `Hand`, `BoardState` dataclasses + `calculate_damage()` |
| `server/tests/test_damage_calculator.py` | 24 unit tests; run with `cd server && pytest -v` |

## Dependencies
| Depends On | Why |
|---|---|
| Card Data (`card_data.py`) | Imports `WeaponCard`, `ItemCard`, `InfusionCard`, `BountyCard`, `TerrainCard`, `BountyModCard`, `ClassCard` |

## Damage Formula

```
Final Damage = ceil(Base Damage × Infusion Multiplier)
```

### Step 1 — Base Damage
1. Sum all weapon damage type values
2. Add each item's `bonus_value`
3. Add each class formula evaluated at `level` (e.g. `"2+LV"` at LV 1 → 3)
4. For each active `BountyModCard`: count how many damage sources in hand have a matching `affected_type`; add `modifier × count`

### Step 2 — Infusion Multiplier
- Start at `×1.0`
- Collect `vuln_types = {bounty.vulnerability} ∪ ({terrain.adds_vulnerability} if terrain else ∅)`
- Collect `resist_types = {bounty.resistance}` unless `resistance_dropped`, in which case `∅`
- For each `InfusionCard` in hand:
  - If type in both: cancel (±0 contribution)
  - If type in `vuln_types` only: `+0.5`
  - If type in `resist_types` only: `−0.5`
- Floor at `×0.5`

**Infusion stacking:** duplicate infusion cards of the same type each apply independently (resolved design issue).

### Step 3 — Final
`ceil(base × multiplier)` — applied once at the end.

## Public API

```python
@dataclass
class Hand:
    weapon: WeaponCard
    items: list[ItemCard]        # 0–2 cards
    infusions: list[InfusionCard]  # 0–2 cards
    class_card: ClassCard
    level: int = 1

@dataclass
class BoardState:
    bounty: BountyCard
    terrain: Optional[TerrainCard] = None
    active_bounty_mods: list[BountyModCard] = field(default_factory=list)
    resistance_dropped: bool = False

def calculate_damage(hand: Hand, board: BoardState) -> int: ...

def calculate_damage_breakdown(hand: Hand, board: BoardState) -> dict: ...
# Returns: {
#   "weapon": int,         # sum of weapon damage type values
#   "class": int,          # class formula evaluated at hand.level
#   "items": list[int],    # bonus_value of each item in hand order
#   "mods_sum": int,       # net contribution from active bounty mods (can be negative)
#   "infusion_mult": float,# final multiplier after vuln/resist reconciliation
#   "total": int,          # ceil((weapon + class + sum(items) + mods_sum) * infusion_mult)
# }
# Used by the showdown overlay to render the per-player math helper.
```

## Signals / Events
None — pure function module.

## Key Patterns & Gotchas
- Bounty mod matching is **case-insensitive** (`dtype.lower() == mod.affected_type.lower()`).
- Infusion cancellation: if the same infusion type appears in both `vuln_types` and `resist_types` (possible when terrain adds a type that the bounty resists), the effects cancel to ±0 for that card. This can happen with Dragon (resist Fire) + Tundra terrain (adds Fire vulnerability).
- Multiplier floor is `×0.5` — even a fully resisted hand deals half damage.
- `ceil()` is applied **once** to the final product, not per step.
- Terrain uses `adds_vulnerability` as a **set** (deduplication) — if terrain adds the same type as the bounty's existing vulnerability, the second entry is redundant.
- Bounty mod applies per damage **source** slot: a dual-type weapon (e.g. Sword and Board) contributes two separate slots, one per type.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-18 | Built `server/damage_calculator.py` and `server/tests/test_damage_calculator.py`. 24 tests passing. Covers base damage, infusion multiplier, terrain, resistance drop, bounty mods, infusion cancellation, stacking, ceil, and multiclass formulas. |
| 2026-04-20 | Added `calculate_damage_breakdown(hand, board) -> dict` for the showdown overlay's per-player math helper. Returns weapon / class / items[] / mods_sum / infusion_mult / total. Same formula as `calculate_damage()` — matching total guaranteed by tests. |
| 2026-04-17 | Bucket stub created. No implementation yet. |

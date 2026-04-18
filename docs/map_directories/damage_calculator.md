# Damage Calculator
**Status:** 🔲 Not built | **Last updated:** 2026-04-17

## Purpose
Computes final damage for a player's hand at showdown. Pure logic module — no state, no side effects, takes a hand + board state and returns an integer. Fully engine-agnostic and unit-testable in isolation.

## Source Files
_None yet. Engine not chosen._

## Dependencies
| Depends On | Why |
|---|---|
| Card Data | Reads card type definitions for formula inputs |

## Damage Formula

```
Final Damage = ceil(Base Damage × Infusion Multiplier)
```

### Step 1 — Base Damage
1. Start with Weapon Card damage value
2. Add Class Card damage (formula: `2+LV` standard; `3+LV` for Mage and favored multiclass type; Starting LV = 1)
3. Add flat Item Card bonus values
4. For each Bounty Mod in play: if the mod's physical type matches any card in the player's hand, apply +1 or −1 per matching card

### Step 2 — Infusion Multiplier
- Start at ×1.0
- For each Infusion card in hand: +0.5 if type matches a Bounty Vulnerability; −0.5 if type matches a Bounty Resistance
- If same infusion type is both Vulnerable and Resistant (same Bounty): effects cancel, treat as ×1 contribution
- Floor: ×0.5 (multiplier can never go below 0.5)
- Open issue: Do duplicate Infusion cards of the same type each add +0.5, or is it capped at one per unique type? — see `map.md` Open Design Issues

### Step 3 — Final
Apply `ceil()` to the result of Base × Multiplier.

## Vulnerabilities & Resistances Reference
**Bounty base:** 1 vulnerability + 1 resistance (from Bounty card)
**Terrain:** adds 1 more vulnerability (from Terrain card, revealed Round 4)
**Resistance Drop:** 25% chance Bounty loses its resistance at Round 3 (rolled by Game State Machine)

## Signals / Events
_None (pure function module — no events)._

## Public API
_None yet. Expected: `calculate_damage(hand, board_state) -> int`_

## Key Patterns & Gotchas
- Must be tested headless with no UI dependency.
- Infusion multiplier floor is ×0.5, not 0 — even a fully resisted hand deals half damage.
- `ceil()` is applied once at the end, not per step.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-17 | Bucket stub created. No implementation yet. |

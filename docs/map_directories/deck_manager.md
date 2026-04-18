# Deck Manager
**Status:** 🔲 Not built | **Last updated:** 2026-04-17

## Purpose
Builds the player deck and bounty deck at the start of each hand, shuffles them, and deals cards to players. Runs server-side. Responsible for enforcing the hand structure (1 Weapon, 1 Item, 1 Infusion, 1 random Item or Infusion) and the bounty reveal sequence.

## Source Files
_None yet. Engine not chosen._

## Dependencies
| Depends On | Why |
|---|---|
| Card Data | Reads card definitions and copy counts to build decks |

## Deck Composition (Classic Mode)
**Player deck (per hand — reshuffled every hand):**
- All weapons (20), items (18), infusions (21) = 59 cards total
- Each player is dealt: 1 Weapon, 1 Item, 1 Infusion, 1 random (Item or Infusion)
- Open issue: probability of 4th card being Item vs Infusion — see Open Design Issues in `map.md`

**Bounty deck (reshuffled every 6 hands):**
- 7 Bounty cards + 7 Terrain cards + 12 Bounty Mod cards = 26 cards
- Each hand draws: 3 Bounty Mods, 1 Bounty, 1 Terrain (in reveal order)

## Reveal Order
Round 1: Bounty Mod | Round 2: Bounty | Round 3: Bounty Mod | Round 4: Terrain | Round 5: Bounty Mod

## Signals / Events
_None yet. Expected: `hand_dealt`, `card_drawn`, `decks_shuffled`_

## Public API
_None yet._

## Key Patterns & Gotchas
- All shuffle logic must run server-side (authoritative host model).
- Bounty deck reshuffles every 6 hands, not every hand — track hand count to know when to reshuffle.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-17 | Bucket stub created. No implementation yet. |

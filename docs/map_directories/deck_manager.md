# Deck Manager
**Status:** ✅ Built | **Last updated:** 2026-04-18

## Purpose
Builds and shuffles player + board decks each hand. Deals 4-card hands to N players and draws board cards (bounty, terrain, mods) per hand. Runs server-side. Pure Python, no state beyond deck positions.

## Source Files
| File | Role |
|---|---|
| `server/deck_manager.py` | Module — `PlayerHand`, `BoardDraw` dataclasses + `DeckManager` class |
| `server/tests/test_deck_manager.py` | 16 unit tests; run with `cd server && pytest -v` |

## Dependencies
| Depends On | Why |
|---|---|
| Card Data (`card_data.py`) | Imports all card types and `CardSet` to build decks |

## Deck Composition (Classic Mode)

**Player deck (rebuilt + reshuffled every `deal_hands` call):**
- Expanded from `CardSet`: all weapon copies, item copies, infusion copies
- Each player dealt: 1 Weapon (primary slot), 1 Item (primary slot), 1 Infusion (primary slot), 1 fourth card (Item or Infusion, drawn from cards remaining after primary slots)
- Fourth card type: random at `FOURTH_CARD_ITEM_PROBABILITY = 0.5` (named constant, subject to playtesting)

**Board sub-piles (persist across hands, each reshuffled independently when depleted):**
- Bounty sub-pile: expanded from `CardSet.bounties` (7 cards in Classic mode)
- Terrain sub-pile: expanded from `CardSet.terrains` (7 cards in Classic mode)
- Mod sub-pile: expanded from `CardSet.bounty_mods` (12 cards in Classic mode, copies counted)
- Each `draw_board()` call consumes: 1 bounty, 1 terrain, 3 mods

## Reveal Order
Round 1: Bounty Mod | Round 2: Bounty | Round 3: Bounty Mod | Round 4: Terrain | Round 5: Bounty Mod

The `BoardDraw` returned by `draw_board()` contains all 5 cards at once. The Game State Machine controls reveal timing.

## Public API

```python
FOURTH_CARD_ITEM_PROBABILITY = 0.5  # subject to playtesting

@dataclass
class PlayerHand:
    weapon: WeaponCard
    item: ItemCard
    infusion: InfusionCard
    fourth_card: Union[ItemCard, InfusionCard]

@dataclass
class BoardDraw:
    bounty: BountyCard
    terrain: TerrainCard
    bounty_mods: list[BountyModCard]  # always exactly 3

class DeckManager:
    def __init__(self, card_set: CardSet, rng: random.Random | None = None): ...
    def deal_hands(self, num_players: int) -> list[PlayerHand]: ...
    def draw_board(self) -> BoardDraw: ...
```

- `rng` is injectable for deterministic testing; defaults to `random.Random()`.
- `deal_hands` rebuilds the entire player deck on every call (fresh shuffle per hand).
- `draw_board` advances each sub-pile independently; each sub-pile reshuffles from `CardSet` when exhausted.

## Signals / Events
None — pure state module, no async/event behavior.

## Key Patterns & Gotchas
- Fourth card draws from cards **remaining after primary slots are filled**. With N players, items[N:] and infusions[N:] form the fourth-card pool. A card cannot appear in both a player's primary item slot and another player's fourth slot.
- `BountyCard` and `TerrainCard` have no `copies` field — `_expand()` treats missing `copies` as 1.
- Board sub-piles reshuffle independently: the mod pile (12 cards, 3 per hand) depletes after ~4 hands; bounty and terrain piles (7 cards each, 1 per hand) deplete after ~7 hands. Not synchronized.
- The "every 6 hands" note in the original stub was approximate; actual depletion depends on card set size.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-18 | Built `server/deck_manager.py` and `server/tests/test_deck_manager.py`. 16 tests passing. Covers player hand structure, fourth-card uniqueness, probability distribution, board draw structure, deck progression, and sub-pile reshuffle-on-depletion. |
| 2026-04-17 | Bucket stub created. No implementation yet. |

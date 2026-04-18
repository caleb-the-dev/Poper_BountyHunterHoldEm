# Game State Machine
**Status:** ✅ Built | **Last updated:** 2026-04-18

## Purpose
Owns the authoritative game flow: round progression (1–5), revealing board cards, rolling the Round 3 resistance drop, and driving showdown via DamageCalculator. All other systems respond to state transitions emitted by this machine.

## Source Files
| File | Role |
|---|---|
| `server/game_state_machine.py` | Module — `GamePhase`, `PlayerState`, `ShowdownResult` dataclasses + `GameStateMachine` class |
| `server/tests/test_game_state_machine.py` | 43 unit tests; run with `cd server && pytest -v` |

## Dependencies
| Depends On | Why |
|---|---|
| Deck Manager (`deck_manager.py`) | `deal_hands(n)` + `draw_board()` called at `start_hand()` |
| Damage Calculator (`damage_calculator.py`) | `calculate_damage(hand, board)` called at `resolve_showdown()` |
| Betting Engine | Not yet wired in — `advance_round()` is the explicit trigger for now |
| Lobby / Networking | Runs server-side; broadcasts state transitions to all clients |

## States
```
LOBBY → CLASS_SELECTION → ROUND_1 → ROUND_2 → ROUND_3 → ROUND_4 → ROUND_5 → SHOWDOWN → HAND_END → (ROUND_1 or GAME_END)
```

| State | What Happens |
|---|---|
| LOBBY | Players join; `add_player` / `remove_player` |
| CLASS_SELECTION | Each player gets a Class Card via `assign_class` |
| ROUND_1 | `start_hand()` deals hands + board; reveals bounty_mods[0] |
| ROUND_2 | Bounty revealed |
| ROUND_3 | Resistance drop rolled (25%); bounty_mods[1] revealed |
| ROUND_4 | Terrain revealed |
| ROUND_5 | bounty_mods[2] revealed |
| SHOWDOWN | `resolve_showdown()` calculates damage for non-folded players |
| HAND_END | Ready for next hand or game end |
| GAME_END | Not yet triggered automatically — caller decides |

## Signals / Events
Events are appended to `gsm.events: list[str]` (not cleared between hands — cumulative log).

| Event | When |
|---|---|
| `class_selection_started` | `start_class_selection()` |
| `hand_started` | `start_hand()` |
| `round_started` | Each round (ROUND_1–5), including at `start_hand()` |
| `bounty_revealed` | `advance_round()` ROUND_1 → ROUND_2 |
| `resistance_dropped` | `advance_round()` ROUND_2 → ROUND_3, when 25% roll succeeds |
| `terrain_revealed` | `advance_round()` ROUND_3 → ROUND_4 |
| `player_folded` | `fold(player_id)` |
| `showdown_started` | `advance_round()` ROUND_5 → SHOWDOWN, or when all-but-one fold |
| `hand_ended` | `resolve_showdown()` |

## Public API

```python
RESISTANCE_DROP_PROBABILITY = 0.25

@dataclass
class PlayerState:
    player_id: str
    class_card: Optional[ClassCard]  # None until assign_class called
    hand: Optional[PlayerHand]       # None until start_hand called
    folded: bool

@dataclass
class ShowdownResult:
    damages: dict        # {player_id: int} — excludes folded players
    winner_ids: list     # player_ids with max damage (list for tie support)

class GameStateMachine:
    def __init__(self, card_set: CardSet, rng: random.Random | None = None): ...

    # Properties
    phase: GamePhase
    players: list[PlayerState]
    events: list[str]
    resistance_dropped: bool
    active_mods: list[BountyModCard]    # grows each mod-reveal round
    revealed_bounty: Optional[BountyCard]
    revealed_terrain: Optional[TerrainCard]
    board_state: Optional[BoardState]   # None until bounty revealed; for DamageCalculator

    # Lobby
    def add_player(self, player_id: str) -> None: ...
    def remove_player(self, player_id: str) -> None: ...

    # Class selection
    def start_class_selection(self) -> None: ...
    def assign_class(self, player_id: str, class_card: ClassCard) -> None: ...

    # Hand flow
    def start_hand(self) -> None: ...          # CLASS_SELECTION/HAND_END → ROUND_1
    def advance_round(self) -> None: ...       # ROUND_N → ROUND_N+1 or SHOWDOWN
    def fold(self, player_id: str) -> None: ...
    def resolve_showdown(self) -> ShowdownResult: ...  # SHOWDOWN → HAND_END
```

- `rng` is injectable for deterministic testing; defaults to `random.Random()`.
- `start_hand()` rebuilds player hands (calls `DeckManager.deal_hands`) and draws a fresh board every hand.
- `advance_round()` is the caller's responsibility — the Betting Engine will call it after `betting_round_complete`.
- `fold()` during a round phase auto-transitions to SHOWDOWN if all-but-one player folds.
- `resolve_showdown()` uses the full board (bounty + terrain + all 3 mods + resistance flag) regardless of reveal state — the reveal properties control what clients see, not what damage calc uses.

## Key Patterns & Gotchas
- **Reveal vs. calculation**: `revealed_bounty` / `revealed_terrain` control what's shown to players. At showdown, `resolve_showdown()` always uses the full board (all 5 cards + resistance flag). Do not gate damage calc on reveal state.
- **Board reveal order**: R1: mods[0], R2: bounty, R3: mods[1] + resistance roll, R4: terrain, R5: mods[2]. `BoardDraw.bounty_mods` is a list of 3; index 0/1/2 maps directly to R1/R3/R5.
- **`events` list is cumulative** across hands — filter by index if you need per-hand events.
- **`board_state` property is None until Round 2** (bounty not yet revealed). Use `active_mods` directly in Round 1 if needed.
- **HAND_END → next hand**: call `start_hand()` again (re-deals, resets folded/hand state, resets resistance_dropped). Phase goes directly to ROUND_1.
- **GAME_END**: not yet triggered automatically. After `resolve_showdown()` the caller decides whether to call `start_hand()` or handle game-over externally.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-18 | Built `server/game_state_machine.py` and `server/tests/test_game_state_machine.py`. 43 tests passing. Covers initial state, player management, phase transitions, board reveals, resistance drop, folding, showdown, multi-hand resets, and events. Total server tests: 105. |
| 2026-04-17 | Bucket stub created. No implementation yet. |

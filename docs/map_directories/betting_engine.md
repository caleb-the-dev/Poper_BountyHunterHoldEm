# Betting Engine
**Status:** ✅ Built | **Last updated:** 2026-04-18

## Purpose
Manages one betting round: tracks turn order, validates actions (call, raise, check, fold, all-in), enforces the bet limit, calculates side pots for all-in scenarios. Caller (game session handler) creates one `BettingEngine` per round, processes player actions, and calls `finish()` to get the `BettingRoundResult`. Runs server-side, pure Python.

## Source Files
| File | Role |
|---|---|
| `server/betting_engine.py` | Module — `BettingPlayer`, `Pot`, `BettingRoundResult` dataclasses + `BettingEngine` class |
| `server/tests/test_betting_engine.py` | 44 unit tests; run with `cd server && pytest -v` |

## Dependencies
None — pure logic, no imports from other game modules.

## Bet Limit Rule
`max_raise = max(10, current_pot_size)` where `current_pot_size` = `pot_entering_round` + sum of all bets placed this round so far. Recalculates each time `max_raise` is read.

## Actions
| Action | Valid When | Effect |
|---|---|---|
| `check()` | `current_bet == 0` | Pass; advance turn |
| `call()` | Any | Match `current_bet`; auto all-in if insufficient chips |
| `raise_bet(amount)` | `1 ≤ amount ≤ max_raise` | Increase `current_bet` by `amount`; re-open action for all other active players |
| `fold()` | Any | Mark folded; advance turn |
| `all_in()` | Any | Commit all remaining chips; if chips > `current_bet`, acts as raise (re-opens); if chips ≤ `current_bet`, acts as partial call (no re-open) |

## Resolved Design Issues
- **Turn order** — `BettingEngine` takes players in turn-order; caller handles dealer rotation externally.
- **Under-bet all-in** — commits all chips; does NOT raise `current_bet` or re-open action; creates a side pot level.
- **Side pot + fold** — folded players are NEVER eligible for any pot. Chips they put in before folding remain in the pot and go to eligible winners.

## Side Pot Rules
Side pots are computed from distinct bet-level brackets. For each distinct `bet_this_round` amount (ascending):
- Pot at that level = sum of each player's contribution up to that level
- Eligible = non-folded players whose `bet_this_round ≥ level`
- Carried-in chips (`pot_entering_round`) are added to the first (main) pot

## Public API

```python
MAX_RAISE_FLOOR = 10

@dataclass
class BettingPlayer:
    player_id: str
    chips: int

@dataclass
class Pot:
    amount: int
    eligible_player_ids: list   # player_ids eligible to win this pot

@dataclass
class BettingRoundResult:
    pots: list                  # list[Pot] — main pot first, side pots after
    remaining_chips: dict       # player_id -> chips remaining
    folded_player_ids: list     # player_ids who folded this round

class BettingEngine:
    def __init__(self, players: list[BettingPlayer], pot_entering_round: int = 0): ...

    # State (read-only)
    current_player_id: str      # player whose turn it is
    current_bet: int            # chips all active players must match
    pot: int                    # pot_entering + sum of all bets so far
    max_raise: int              # max(MAX_RAISE_FLOOR, pot) — recalculates live
    is_round_complete: bool

    # Actions (always apply to current_player_id)
    def check(self) -> None: ...
    def call(self) -> None: ...
    def raise_bet(self, amount: int) -> None: ...
    def fold(self) -> None: ...
    def all_in(self) -> None: ...

    def finish(self) -> BettingRoundResult: ...  # only valid when is_round_complete
```

## Integration with Game State Machine
The GSM currently calls `advance_round()` explicitly. When wiring the Betting Engine in:
1. After each board card reveal, create `BettingEngine(active_players, pot_entering_round=pot)`
2. Process player actions from the relay server
3. When `is_round_complete`, call `finish()` to get `BettingRoundResult`
4. Apply folded players to GSM via `gsm.fold(pid)`
5. Call `gsm.advance_round()` to move to the next phase

## Key Patterns & Gotchas
- **Re-open after raise**: when `raise_bet()` or `all_in()` raises the bet, `round_acted` is reset to `False` for all other active (non-folded, non-all-in) players — they must act again.
- **Round complete when**: all non-folded, non-all-in players have `round_acted=True` AND `bet_this_round == current_bet`. If only one non-folded player remains OR all remaining non-folded players are all-in, round is also complete.
- **`pot` grows in real time** as bets are placed — `max_raise` therefore increases during a round as chips are committed.
- **`finish()` raises** `ValueError` if called before `is_round_complete`.
- **No player_id passed to actions** — actions always apply to `current_player_id`. The relay server validates that the correct client sent the action.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-18 | Built `server/betting_engine.py` and `server/tests/test_betting_engine.py`. 44 tests passing. Covers check/call/raise/fold/all-in, turn advancement, re-open-after-raise, side pots, partial-call all-in, carried pot, round completion. Total server tests: 167. |
| 2026-04-17 | Bucket stub created. No implementation yet. |

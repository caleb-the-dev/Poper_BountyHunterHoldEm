# Game State Machine
**Status:** 🔲 Not built | **Last updated:** 2026-04-17

## Purpose
Owns the authoritative game flow: round progression (1–5), triggering betting windows, revealing board cards, rolling the Round 3 resistance drop, and driving showdown. All other systems respond to state transitions emitted by this machine.

## Source Files
_None yet. Engine not chosen._

## Dependencies
| Depends On | Why |
|---|---|
| Deck Manager | Requests card reveals each round |
| Betting Engine | Triggers betting window per round; waits for `betting_round_complete` |
| Damage Calculator | Triggers showdown calculation |
| Lobby / Networking | Runs server-side; broadcasts state transitions to all clients |

## States
```
LOBBY → CLASS_SELECTION → HAND_START → ROUND_1 → ROUND_2 → ROUND_3 → ROUND_4 → ROUND_5 → SHOWDOWN → HAND_END → (HAND_START or GAME_END)
```

| State | What Happens |
|---|---|
| LOBBY | Players join via room code; host waits for 2–8 players |
| CLASS_SELECTION | Each player selects a Class Card |
| HAND_START | Ante collected; decks built + shuffled; hands dealt |
| ROUND_1–5 | Board card revealed; betting window opened |
| ROUND_3 | 25% resistance drop rolled and announced before betting |
| SHOWDOWN | Damage calculated for all non-folded players; pot resolved |
| HAND_END | XP/stats written to Save System; next hand or game end |
| GAME_END | One player holds all coins, or players quit |

## Signals / Events
_None yet. Expected: `round_started`, `board_card_revealed`, `resistance_dropped`, `showdown_started`, `hand_ended`, `game_ended`_

## Public API
_None yet._

## Key Patterns & Gotchas
- All state transitions run server-side; clients receive broadcast updates only.
- Round 3 resistance drop is a 25% roll — must happen before the betting window opens, and result broadcast publicly.
- If all players but one fold before showdown, skip damage calculation and award pot directly.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-17 | Bucket stub created. No implementation yet. |

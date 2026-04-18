# Betting Engine
**Status:** 🔲 Not built | **Last updated:** 2026-04-17

## Purpose
Manages one betting round: tracks turn order, validates actions (call, raise, check, fold, all-in), enforces the bet limit, calculates side pots for all-in scenarios, and resolves the pot at showdown. Runs server-side.

## Source Files
_None yet. Engine not chosen._

## Dependencies
| Depends On | Why |
|---|---|
| Game State Machine | Receives `betting_window_opened`; emits `betting_round_complete` to advance GSM |

## Bet Limit Rule
`max_bet = max(10cp, current_pot_size)`

## Actions
| Action | Effect |
|---|---|
| Call | Match the current bet |
| Raise | Increase the current bet (subject to bet limit) |
| Check | Pass with no addition to pot (only valid if no bet has been placed this round) |
| Fold | Forfeit the hand; coins already in pot are lost |
| All-In | Commit all remaining coins; may create a side pot |

## Side Pot Rules
- When a player goes all-in for less than the current bet, a side pot is created.
- Players who bet more than the all-in amount are eligible only for the main pot up to the all-in amount; excess goes to a side pot.
- Open issue: Can a folded player win a side pot they were all-in for before folding? — see `map.md` Open Design Issues.

## Open Design Issues (Betting-Specific)
- Dealer button position and clockwise turn order not yet defined.
- Under-bet all-in handling (partial call) not yet specified.

## Signals / Events
_None yet. Expected: `bet_placed`, `player_folded`, `player_all_in`, `betting_round_complete`, `side_pot_created`_

## Public API
_None yet._

## Key Patterns & Gotchas
- All pot logic runs server-side.
- The bet limit recalculates as the pot grows within a round — a raise can open up a higher max for the next raise in the same round.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-17 | Bucket stub created. No implementation yet. |

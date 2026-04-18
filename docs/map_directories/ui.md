# UI
**Status:** 🔲 Not built | **Last updated:** 2026-04-17

## Purpose
Displays game state to the local player. Functional-only for the vertical slice — no cosmetics, no animations beyond what's needed for clarity. Reads from Game State Machine broadcasts; sends player actions (bet, fold, etc.) back to the network layer.

## Source Files
_None yet. Engine not chosen._

## Dependencies
| Depends On | Why |
|---|---|
| Game State Machine | Reads state broadcasts to update display |
| Betting Engine | Renders betting actions and pot; forwards local player input to server |

## Vertical Slice UI Scope
| Element | Notes |
|---|---|
| Player hand display | Show 4 dealt cards + Class Card |
| Board display | Revealed Bounty Mods, Bounty, Terrain as they appear each round |
| Pot display | Current pot size (and side pots if applicable) |
| Coin count | Per-player coin totals |
| Round indicator | Current round (1–5) + round name |
| Betting controls | Call / Raise / Check / Fold / All-In buttons; greyed when not player's turn |
| Damage reveal | Show each player's final damage at showdown |

## Out of Scope (Backlog)
- Card animations, card backs, table skins
- Avatars, player cosmetics
- Spectator view

## Signals / Events
_None yet. Expected: `bet_action_submitted`, `fold_submitted`_

## Public API
_None yet._

## Key Patterns & Gotchas
- UI must not compute any game logic — it only renders what the server broadcasts.
- Do not test UI code (rendering, input handling) — see CLAUDE.md Testing Approach.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-17 | Bucket stub created. No implementation yet. |

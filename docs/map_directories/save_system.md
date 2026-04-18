# Save System
**Status:** 🔲 Not built | **Last updated:** 2026-04-17

## Purpose
Reads and writes the local player save file (JSON). Tracks persistent stats across sessions: XP, level, wins, hands played, lifetime coins earned. Cloud save is backlog.

## Source Files
_None yet. Engine not chosen._

## Dependencies
| Depends On | Why |
|---|---|
| Game State Machine | Listens for `hand_ended` / `game_ended` to write XP and stats |

## Save File Schema
```json
{
  "player_name": "string",
  "player_level": 1,
  "total_xp": 0,
  "total_wins": 0,
  "total_hands": 0,
  "total_coins_earned": 0,
  "cosmetics_unlocked": []
}
```

## XP Rules
- +10 XP per hand played
- +25 XP bonus per hand won

## Notes
- Build XP/level infrastructure now so progression carries forward when cosmetics are added.
- `cosmetics_unlocked` should be stored as an array of IDs even though cosmetics are backlog — schema must be forward-compatible.
- Save file location will depend on engine; use engine-provided user data directory.

## Signals / Events
_None yet. Expected: `save_written`, `save_loaded`_

## Public API
_None yet. Expected: `load_save() -> SaveData`, `write_save(data: SaveData)`_

## Key Patterns & Gotchas
- Write on hand end, not mid-hand — a crash mid-hand should not corrupt save.
- First launch: if no save file exists, initialize with defaults.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-17 | Bucket stub created. No implementation yet. |

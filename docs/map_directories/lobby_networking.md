# Lobby / Networking
**Status:** 🔲 Not built | **Last updated:** 2026-04-17

## Purpose
Handles room creation, room joining via code, player connection management, and the authoritative host model for all server-side game logic. The host runs the Game State Machine; clients receive state broadcasts and send input actions.

## Source Files
_None yet. Engine not chosen._

## Dependencies
| Depends On | Why |
|---|---|
| Game State Machine | Host runs GSM; networking layer broadcasts GSM state to clients |

## Architecture: Authoritative Host Model
- One player acts as the **host** (server).
- **All** shuffle, damage, pot logic, and state transitions run on the host only.
- Clients send actions (bet, fold, etc.) to host; host validates and broadcasts results.
- Clients never compute authoritative game state — they only render what the host broadcasts.

## Lobby Rules
- Room supports 2–8 players.
- Players join via a room code (exact format TBD — likely 4–6 alphanumeric characters).
- Host can start the game once ≥2 players have joined.
- Player disconnection handling is not yet specified (backlog concern for vertical slice).

## Signals / Events
_None yet. Expected: `player_joined`, `player_left`, `game_started`, `state_synced`_

## Public API
_None yet._

## Key Patterns & Gotchas
- Engine choice will heavily determine the networking layer (GMS2: built-in networking or Steam SDK; Godot: built-in High-Level Multiplayer API or ENet).
- Transport layer (UDP/TCP/WebSocket) is intentionally not tested — see CLAUDE.md Testing Approach.

## Recent Changes
| Date | Change |
|---|---|
| 2026-04-17 | Bucket stub created. No implementation yet. Engine TBD. |

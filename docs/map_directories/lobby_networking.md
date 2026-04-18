# Lobby / Networking
**Status:** ✅ POC Built | **Last updated:** 2026-04-18

## Purpose
Handles room creation, room joining via code, player connection management, and the authoritative relay model for all server-side game logic. The relay server brokers all messages between clients; game logic (shuffle, damage, pot resolution) will run server-side in the full build.

## Source Files
- `server/relay_server.py` — Python asyncio WebSocket relay server
- `server/room_manager.py` — room state and player tracking
- `server/config.py` — server configuration constants
- `server/requirements.txt` — Python dependencies (`websockets>=12.0`)
- `server/pytest.ini` — test runner config
- `server/tests/conftest.py` — shared test fixtures
- `server/tests/test_room_manager.py` — unit tests for room logic (11 tests)
- `server/tests/test_relay.py` — integration tests for relay server (7 tests)
- `client/project.godot` — Godot 4 project
- `client/autoload/config.gd` — `Config` autoload; holds `SERVER_URL`
- `client/autoload/ws_client.gd` — `WsClient` autoload; WebSocket client singleton
- `client/scenes/main.tscn` / `main.gd` — root scene; screen switcher
- `client/scenes/screens/name_entry.gd` — player name entry screen
- `client/scenes/screens/main_menu.gd` — create/join room UI
- `client/scenes/screens/lobby.gd` — in-room UI, chat, player list

## Dependencies
| Depends On | Why |
|---|---|
| Godot `WebSocketPeer` (built-in) | `WsClient` uses it for WebSocket transport |
| `websockets>=12.0` (Python) | relay server async WebSocket handling |
| `room_manager.py` | relay server delegates room state to this module |
| `Config` autoload | `main_menu.gd` reads `Config.SERVER_URL` |
| `WsClient` autoload | `main_menu.gd` and `lobby.gd` send/receive messages through it |

---

## Architecture

WebSocket relay model. Python asyncio server (`server/relay_server.py`) acts as the authoritative relay — all clients connect outbound to it, no port forwarding required. Uses the `websockets>=12.0` library. Matches the authoritative-host model planned for full game logic. Easy to deploy to any cloud host or expose via ngrok for local development.

---

## Signals / Events (GDScript — `client/autoload/ws_client.gd`)

| Signal | Args | When emitted |
|---|---|---|
| `connected` | — | WebSocket state transitions to STATE_OPEN for the first time |
| `disconnected` | — | WebSocket state transitions to STATE_CLOSED |
| `message_received` | `data: Dictionary` | JSON message parsed from server |

---

## Public API (GDScript — `WsClient` autoload)

| Method | Args | Effect |
|---|---|---|
| `connect_to_server` | `url: String` | Creates WebSocketPeer and initiates connection |
| `send_message` | `data: Dictionary` | JSON-encodes and sends dict to server |
| `disconnect_from_server` | — | Calls `socket.close()` to begin graceful shutdown |

---

## Server Message Protocol

**Client → Server actions:** `set_name`, `create_room`, `join_room`, `chat`, `leave_room`

**Server → Client events:** `name_set`, `room_created`, `room_joined`, `player_joined`, `player_left`, `chat`, `error`

Full protocol table is in `docs/superpowers/plans/2026-04-18-multiplayer-poc.md`.

---

## Lobby Rules
- Room supports 2–8 players.
- Players join via a 4-digit numeric room code.
- Host can start the game once ≥2 players have joined (full build; not enforced in POC).
- Player disconnection is announced to remaining players via `player_left` event.

---

## Key Patterns & Gotchas

- **Signal cleanup required:** `WsClient` is a singleton that outlives screens. `main_menu.gd` and `lobby.gd` both connect signals in `_ready` and must disconnect in `_exit_tree` using stored `Callable` vars for lambdas — otherwise duplicate handlers accumulate on screen re-entry.
- **Polling pattern:** `WsClient._process` polls `WebSocketPeer` every frame. No event-driven callbacks — the poll loop is required.
- **ngrok WSS:** For cross-machine testing, run `ngrok http 8765` and update `client/autoload/config.gd` `SERVER_URL` to use `wss://` (not `https://`).
- **`set_name` must be first:** Server ignores all actions until `set_name` is received.
- **One socket at a time:** Calling `connect_to_server` while a close is in progress leaks the old socket. Always await disconnect before reconnecting (current UX flow prevents this in practice).
- Transport layer is intentionally not tested — see CLAUDE.md Testing Approach.

---

## Recent Changes

| Date | Change |
|---|---|
| 2026-04-18 | Built multiplayer POC: Python relay server + Godot 4 client. Room create/join by 4-digit code, chat, disconnect notification. Zero port forwarding via WebSocket outbound + ngrok tunnel. |
| 2026-04-17 | Bucket stub created. No implementation yet. Engine TBD. |

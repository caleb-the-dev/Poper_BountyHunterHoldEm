# Lobby / Networking
**Status:** ✅ POC + Game Session Built | **Last updated:** 2026-04-19

## Purpose
Handles room creation, room joining via code, player connection management, and the authoritative relay model for all server-side game logic. The relay server brokers all messages between clients; game logic (shuffle, damage, pot resolution) will run server-side in the full build.

## Source Files
- `start_dev.py` — dev startup script: launches relay + ngrok, patches `config.gd` with live `wss://` URL, restores on exit. Invoke via `/start-server` skill.
- `server/relay_server.py` — Python asyncio WebSocket relay server
- `server/room_manager.py` — room state and player tracking
- `server/config.py` — server configuration constants
- `server/requirements.txt` — Python dependencies (`websockets>=12.0`)
- `server/pytest.ini` — test runner config
- `server/tests/conftest.py` — shared test fixtures
- `server/tests/test_room_manager.py` — unit tests for room logic (20 tests)
- `server/tests/test_relay.py` — integration tests for relay server (7 tests)
- `server/game_session.py` — per-room GameSession class; assembles GSM + BettingEngine, handles bet_action / disconnects / snapshots
- `server/tests/test_game_session.py` — 55+ unit tests
- `server/tests/test_relay_game_integration.py` — 9 end-to-end integration tests
- `scripts/smoke_test_game.py` — manual smoke test (plays one full hand)
- `client/project.godot` — Godot 4 project
- `client/autoload/config.gd` — `Config` autoload; holds `SERVER_URL`
- `client/autoload/ws_client.gd` — `WsClient` autoload; WebSocket client singleton
- `client/scenes/main.tscn` / `main.gd` — root scene; screen switcher
- `client/scenes/screens/name_entry.gd` — player name entry screen
- `client/scenes/screens/main_menu.gd` — create/join room UI
- `client/scenes/screens/lobby.gd` — in-room UI, chat, player list (font sizes 20–24px, 48px input height)

## Dependencies
| Depends On | Why |
|---|---|
| Godot `WebSocketPeer` (built-in) | `WsClient` uses it for WebSocket transport |
| `websockets>=12.0` (Python) | relay server async WebSocket handling |
| `room_manager.py` | relay server delegates room state to this module |
| `Config` autoload | `main_menu.gd` reads `Config.SERVER_URL` |
| `WsClient` autoload | `main_menu.gd` and `lobby.gd` send/receive messages through it |
| `game_state_machine.py` + `betting_engine.py` + `card_data.py` | `GameSession` composes these for per-room authoritative game logic |

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

**Client → Server actions:** `set_name`, `create_room`, `join_room`, `chat`, `leave_room`, `start_game`, `bet_action`

**Server → Client events:** `name_set`, `room_created`, `room_joined`, `player_joined`, `player_left`, `chat`, `error`, `game_state`, `your_hand`

Full protocol table is in `docs/superpowers/plans/2026-04-18-multiplayer-poc.md`.

---

## Game Session Protocol

### New actions
| Action | Payload | Who can send |
|---|---|---|
| `start_game` | `{}` | Host only (first client in room) |
| `bet_action` | `{type, amount?}` where type ∈ {check, call, raise, fold, all_in} | Current player only |

### New events
| Event | Payload | When |
|---|---|---|
| `game_state` | Full shared snapshot (`room_code`, `host_id`, phase, players, board, pot, turn, showdown) | After every state change |
| `your_hand` | Private: `{hand: {weapon, item, infusion, fourth_card}, class_card}` | Sent to each player right after `start_game` |

### Rules
- Starting chips: 100 per player
- Classes assigned randomly at game start (no player choice in this slice)
- Mid-game `join_room` is rejected with error
- Mid-game `leave_room` and disconnect auto-fold the player
- One hand per session; HAND_END is terminal in this slice

See `docs/superpowers/specs/2026-04-18-game-session-handler-design.md` for the full design.

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
- **`start_dev.py` handles ngrok automatically:** Run `/start-server` (or `python start_dev.py` directly) — it launches the relay, starts ngrok, polls the ngrok local API, patches `config.gd` with the live `wss://` URL, and restores it on Ctrl+C. Do not manually edit `config.gd` for testing. The `cross-machine-test` branch has a committed ngrok URL — that branch exists only for onboarding second machines; never merge that URL to main.
- **Cross-machine test confirmed (2026-04-18):** Two separate machines (different laptops) connected via ngrok tunnel. Lobby create/join, player list sync, and bidirectional chat all confirmed working across machines.
- **`set_name` must be first:** Server ignores all actions until `set_name` is received.
- **One socket at a time:** Calling `connect_to_server` while a close is in progress leaks the old socket. Always await disconnect before reconnecting (current UX flow prevents this in practice).
- **`is_valid_int()` not `is_numeric()`:** Godot 4 String has no `is_numeric()` method. Use `is_valid_int()` to validate room code input.
- **Disconnect notification latency (mitigation in place, needs live verification):** Protocol-level WebSocket ping/pong is configured on the server with `ping_interval=10, ping_timeout=10` (default was 20/20), so abrupt client death should surface as a disconnect in ~20s worst case. Godot's `WebSocketPeer` responds to pings automatically — no client code needed. An application-level heartbeat (sub-10s detection or driving UI) is still deferred.
- **Godot 4.6 project:** The `project.godot` was auto-upgraded from 4.3 to 4.6 format by the engine on first open. This is the committed version going forward.
- **`.gitignore`:** `client/.godot/`, `client/**/*.uid`, `server/__pycache__/`, and `.claude/` are excluded. Do not commit generated Godot files.
- Transport layer is intentionally not tested — see CLAUDE.md Testing Approach.

---

## Recent Changes

| Date | Change |
|---|---|
| 2026-04-18 | Built multiplayer POC: Python relay server + Godot 4 client. Room create/join by 4-digit code, chat, disconnect notification. Zero port forwarding via WebSocket outbound + ngrok tunnel. |
| 2026-04-18 | Live-tested POC on two Godot instances on same machine. All core features confirmed working: lobby creation, join by code, live player list, bidirectional chat. Fixed `is_numeric()` → `is_valid_int()` (Godot 4 API). Project auto-upgraded to Godot 4.6. Added `.gitignore`. Known issue: abrupt disconnect does not deliver `player_left` to remaining clients — deferred. |
| 2026-04-18 | Built `start_dev.py` — one-command dev startup (relay + ngrok + config.gd patch + restore on exit). `/start-server` skill added. Cross-machine test confirmed on two separate laptops via ngrok. Lobby UI scaled up: headers 24px, body/chat/input 20px, input/button min height 48px. |
| 2026-04-19 | Post-ship cleanup: `snapshot()` now exposes `room_code` + `host_id` (Godot UI will need both). Added `RoomManager.get_clients(code)` accessor, removing relay's `_rooms` reach-ins. Added `GameStateMachine.force_hand_end_walkover()`, replacing private-state pokes in `GameSession._resolve_showdown`. Fixed `BettingEngine.fold_player` to advance turn when folding the current player — otherwise mid-raise disconnects stalled the room. Tightened `ping_interval`/`ping_timeout` to 10/10 (was 20/20) for faster abrupt-disconnect detection. Added test coverage for mid-raise disconnect and the pathological "winner ineligible for side pot" fallback. 255 server tests. |
| 2026-04-18 | Wired GSM + BettingEngine into the relay server via new `server/game_session.py`. Added `start_game` and `bet_action` actions, `game_state` + `your_hand` events. Host-only game start; random class assignment; 100 starting chips; auto-fold on disconnect; mid-game joins rejected. Full-hand end-to-end playable via the protocol. 245 server tests. |
| 2026-04-17 | Bucket stub created. No implementation yet. Engine TBD. |

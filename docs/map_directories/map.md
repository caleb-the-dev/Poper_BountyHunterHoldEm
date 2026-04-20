# Poper: Bounty Hunter Hold'em — System Map
**Last updated:** 2026-04-19 | **Stage:** Pre-development (vertical slice not started; multiplayer POC confirmed on two machines)

> This file is the index of all game systems. Read it at the start of any session involving an unfamiliar system, then open only the bucket file(s) you need. Do not load bucket files speculatively.

---

## System Index

| System | Bucket File | Status | Notes |
|---|---|---|---|
| Card Data | [card_data.md](card_data.md) | ✅ Built | `server/card_data.py`; 22 tests passing; loads all 8 Classic CSVs |
| Deck Manager | [deck_manager.md](deck_manager.md) | ✅ Built | `server/deck_manager.py`; 16 tests passing; deals player hands + board draws |
| Game State Machine | [game_state_machine.md](game_state_machine.md) | ✅ Built | `server/game_state_machine.py`; 46 tests passing; phases, reveals, resistance drop, showdown, walkover helper |
| Betting Engine | [betting_engine.md](betting_engine.md) | ✅ Built | `server/betting_engine.py`; 49 tests passing; call/raise/check/fold/all-in + side pots + out-of-turn fold (advances turn when current) |
| Damage Calculator | [damage_calculator.md](damage_calculator.md) | ✅ Built | `server/damage_calculator.py`; 24 tests passing |
| Lobby / Networking | [lobby_networking.md](lobby_networking.md) | ✅ Built | Python WebSocket relay (10s ping/pong) + Godot 4 client; room code, chat, disconnect, start_game, bet_action |
| Game Session | [lobby_networking.md](lobby_networking.md) | ✅ Built | `server/game_session.py`; 59 tests passing; per-room GSM+Betting integration; snapshot exposes room_code + host_id |
| Save System | [save_system.md](save_system.md) | 🔲 Not built | Local JSON; XP, level, wins, hands, coins earned |
| UI | [ui.md](ui.md) | ✅ Built | Programmatic Godot UI; game screen + overlays; see Client UI section below |

---

## Client UI

Programmatic Godot 4.6 UI for the vertical slice. All scenes are assembled in code; `.tscn` is a thin root. Headless Godot test harness covers non-rendering logic.

- `client/scenes/game/game.gd` — top-level game screen; subscribes to `game_state` / `your_hand` and orchestrates board / seats / hud / overlays
- `client/scenes/game/game.tscn` — root Node3D scene
- `client/components/board_3d.gd` — 5-slot board (bounty / bounty_mods / terrain) with reveal animations
- `client/components/seats_3d.gd` — per-player seat placement ring around the board
- `client/components/card_3d.gd` — MeshInstance3D + SubViewport wrapper that renders a `card_face` into a 3D quad
- `client/components/card_face.gd` — uniform Control-based card front (name, stats, art region)
- `client/components/nameplate_3d.gd` — worldspace Label3D nameplate above each seat
- `client/components/hud.gd` — CanvasLayer HUD with bet buttons, pot/turn indicator, chat drawer
- `client/overlays/class_reveal.gd` — modal overlay shown at CLASS_SELECTION
- `client/overlays/showdown.gd` — full-screen overlay rendering revealed hands + damage breakdown
- `client/tests/run_all.gd` — headless Godot test entrypoint (`godot --headless --script res://tests/run_all.gd`)

---

## Dependency Graph

```
Lobby / Networking (relay_server)
  └── Room Manager
        └── Game Session   (one per room when game active)
              ├── Game State Machine
              │     ├── Deck Manager ─── Card Data
              │     └── Damage Calculator ─── Card Data
              └── Betting Engine

Save System
  └── Game State Machine (listens for hand_ended, game_ended to write XP/stats)
```

**Rule:** All shuffle, damage, and pot logic must run server-side (authoritative host). No client-side game logic.

---

## Project File Tree

```
Poper_BountyHunterHoldEm/
├── .gitignore                       — excludes client/.godot/, *.uid, __pycache__, .claude/
├── CLAUDE.md                        — build authority for Claude sessions
├── TESTING.md                       — step-by-step instructions for relay server + ngrok + Godot E2E test
├── start_dev.py                     — dev startup: relay + ngrok + config.gd patch; invoke via /start-server skill
├── docs/
│   ├── game_bible.md                — design authority (DO NOT modify without user approval)
│   ├── backlog.md                   — user-managed; do not read automatically
│   ├── superpowers/
│   │   ├── specs/2026-04-18-game-session-handler-design.md
│   │   └── plans/2026-04-18-game-session-handler.md
│   └── map_directories/
│       ├── map.md                   — this file
│       ├── card_data.md
│       ├── deck_manager.md
│       ├── game_state_machine.md
│       ├── betting_engine.md
│       ├── damage_calculator.md
│       ├── lobby_networking.md
│       ├── save_system.md
│       └── ui.md
├── data/                            — CSV card data (exists; see Card Data bucket)
│   └── (weapon, item, infusion, bounty, terrain, bounty_mod, training, feints CSVs)
├── scripts/
│   └── smoke_test_game.py           — two-client E2E smoke test (manual sanity)
├── server/                          — Python asyncio WebSocket relay server
│   ├── relay_server.py
│   ├── room_manager.py
│   ├── game_session.py
│   ├── config.py
│   ├── card_data.py
│   ├── damage_calculator.py
│   ├── deck_manager.py
│   ├── betting_engine.py
│   ├── game_state_machine.py
│   ├── requirements.txt
│   ├── pytest.ini
│   └── tests/
│       ├── conftest.py
│       ├── test_room_manager.py
│       ├── test_relay.py
│       ├── test_relay_game_integration.py
│       ├── test_game_session.py
│       ├── test_card_data.py
│       ├── test_damage_calculator.py
│       ├── test_deck_manager.py
│       ├── test_betting_engine.py
│       └── test_game_state_machine.py
└── client/                          — Godot 4 lobby client
    ├── project.godot
    ├── autoload/
    │   ├── config.gd
    │   └── ws_client.gd
    └── scenes/
        ├── main.tscn
        ├── main.gd
        └── screens/
            ├── name_entry.gd
            ├── main_menu.gd
            └── lobby.gd
```

---

## Open Design Issues

These must be resolved before or during vertical slice development. Block on them if the system being built depends on the answer.

| # | Issue | Blocks |
|---|---|---|
| 1 | **4th card probability** — 50/50 Item vs Infusion, or weighted? | Deck Manager |
| 2 | **Infusion stacking** — Duplicate Infusion cards: each +0.5, or capped at one per type? | Damage Calculator |
| 3 | ~~**Betting order**~~ — **Resolved:** `BettingEngine` takes players in turn order; caller (Game Session) handles dealer rotation externally. Under-bet all-ins commit all chips without raising `current_bet`. | Betting Engine |
| 4 | ~~**Side pot + fold**~~ — **Resolved:** folded players are never eligible for any pot. Chips put in before folding remain in the pot. | Betting Engine |

---

## Session Log

| Date | Summary |
|---|---|
| 2026-04-17 | Project initialized. Game Bible reviewed. map.md and all system bucket stubs created. Engine not yet chosen. |
| 2026-04-18 | Built multiplayer POC: Python asyncio WebSocket relay server + Godot 4 client. Players join shared lobby by 4-digit room code and exchange chat. Zero port forwarding. Automated tests: 18 passing (11 unit + 7 integration). |
| 2026-04-18 | Live tested POC — two Godot 4.6 instances on same machine via ngrok. Core loop confirmed: create room, join by code, player list, bidirectional chat all working. Fixed Godot 4 API bug (`is_valid_int`). Known issue: abrupt disconnect does not fire `player_left`. Added .gitignore. Next: startup script to launch relay + ngrok programmatically. |
| 2026-04-18 | Built `start_dev.py` + `/start-server` skill. Cross-machine test confirmed on two separate laptops via ngrok tunnel — full lobby flow working. Lobby UI scaled up (20–24px fonts, 48px inputs). Design issues #1 (4th card: 50/50) and #2 (infusion stacking: duplicates stack) resolved. Build order locked: Card Data → Damage Calculator → Deck Manager. |
| 2026-04-18 | Built `server/card_data.py` — Card Data foundation layer. Loads all 8 Classic CSVs (weapons, items, infusions, bounties, terrains, bounty_mods, singleclasses, multiclasses) as typed dataclasses with de-duplication and normalization. 22 tests passing. |
| 2026-04-18 | Built `server/damage_calculator.py` — Damage Calculator. `calculate_damage(hand, board) -> int` implements the full formula: base damage (weapon + class + items ± bounty_mods) × infusion multiplier (floor 0.5), ceil. 24 tests passing. |
| 2026-04-18 | Built `server/deck_manager.py` — Deck Manager. `deal_hands(n) -> list[PlayerHand]` and `draw_board() -> BoardDraw`. Player deck rebuilt each hand; board sub-piles (bounty/terrain/mod) persist and reshuffle independently when depleted. 16 tests passing. Total: 62 server tests. |
| 2026-04-18 | Built `server/betting_engine.py` — Betting Engine. `BettingEngine` manages one betting round: check/call/raise/fold/all-in, re-open after raise, side pot calculation, partial-call all-in. 44 tests passing. Total: 167 server tests. |
| 2026-04-18 | Built `server/game_state_machine.py` — Game State Machine. Drives the full hand lifecycle (LOBBY → CLASS_SELECTION → ROUND_1–5 → SHOWDOWN → HAND_END). Board reveals per round, 25% resistance drop at Round 3, showdown via DamageCalculator. 43 tests passing. Total: 105 server tests. |
| 2026-04-18 | Wired GSM + Betting Engine into the relay server as `server/game_session.py`. Added `start_game` + `bet_action` protocol. One-hand-at-a-time authoritative game session: random class assignment, 100 starting chips, full board reveals, showdown + pot distribution, auto-fold on disconnect, mid-game join rejection. 245 server tests passing. |
| 2026-04-19 | Post-ship cleanup pass. Spec drift fix (your_hand payload shape). Added `room_code`+`host_id` to `snapshot()`. New `RoomManager.get_clients(code)` accessor (replaces `_rooms` reach-ins). New `GameStateMachine.force_hand_end_walkover()` (replaces private-state pokes in `GameSession._resolve_showdown`). Fixed `BettingEngine.fold_player` to advance turn when folding the current player — mid-raise disconnect bug. Tightened websocket ping/pong to 10/10s. New tests: mid-raise disconnect; pathological all-winners-ineligible side pot fallback. 255 server tests. |
| 2026-04-20 | Godot UI milestone. Built programmatic Godot 4.6 game screen + overlays: `client/scenes/game/` (game.gd + game.tscn), `client/components/` (board_3d, seats_3d, card_3d, card_face, nameplate_3d, hud), `client/overlays/` (class_reveal, showdown). Added headless test harness at `client/tests/run_all.gd`. Server-side contract additions: `name_set.player_id`; `game_state.showdown.damage_breakdown` (per-player math parts); `game_state.showdown.revealed_hands` (non-folded cards). New `DamageCalculator.calculate_damage_breakdown(hand, board) -> dict`. Added Start Game button to lobby header. Next: live two-client integration test. |

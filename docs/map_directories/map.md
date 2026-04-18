# Poper: Bounty Hunter Hold'em — System Map
**Last updated:** 2026-04-18 | **Stage:** Pre-development (vertical slice not started; multiplayer POC complete)

> This file is the index of all game systems. Read it at the start of any session involving an unfamiliar system, then open only the bucket file(s) you need. Do not load bucket files speculatively.

---

## System Index

| System | Bucket File | Status | Notes |
|---|---|---|---|
| Card Data | [card_data.md](card_data.md) | 🔲 Not built | CSVs exist in `/data/`; de-dupe by unique card identity |
| Deck Manager | [deck_manager.md](deck_manager.md) | 🔲 Not built | Builds and shuffles player + bounty decks each hand |
| Game State Machine | [game_state_machine.md](game_state_machine.md) | 🔲 Not built | Rounds 1–5, betting, showdown |
| Betting Engine | [betting_engine.md](betting_engine.md) | 🔲 Not built | Call, raise, check, fold, all-in + side pot logic |
| Damage Calculator | [damage_calculator.md](damage_calculator.md) | 🔲 Not built | Base dmg → infusion multiplier → ceil |
| Lobby / Networking | [lobby_networking.md](lobby_networking.md) | ✅ Built (POC) | Python WebSocket relay + Godot 4 client; room code, chat, disconnect |
| Save System | [save_system.md](save_system.md) | 🔲 Not built | Local JSON; XP, level, wins, hands, coins earned |
| UI | [ui.md](ui.md) | 🔲 Not built | Functional only for vertical slice |

---

## Dependency Graph

```
Card Data
  └── Deck Manager
        └── Game State Machine
              ├── Betting Engine (mutual dependency: GSM drives betting rounds; Betting Engine advances GSM)
              ├── Damage Calculator
              ├── Lobby / Networking (GSM runs server-side under authoritative host)
              └── UI (reads GSM state for display)

Damage Calculator
  └── Card Data (reads card types for formula)

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
├── docs/
│   ├── game_bible.md                — design authority (DO NOT modify without user approval)
│   ├── backlog.md                   — user-managed; do not read automatically
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
├── server/                          — Python asyncio WebSocket relay server
│   ├── relay_server.py
│   ├── room_manager.py
│   ├── config.py
│   ├── requirements.txt
│   ├── pytest.ini
│   └── tests/
│       ├── conftest.py
│       ├── test_room_manager.py
│       └── test_relay.py
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
| 3 | **Betting order** — Dealer button, clockwise turn order, under-bet all-in handling | Betting Engine |
| 4 | **Side pot + fold** — Can a folded player win a side pot they were all-in for? | Betting Engine |

---

## Session Log

| Date | Summary |
|---|---|
| 2026-04-17 | Project initialized. Game Bible reviewed. map.md and all system bucket stubs created. Engine not yet chosen. |
| 2026-04-18 | Built multiplayer POC: Python asyncio WebSocket relay server + Godot 4 client. Players join shared lobby by 4-digit room code and exchange chat. Zero port forwarding. Automated tests: 18 passing (11 unit + 7 integration). |
| 2026-04-18 | Live tested POC — two Godot 4.6 instances on same machine via ngrok. Core loop confirmed: create room, join by code, player list, bidirectional chat all working. Fixed Godot 4 API bug (`is_valid_int`). Known issue: abrupt disconnect does not fire `player_left`. Added .gitignore. Next: startup script to launch relay + ngrok programmatically. |

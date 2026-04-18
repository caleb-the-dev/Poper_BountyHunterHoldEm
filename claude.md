# Poper: Bounty Hunter Hold'em — Claude Session Context

> Drop this file at the start of every session. GAME_BIBLE is the design authority; this file is the build authority.

---

## Project Identity

- **Game:** Poper: Bounty Hunter Hold'em — poker-adjacent online multiplayer card game
- **Engine:** Godot 4.6
- **Repo:** https://github.com/caleb-the-dev/Poper_BountyHunterHoldEm.git
- **Solo dev** — background in GML and SQL; comfortable in Python; light JS/GDScript
- **Design authority:** `docs/game_bible.md`
- **Backlog:** `docs/backlog.md` — do not read automatically; user manages this

---

## Current Build State

- **Stage:** Pre-development — design complete, vertical slice not started; multiplayer POC complete
- **Working:** Multiplayer POC — relay server + Godot 4.6 lobby client. Live-tested: create room, join by code, bidirectional chat all confirmed working. (See TESTING.md)
- **Known issue:** Abrupt client disconnect (window close) does not deliver `player_left` to remaining clients. Clean leave-room works. Deferred to vertical slice — needs heartbeat/ping-pong.
- **Vertical slice target:** Classic mode, fully playable online with 2–8 players
- **`start_dev.py` built** — launches relay + ngrok, patches config.gd with live wss:// URL, restores on exit. Invoke with `/start-server` skill.
- **Next task:** Cross-machine test via Tailscale (second laptop ready). Run `start_dev.py`, connect second machine to the wss:// URL, verify lobby + chat.
- **Build order after networking confirmed:** Card Data loader → Damage Calculator → Deck Manager (all server-side Python, all unit-tested before any Godot work)
- **Cross-machine testing:** Second laptop available with Tailscale already set up — can use Tailscale IP instead of ngrok for LAN-free two-machine tests

---

## Map Protocol

Read `docs/map_directories/map.md` at the start of any session involving an unfamiliar system.
`map.md` is the index of all game systems. Use it to navigate to the relevant bucket file before reading source code.
Each bucket file in `docs/map_directories/` is the authoritative description of that system: purpose, dependencies, signals/events, and public API.
Only read the bucket files you need — the goal is targeted context, not full context load.

After any significant implementation, update the relevant bucket file(s) to reflect:
- New or changed signals/events
- New or changed public methods
- New dependencies on other systems
- Structural decisions made during implementation

If a change crosses two systems, update both bucket files. If a new system is added, add it to `map.md`.

### Session Wrap-Up Skill (`/wrapup`)
A global `/wrapup` skill lives at `C:\Users\caleb\.claude\skills\wrapup\SKILL.md`. When the user invokes `/wrapup` (or says "wrap up", "close out", "done for today", etc.), this skill takes over and:
1. Commits any uncommitted work, pushes the feature branch, and merges to main
2. Reads every source file changed this session and exhaustively updates all relevant map directory files — signals/events, public API, dependencies, gotchas, recent-changes rows, and `map.md` index/session log

The skill is the authoritative end-of-session workflow. Do not do wrap-up work ad-hoc outside of it.

---

## Key Systems (Vertical Slice)

| System | Status | Notes |
|---|---|---|
| Card Data | 🔲 Not built | CSVs exist in `/data/`; de-dupe by unique card identity |
| Deck Manager | 🔲 Not built | Builds and shuffles player + bounty decks each hand |
| Game State Machine | 🔲 Not built | Rounds 1–5, betting, showdown |
| Betting Engine | 🔲 Not built | Call, raise, check, fold, all-in + side pot logic |
| Damage Calculator | 🔲 Not built | Base dmg → infusion multiplier → ceil |
| Lobby / Networking | ✅ POC Built | Python WebSocket relay + Godot 4 client; room code, chat, disconnect |
| Save System | 🔲 Not built | Local JSON; XP, level, wins, hands, coins earned |
| UI | 🔲 Not built | Functional only for vertical slice |

---

## Core Design Rules (do not deviate)

- **Classic mode only** for the vertical slice. No shop, no consumables, no class leveling.
- **Hand structure:** 4-card starting hand (1 Weapon, 1 Item, 1 Infusion, 1 random Item or Infusion) + Class Card chosen at game start.
- **5 betting rounds:** Bounty Mod → Bounty → Bounty Mod → Terrain → Bounty Mod.
- **Damage formula:** `ceil((weapon + class + items ± bounty_mods) × infusion_multiplier)`. Infusion multiplier starts at ×1, +0.5 per matching vulnerability, −0.5 per matching resistance, floor ×0.5.
- **25% resistance drop** is rolled and announced publicly at the start of Round 3.
- **Bounty gives 1 vulnerability. Terrain gives the 2nd.** (Not 2 from the Bounty.)
- **Starting LV = 1.** Class formula is `2+LV` (or `3+LV` for Mage / favored multiclass type).
- **Networking must be authoritative host model** — all shuffle, damage, and pot logic runs server-side.
- **Betting limit:** max 10cp or current pot size, whichever is greater.

---

## Code Conventions

- Comment the *why*, not the *what*
- Signals/events use past-tense names: `hand_dealt`, `bet_placed`, `bounty_revealed`
- One module/script per system
- All game logic (damage calc, deck shuffling, pot resolution) must be engine-agnostic and unit-testable in isolation

---

## Testing Approach

Write implementation + tests together. Tests must be runnable headless with no UI.

Test: damage formula, deck math, betting state transitions, pot/side-pot resolution, win/lose conditions.
Do NOT test: rendering, input handling, network transport layer.

---

## Open Design Issues

Resolve these before or during vertical slice development:

1. ~~**4th card probability**~~ — **Resolved: 50/50** (subject to playtesting). Implement as a named constant.
2. ~~**Infusion stacking**~~ — **Resolved: duplicates stack** (each copy adds +0.5). Subject to playtesting; implement as a flag constant.
3. **Betting order** — Define dealer button, clockwise turn order, and under-bet all-in handling.
4. **Side pot + fold** — Can a player who folded still win a side pot they were all-in for?

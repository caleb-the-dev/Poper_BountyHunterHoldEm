# Game Session Handler — Design

**Date:** 2026-04-18
**Status:** Approved — ready for implementation plan
**Scope:** Wire the Game State Machine and Betting Engine into the relay server as an authoritative, per-room game session. Target: **one complete hand**, end-to-end, playable via the relay protocol.

---

## Goal

The pure-Python game logic (Card Data, Damage Calculator, Deck Manager, GSM, Betting Engine) is complete — 167 server tests passing. The relay server currently only brokers lobby/chat messages. This work bridges the two: players in a room can start a game, classes get assigned, 5 betting rounds run with real chips, a showdown resolves damage, and the hand ends with winners paid out. No multi-hand game loop, no Godot UI changes.

---

## Decisions (locked during brainstorm)

| # | Decision | Choice |
|---|---|---|
| 1 | Scope | **One complete hand, end-to-end.** No multi-hand, no game-over detection. |
| 2 | Game start trigger | **Explicit host action.** The room creator sends `start_game`. |
| 3 | Class selection | **Random assignment.** Server picks a random class per player. |
| 4 | Starting chips | **100 per player.** |
| 5 | Mid-hand disconnect | **Auto-fold.** Dropped player is treated as folded. |
| 6 | Module structure | **New `server/game_session.py`.** Keeps the "one module per system" pattern. |
| 7 | Broadcast style | **Full state snapshot.** After every change, broadcast complete `game_state`; private `your_hand` sent separately. |

---

## Architecture

```
┌─────────────────────────────────────────────┐
│ relay_server.py  (transport layer)          │
│   - receives client messages                │
│   - dispatches "start_game" / "bet_action"  │
│     to the room's GameSession               │
│   - broadcasts snapshots + private hands    │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ game_session.py  (NEW — per-room game)      │
│   GameSession owns:                          │
│     • GameStateMachine                       │
│     • current BettingEngine (per round)     │
│     • chip stacks {player_id: int}          │
│     • pot carryover between rounds          │
│     • host_id                               │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│ game_state_machine.py + betting_engine.py   │
│   (pure logic, already built)               │
└─────────────────────────────────────────────┘
```

**Boundaries:**
- `game_session.py` imports GSM, BettingEngine, CardSet. **No network imports.**
- `relay_server.py` is the ONLY file that touches `websockets`. It calls `GameSession` methods and formats responses.
- `room_manager.py` gains one field per room: `game_session: GameSession | None`.

This keeps `GameSession` unit-testable with plain Python — no mock sockets, no async fixtures.

---

## Data Model

```python
# server/game_session.py

STARTING_CHIPS = 100

@dataclass
class GameSession:
    room_code: str
    host_id: str
    player_ids: list[str]              # seat order, fixed at start_game
    gsm: GameStateMachine
    chips: dict[str, int]              # {player_id: chips remaining}
    pot_carry: int = 0                 # chips carried between betting rounds
    betting: BettingEngine | None = None   # active round's engine
    last_round_pots: list = field(default_factory=list)  # from last BettingRoundResult
```

**Player identity:** The relay server currently uses the WebSocket object's `name` as an identifier. For GameSession, we adopt an internal canonical `player_id` equal to `str(id(ws))` (Python object id as string) so two players with the same display name can't collide. `name` is exposed separately in snapshots for display.

**Host identity:** `RoomManager` already keeps the room creator as the first client in its internal list (`self._rooms[code][0]`). We treat that first client as the implicit host. `GameSession.host_id` is locked at game-start time to that client's `player_id`. No new host-tracking field is needed in `RoomManager` — add a read-only helper `get_host(code) -> client | None`.

---

## Lifecycle

**1. Pre-game (lobby):** Players in room, `game_session is None`. Host sends `start_game`.

**2. Game start:**
1. Relay validates: sender is host, ≥2 players, no game in progress.
2. Calls `RoomManager.start_game(host_client)` → constructs `GameSession`.
3. `GameSession.__init__`:
   - Locks `player_ids` in current roster seat order.
   - Assigns random class to each via `gsm.assign_class()` (uses `random.choice(card_set.classes)`).
   - Calls `gsm.start_hand()` — deals hands, draws board, reveals `mods[0]`, phase → ROUND_1.
   - Creates first `BettingEngine(players=[BettingPlayer(pid, 100) for pid in player_ids])`.
4. Relay broadcasts `game_state` to all, plus private `your_hand` to each player.

**3. Betting round loop (R1–R5):**
Current player sends `bet_action`. Relay validates sender is `current_player_id`, then:

1. Call the matching `BettingEngine` method (`check`, `call`, `raise_bet(amount)`, `fold`, `all_in`).
2. If the action was `fold`, also call `gsm.fold(pid)` (lets GSM's auto-SHOWDOWN-if-all-but-one-folded trigger).
3. If `betting.is_round_complete`:
   - `result = betting.finish()`.
   - For each `pid in result.folded_player_ids`: call `gsm.fold(pid)` (idempotent).
   - Update `session.chips` from `result.remaining_chips`.
   - `pot_carry = sum(p.amount for p in result.pots)`.
   - Store `result.pots` on `session.last_round_pots`.
   - If `gsm.phase == SHOWDOWN` (all-but-one folded): resolve showdown (step 4).
   - Else: `gsm.advance_round()`. If new phase is SHOWDOWN, resolve showdown. Otherwise, spin up next `BettingEngine` with surviving non-folded, non-broke players and `pot_entering_round=pot_carry`.
   - **Fast-forward:** if the new BettingEngine has <2 active bettors (everyone remaining is all-in or broke), skip creating it and loop `gsm.advance_round()` to SHOWDOWN, carrying `pot_carry` forward.
4. Relay broadcasts `game_state`.

**4. Showdown:**
- If all-but-one player folded before showdown: synthetic result — sole survivor wins all pots unconditionally. Damage calc not invoked. `showdown.damages = {}`, `winner_ids = [sole_survivor]`.
- Otherwise: `gsm.resolve_showdown()` → `ShowdownResult(damages, winner_ids)`.
- Pot distribution: for each `Pot` in `session.last_round_pots`:
  - Find intersection of `pot.eligible_player_ids` with players tied at max damage (or use `winner_ids` directly, filtered by eligibility).
  - If ≥1 eligible winner for the pot: split amount evenly (integer division). Remainder chips go to the earliest-seated eligible winner.
  - If 0 eligible winners (pathological — all damage-winners folded for that side pot): fall back to the highest-damage eligible player in that pot. Deterministic; vanishingly rare.
- Update `session.chips` with winnings.
- Phase is now `HAND_END`.
- Relay broadcasts final `game_state` with populated `showdown` field.

**5. Post-HAND_END:** This slice stops here. `game_session` remains frozen in HAND_END until the room empties. No "next hand" action in this iteration.

---

## Protocol

### Client → Server

New actions added to the relay handler:

| Action | Payload | Who can send |
|---|---|---|
| `start_game` | `{}` | Host only |
| `bet_action` | `{type: "check"\|"call"\|"raise"\|"fold"\|"all_in", amount?: int}` | Current player only; `amount` only used for `raise` |

Existing actions (`set_name`, `create_room`, `join_room`, `chat`, `leave_room`) are unchanged. `chat` remains available during gameplay.

### Server → Client

| Event | Payload | When |
|---|---|---|
| `game_state` | Full shared snapshot (below) | After `start_game`, after every `bet_action`, after every round transition, after showdown |
| `your_hand` | `{hand: {weapon, item, infusion, fourth_card}, class_card: {...}}` — `fourth_card` is a random Item or Infusion (see Card Data) | Sent privately to each player right after `start_game` |
| `error` | `{message: str}` (existing) | On invalid action — sender only, no state change |

### `game_state` snapshot shape

```jsonc
{
  "event": "game_state",
  "phase": "round_1" | ... | "showdown" | "hand_end",
  "players": [
    {
      "player_id": "...",
      "name": "...",
      "chips": 90,
      "bet_this_round": 10,
      "folded": false,
      "all_in": false,
      "class_name": "Warrior"
    }
  ],
  "current_player_id": "p1" | null,    // null outside betting rounds
  "current_bet": 10,
  "max_raise": 20,
  "pot": 30,                            // carry + current round bets
  "board": {
    "bounty": {...} | null,             // null until revealed
    "terrain": {...} | null,
    "mods_revealed": [{...}, ...]
  },
  "resistance_dropped": false,
  "showdown": null | {
    "damages": {"p0": 15, "p1": 22},
    "winner_ids": ["p1"],
    "pot_distribution": {"p1": 30}
  }
}
```

### Validation (relay handler, before calling GameSession)

| Condition | Response |
|---|---|
| `start_game` from non-host | `error: "Only the host can start the game"` |
| `start_game` when game already running | `error: "Game already in progress"` |
| `start_game` with <2 players | `error: "Need at least 2 players to start"` |
| `bet_action` when no game running | `error: "No game in progress"` |
| `bet_action` when not your turn | `error: "Not your turn"` |
| `bet_action` with missing/invalid `type` | `error: "Invalid bet action type"` |
| `bet_action` type="raise" without `amount` | `error: "Raise requires amount"` |
| `join_room` when that room has a game in progress | `error: "Room is in-game — cannot join"` (modifies existing `join_room` handler) |
| `leave_room` while game in progress | Accepted. Auto-fold the leaving player via `on_player_disconnect`, then proceed with normal leave flow (broadcast `player_left`, remove from room). |

GameSession-level errors (raised by BettingEngine) are caught and translated:

| BettingEngine raises | Client sees |
|---|---|
| `ValueError("Cannot check when there is an outstanding bet")` | `"Cannot check — there is a bet to call"` |
| `ValueError("Raise amount X exceeds max raise Y")` | `"Raise too large — max is Y"` |
| `ValueError("Raise amount must be at least 1")` | `"Raise must be at least 1"` |
| `ValueError("Not enough chips to raise")` | `"Not enough chips for that raise"` |

Pattern: `GameSession.apply_bet_action` wraps the BettingEngine call in `try/except ValueError` and re-raises as a typed `InvalidActionError` with a client-friendly message. Relay catches, sends `error` to the offending client only.

---

## Edge Cases

| Case | Behavior |
|---|---|
| Player with 0 chips at new round start | Skipped from new `BettingEngine`. GSM still considers them "in" (they exist as a PlayerState but can't bet). Covered by fast-forward if only one bettor remains. |
| All remaining players all-in mid-round | `BettingEngine.is_round_complete` already handles this. Session finishes round and fast-forwards remaining rounds to showdown. |
| All-but-one player folds | GSM auto-transitions to SHOWDOWN. Session skips remaining rounds. Sole survivor wins all pots (synthetic showdown). |
| Disconnect of current better | `on_player_disconnect` calls `apply_bet_action(pid, "fold")`. |
| Disconnect of non-current player mid-round | Calls `gsm.fold(pid)` + new `BettingEngine.fold_player(pid)` method. |
| Host disconnects mid-game | Same as any other disconnect. Host status is unused post-start. |
| Voluntary `leave_room` mid-game | Treated identically to disconnect — auto-fold, then proceed with normal leave. |
| New player tries to `join_room` while game is running | Rejected with error. Players cannot join a game mid-hand. |
| All players disconnect | `RoomManager` already cleans up empty rooms. `GameSession` drops with the room. |
| Tied winners at showdown | Pot split by integer division; remainder chip(s) go to earliest-seated eligible winner. |
| Multiple side pots with different winners | Each pot resolved independently against its own `eligible_player_ids`. |

---

## New BettingEngine Method (additive)

The only change to existing code outside `relay_server.py` + `room_manager.py`:

```python
# server/betting_engine.py

def fold_player(self, player_id: str) -> None:
    """Fold a specific player (for disconnect handling). Unlike fold(), does not
    require it to be the player's turn. No-op if player is already folded or not
    in this engine."""
```

Reasoning: `BettingEngine.fold()` always acts on `current_player_id`. Disconnects can happen at any time, including to a player who isn't currently up. `fold_player` handles that cleanly. Three new tests:
- Out-of-turn fold marks player folded
- Out-of-turn fold does not change current turn
- Out-of-turn fold triggers round completion if only one active player remains

---

## Testing

**Programmatic, runs headless via `pytest`.** Baseline 167 → target ~210+.

### `server/tests/test_game_session.py` (~30–40 tests)

1. **Initial state & construction** — 100 chips each, classes assigned, GSM in ROUND_1, first BettingEngine exists, host_id set
2. **Start-game validation** — <2 players raises; classes assigned to every player; board drawn; private hands accessible per player
3. **Betting round flow** — apply_bet_action delegates correctly; check/call/raise/fold/all_in each update state; round completion advances GSM; chips tracked between rounds; pot_carry propagates
4. **Disconnect handling** — on_player_disconnect folds current player; folds non-current player via fold_player; fold-to-showdown awards sole-survivor all pots
5. **Edge cases** — all-but-one fold mid-round; all-remaining-players all-in fast-forwards to showdown; 0-chip player skipped from new BettingEngine; tied winners split pot; odd chip to earliest seat; side pot with separate winner
6. **Snapshot** — `snapshot(viewer_id)` returns shared state; private hand only in `your_hand`; shape matches protocol
7. **Error translation** — BettingEngine ValueErrors become typed `InvalidActionError` with client-friendly messages

All tests use an injected `random.Random(seed)` for determinism.

### `server/tests/test_relay_game_integration.py` (~5–8 tests)

1. Full-hand E2E — 2 clients, host starts, turns taken, hand resolves, final `game_state` shows winner
2. `start_game` from non-host → error
3. `bet_action` when not your turn → error
4. `bet_action` with invalid type → error
5. Disconnect mid-hand via clean `leave_room` → auto-fold

### `server/tests/test_betting_engine.py` (existing, +3 tests)

Tests for the new `fold_player` method (listed above).

### Manual smoke test: `scripts/smoke_test_game.py`

Optional sanity check the user can run after `/start-server`. Python script that:
1. Opens two WebSocket connections to the local relay
2. Sets names, creates a room with client A, joins with client B
3. Host sends `start_game`
4. Prints each `game_state` snapshot
5. Each client plays its turns automatically (simple "always check or call" strategy)
6. Prints the final showdown

No assertion — just visual inspection. Complements the programmatic integration tests.

### Not tested (per CLAUDE.md)
- Transport layer internals, WebSocket reconnection, ngrok routing
- Godot client behavior (no automated client tests)
- Rendering / UI state

### TDD discipline
Each GameSession feature goes test-first. The new `fold_player` on BettingEngine is test-first. Integration tests written last, after GameSession is green. All tests green before any commit.

---

## Out of Scope (for this slice)

- Multi-hand loop / dealer button rotation
- Game-over detection ("player has all chips")
- Godot UI for gameplay (class reveal, hand display, board reveal animation, bet buttons, showdown screen)
- Class-selection UX (picker screen — classes are random-assigned here)
- Heartbeat / reconnect protocol
- Spectator mode
- "Next hand" action
- Any changes to lobby/chat behavior

All of the above are logical follow-up slices.

---

## File Changes Summary

| File | Change |
|---|---|
| `server/game_session.py` | **New** — GameSession class, STARTING_CHIPS, InvalidActionError |
| `server/room_manager.py` | Add `game_session: GameSession \| None` per room; add `start_game(host_client)` and `get_game_session(client)` methods; track host (first client in room) |
| `server/relay_server.py` | Add `start_game` and `bet_action` action handlers; add disconnect-triggers-auto-fold logic; broadcast `game_state` + private `your_hand` |
| `server/betting_engine.py` | Add `fold_player(player_id)` method (~10 lines) |
| `server/tests/test_game_session.py` | **New** — 30–40 unit tests |
| `server/tests/test_relay_game_integration.py` | **New** — 5–8 integration tests |
| `server/tests/test_betting_engine.py` | Add 3 tests for `fold_player` |
| `scripts/smoke_test_game.py` | **New** — optional manual smoke test |
| `docs/map_directories/lobby_networking.md` | Update: new actions, new events, `game_session` reference |
| `docs/map_directories/betting_engine.md` | Update: `fold_player` method in public API |
| `docs/map_directories/map.md` | Add row for Game Session Handler; add file tree entries; session log |
| `CLAUDE.md` | Update Current Build State; update Key Systems table; update Next task |

No new bucket file needed — `game_session.py` is documented in `lobby_networking.md` since it's the server-side integration layer, not its own game system. (If the file grows significantly in a future slice, split into its own bucket.)

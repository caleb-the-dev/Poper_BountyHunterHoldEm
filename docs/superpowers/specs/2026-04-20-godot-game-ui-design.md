# Godot Game UI — Design

**Date:** 2026-04-20
**Status:** Approved — ready for implementation plan
**Scope:** The first playable Godot game UI for Poper: Bounty Hunter Hold'em. A **3D** view-layer over the server-authoritative `game_state` snapshots, with a 2D HUD overlay for controls. Target milestone: **two Godot clients play one full Classic hand end-to-end, matching `scripts/smoke_test_game.py`.**

---

## Goal

The server is fully built (255 tests passing). `GameSession` broadcasts `game_state` snapshots and private `your_hand` payloads; it accepts `bet_action` (check/call/raise/fold/all_in). Lobby + chat flow already work from two Godot clients.

This spec covers the game-in-progress UI: rendering the 3D table, cards, opponents, a HUD with betting controls, a class/hand reveal overlay, and a showdown overlay. Zero new server game logic — only two small protocol additions (below).

---

## Decisions (locked during brainstorm)

| # | Decision | Choice |
|---|---|---|
| 1 | Engine mode | **Godot 3D (Forward+).** Cards must feel real; pivoting 2D→3D later would be costly. |
| 2 | Card rendering | **MeshInstance3D QuadMesh + SubViewport** rendering a 2D Control for the face. No art assets. |
| 3 | Card face styling | **Uniform across all card types.** Type label is the only difference; class card is not visually distinguished. |
| 4 | Camera | **Fixed first-person table view.** Camera low and slightly tilted down, your seat bottom, opponents across/around the far arc. |
| 5 | Seat layout | **Local player pinned to Seat_0.** Opponents fill Seat_1..7 in `snapshot.players[]` order (deterministic). |
| 6 | Opponent display | **3D worldspace nameplates** above each seat (name, class, chips, bet, folded/all-in). No opponent card-backs — nothing public about opponents' hands. |
| 7 | HUD layout | **Classic Layout A.** Top strip (room / phase / pot / turn state) + persistent bet bar bottom-center + your-chips bottom-left + chat-toggle bottom-right. |
| 8 | Bet bar behavior | **Always visible.** Interactive on your turn; dimmed + non-interactive when waiting. Hidden entirely if you're folded or all-in. |
| 9 | Chat | **Collapsible drawer** (hidden by default). Unread dot on toggle when closed. |
| 10 | Class/hand reveal | **Combined modal overlay** — class + 4 hand cards, single "Begin Round 1" button. Triggers on first `your_hand` of a hand. |
| 11 | Showdown | **Full-screen overlay.** Ranked rows per player (cards, damage, chips), winner highlighted, subtle math helper under damage total. "Leave Game" button returns to main menu. |
| 12 | Animations | **Deferred.** Node structure supports them (`set_face_down`, `set_card` methods) but no animation work in this milestone. |

---

## Server protocol additions (minor)

Three small server changes required for the UI to be feasible without duplicating server logic:

**1. Add `player_id` to `name_set` event.**
The client currently has no way to know its own player_id — only its name. Server identifies clients by the websocket object, but the client never receives that identity.

```python
# server/relay_server.py — in the set_name handler
await _send(ws, "name_set", name=ws.name, player_id=str(id(ws)))
```

Client stores `WsClient.my_player_id` when `name_set` arrives. Used throughout to find "my" entry in `players[]` and compare `current_player_id`.

**2. Add `damage_breakdown` to showdown payload.**
The showdown overlay shows a subtle math helper (e.g. `3 + 3 + 1 + 1 + 2 → 10 × 1.5`). Computing this on the client would duplicate infusion/resistance logic. Instead, expose the breakdown from `damage_calculator.py`.

```python
# snapshot.showdown shape (added fields in bold):
{
  "damages": {player_id: 15, ...},
  "winner_ids": [player_id, ...],
  "pot_distribution": {player_id: 42, ...},
  "damage_breakdown": {                           # NEW
    player_id: {
      "weapon": 3,
      "class": 3,
      "items": [1, 1],
      "mods_sum": 2,
      "infusion_mult": 1.5,
      "total": 15,
    },
    ...
  },
}
```

Walkover case (sole survivor): `damages == {}`, `damage_breakdown == {}`. Overlay skips the damage columns entirely.

**3. Add `revealed_hands` to showdown payload.**
`snapshot.players[]` carries `class_name` but not hand cards — opponent hands are never part of the public snapshot during a live round. At showdown, non-folded players' hands must become public so the overlay can show them. Folded players' hands stay hidden.

```python
# snapshot.showdown — added field:
{
  ...
  "revealed_hands": {
    player_id: {
      "weapon":      {...},
      "item":        {...},
      "infusion":    {...},
      "fourth_card": {...},
      "class_card":  {...},
    },
    ...  # folded players omitted
  },
}
```

All three server changes are small and testable. Bundle them into the implementation plan as the first step before touching Godot.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Godot autoloads (already exist)                             │
│   WsClient    — websocket polling, signals, my_player_id    │
│   Config      — SERVER_URL                                  │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│ main.gd  (scene swap controller)                            │
│   main_menu ↔ lobby ↔ game ↔ main_menu                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ scenes/game/game.tscn  (Node3D root — game.gd)              │
│                                                             │
│   ├── Camera3D (fixed, first-person table view)             │
│   ├── DirectionalLight3D                                    │
│   ├── WorldEnvironment                                      │
│   ├── Table (MeshInstance3D, elliptical felt)               │
│   ├── Board (Node3D — board_3d.gd)                          │
│   │     ├── Slot_Mod1    (Marker3D)                         │
│   │     ├── Slot_Bounty  (Marker3D)                         │
│   │     ├── Slot_Mod2    (Marker3D)                         │
│   │     ├── Slot_Terrain (Marker3D)                         │
│   │     └── Slot_Mod3    (Marker3D)                         │
│   ├── Seats (Node3D — seats_3d.gd)                          │
│   │     └── Seat_0..7    (Marker3D; 0 is local player)      │
│   │           ├── card slots (Marker3D) for hand            │
│   │           └── Nameplate3D (worldspace, opp. only)       │
│   └── HUD (CanvasLayer — hud.gd)                            │
│         ├── TopStrip, ResistanceBanner                      │
│         ├── YourChipsPanel, ChatToggle, BetBar              │
│         ├── ChatDrawer                                      │
│         ├── ClassRevealOverlay                              │
│         └── ShowdownOverlay                                 │
└─────────────────────────────────────────────────────────────┘
```

**Module boundaries:**
- `game.gd` — top-level. Subscribes to `WsClient.message_received`. Owns `apply_state(snap)` and `apply_private_hand(priv)`. Delegates to sub-widgets.
- `board_3d.gd` — updates board slot cards from `snap.board` + `snap.resistance_dropped`.
- `seats_3d.gd` — places local hand cards, manages opponent nameplates, turn highlight.
- `card_3d.gd` — one script per card mesh. Public: `set_card(card_dict)`, `set_face_down()`. Internally wraps a SubViewport + `card_face.gd` Control.
- `card_face.gd` — 2D Control drawn inside the SubViewport. Uniform layout for all card types; type label is a parameter.
- `hud.gd` — updates TopStrip, BetBar, YourChipsPanel, ResistanceBanner from snapshot. Emits `bet_action_requested(type, amount)` back to `game.gd`.
- `overlays/class_reveal.gd`, `overlays/showdown.gd` — modals. Shown/hidden by `game.gd`, read from snapshot + private hand.

**State ownership:** `game.gd` holds `_last_snap` and `_last_private`. Every widget is idempotent — it compares its inputs against stored state and updates only if something changed.

---

## 3D Scene Composition

**Camera:** Fixed position (no orbit/pan). Slightly behind and above Seat_0, ~15° down-tilt. Framed so the board is centered, local hand visible bottom, opponents fan across the far arc.

**Table:** One elliptical `MeshInstance3D` with a felt `StandardMaterial3D` (plain green, no texture for v1). Positioned at y=0.

**Board slots:** 5 `Marker3D` anchors in a row across the center of the table. Slot order left-to-right matches reveal order: Mod1 → Bounty → Mod2 → Terrain → Mod3. Each slot hosts one `CardInstance3D` scene, spawned at `_ready()`, starting face-down.

**Seats:** 8 `Marker3D` nodes arranged around the table. Seat_0 is closest to the camera (bottom); Seat_1..7 fan across the far arc with equal angular spacing. Each seat has:
- 5 card-slot Markers (class + 4 hand slots). Only Seat_0's cards are ever shown face-up.
- One `Nameplate3D` worldspace label (Seat_1..7 only; local player identity is shown via the HUD, not a worldspace label).

**Cards (the key rendering decision):**
Each card is a `MeshInstance3D` with a `QuadMesh` (aspect 5:7) and a `StandardMaterial3D`. The material's `albedo_texture` is a `ViewportTexture` pointing at a `SubViewport` child. The SubViewport renders a 2D Control (`card_face.gd`) that is designed for a 256×358 render target. Result: a 3D card whose face is a crisp 2D layout — no per-card art assets needed.

Face-down cards swap the material's albedo to a single shared "card back" texture (flat color + subtle pattern — programmatic, no asset).

`card_3d.gd` public API:
```
set_card(card_dict: Dictionary)    # weapon/item/infusion/class, uniform styling
set_face_down()
```

Extension hooks left in place for later animations (`flip_to_face_up()`, `slide_to(target: Marker3D)`) but not wired for this milestone.

---

## HUD Wiring

**TopStrip (CanvasLayer, top anchor):**
| Region | Source | Display |
|---|---|---|
| Left | `snap.room_code` | "Room: ABCD" |
| Left-center | `snap.phase` | Human label: `round_1` → "Bounty Mod 1", `round_2` → "Bounty", `round_3` → "Bounty Mod 2", `round_4` → "Terrain", `round_5` → "Bounty Mod 3", `showdown` → "Showdown" |
| Center | `snap.pot` | "Pot: 42cp" |
| Right | derived | "YOUR TURN" (gold) if `current_player_id == my_player_id`; "Waiting for {name}" otherwise |

**ResistanceBanner (directly under TopStrip):**
Red bar: "⚠ 25% Resistance Dropped!" — visible iff `snap.resistance_dropped == true`.

**BetBar (bottom-center, CanvasLayer):**
- Always present. When `current_player_id != my_player_id` OR the local player is folded/all-in, bar is dimmed (opacity 0.3) and non-interactive. When folded/all-in, bar hides entirely.
- **Check/Call button** — label is "Check" if `current_bet == my.bet_this_round`, otherwise "Call {diff}cp".
- **Raise button** — click opens an inline slider (min = `current_bet + 1`, max = `max_raise`). Slider commit sends `bet_action {type: "raise", amount: N}`.
- **Fold button** — instant send, no confirm.
- **All-In button** — sends `bet_action {type: "all_in"}`. Hidden if `my.chips <= current_bet` (you'd just be calling).

**YourChipsPanel (bottom-left):**
Two lines: `Chips: {my.chips}cp` / `Bet: {my.bet_this_round}cp`.

**ChatToggle + ChatDrawer (bottom-right):**
Toggle button labeled "Chat ▲" (closed) / "Chat ▼" (open). Drawer is a ~240×180 panel that slides up from bottom-right when toggled. Unread dot on toggle when a `chat` event arrives while closed; cleared on open.

**Nameplates (3D worldspace, seats 1..7):**
Each opponent nameplate shows: name / class_name / chips / bet_this_round. Badges: "FOLDED" (gray) or "ALL-IN" (red). Border glows gold when `current_player_id == this seat's player_id`.

---

## Screen & Overlay Flow

**Triggers:**
- Lobby → Game: `main.gd` swaps to `game.tscn` when a `game_state` event arrives while on the lobby screen.
- Class/Hand reveal: first `your_hand` event of a hand → `ClassRevealOverlay.show(private_hand)`. Dismissed by "Begin Round 1" button. Flag `_hand_reveal_shown` prevents re-firing on subsequent snapshots in the same hand; cleared if phase returns to `class_selection` (future multi-hand).
- Showdown: `snap.showdown != null` → `ShowdownOverlay.show(snap)`. Overlay pulls revealed hands from `snap.showdown.revealed_hands` (server protocol addition #3).
- Leave Game: button in ShowdownOverlay sends `leave_room` action, then `main.gd` swaps back to `main_menu`.

---

## Class/Hand Reveal Overlay

Modal, dims the 3D scene.

**Layout:**
- Title: "YOUR HAND"
- 1 large class card (same styling as other types, labeled "CLASS")
- 4 hand cards below in a row (Weapon / Item / Infusion / fourth_card)
- "Begin Round 1 ▸" button

**Data:** Reads `private_hand.hand.{weapon, item, infusion, fourth_card}` and `private_hand.class_card`.

**Dismissal:** Click button → overlay hides → game proceeds to normal 3D view.

---

## Showdown Overlay

Full-screen modal, dims the 3D scene. Ranked rows per player.

**Row layout (grid):**
| name + class | 5 cards (class + 4 hand) | damage + math | chips change |
|---|---|---|---|

**Row states:**
- Winner (`player_id in winner_ids`): gold left-border, gold-tinted background.
- Folded: 50% opacity, cards replaced by 5 "Folded" placeholders, damage shown as "—".

**Math helper (subtle):**
Below each damage total, a small muted line shows:
```
3 + 3 + 1 + 1 + 2 → 10 × 1.5
```
Derived from `damage_breakdown`: `weapon + class + items.join(" + ") + mods_sum → subtotal × infusion_mult`. No labels — readable only to players who want the breakdown. (A richer counting animation is an explicit future extension.)

**Board reference strip** at top: shows revealed mods / bounty / terrain inline as a sanity check for the damage math. Resistance-dropped tag shown if applicable.

**Bottom:** Single "Leave Game" button. Sends `leave_room`, returns to main menu.

**Data sources:**
- `snap.showdown.damages` — per-player totals.
- `snap.showdown.damage_breakdown` — per-player math parts (new field).
- `snap.showdown.winner_ids` — for highlight.
- `snap.showdown.pot_distribution` — chips won. Chips lost = derived from the pre-showdown snapshot's `chips` minus current `chips` + pot_distribution.
- `snap.showdown.revealed_hands` — per-player revealed cards (new field).
- `snap.board` — for the board reference strip.

---

## Data Flow Summary

Every `game_state` event:

```
WsClient.message_received(msg)
  → main.gd routes by event type
    → game.gd.apply_state(snap)
         board_3d.update(snap.board, snap.resistance_dropped)
         seats_3d.update(snap.players, snap.current_player_id, my_player_id)
         hud.update(snap, my_player_id)
         if snap.showdown != null and not _showdown_shown:
             showdown_overlay.show(snap, _last_private)
             _showdown_shown = true
```

Every `your_hand` event:

```
WsClient.message_received(msg)
  → main.gd routes
    → game.gd.apply_private_hand(priv)
         _last_private = priv
         if not _hand_reveal_shown:
             class_reveal_overlay.show(priv)
             _hand_reveal_shown = true
         seats_3d.set_local_hand(priv.hand, priv.class_card)
```

Player identity:
- `WsClient.my_player_id` is set when `name_set` arrives (depends on server fix #1).
- `game.gd` pulls `my_player_id` from `WsClient` at `_ready()`, stores it for fast lookup.

Signal cleanup:
- Every widget that connects to `WsClient.message_received` stores its Callable ref at connect time and disconnects in `_exit_tree`. Matches the existing lobby.gd pattern.

---

## Testing Approach

**Headless unit tests (GDScript, `godot --headless --script tests/run_all.gd`):**
- `hud.gd` — given a snapshot dict, assert bet bar state (enabled/disabled/hidden), check/call label, raise slider bounds, pot display, resistance banner visibility.
- `seats_3d.gd` — given `players[]` + `current_player_id` + `my_player_id`, assert opponent nameplate text, badges, turn highlight, local hand card population.
- `board_3d.gd` — given a board dict, assert which slots are face-up vs face-down and which card data each face-up slot holds.
- `card_face.gd` — given a card dict, assert rendered labels match (name, type, damage stat, flavor if any).

Target: ~15–20 tests. Keep each widget as a pure-ish function of its inputs.

**Manual integration test (the milestone):**
Two Godot clients (Tailscale between two laptops, or two windows + localhost) play one complete Classic hand:

1. Create a room on client A, join on client B.
2. Host starts game from lobby.
3. Both clients see class/hand reveal overlay → dismiss.
4. Play through 5 betting rounds (check/call/raise/fold from both sides).
5. Confirm board cards reveal at the right phase boundaries.
6. Confirm 25% resistance banner appears entering Round 3.
7. Reach showdown — verify overlay shows both hands, damage math, winner highlighted, pot distributed correctly.
8. Click "Leave Game" — both clients return to main menu cleanly.

**Edge cases to validate manually:**
- One player folds the others → sole-survivor walkover path (showdown with `damages == {}`).
- Player disconnects mid-bet → auto-fold propagates to remaining client.
- Invalid bet (amount over `max_raise`) → server sends `error` event, client shows toast.

**Not tested:** animations (none yet), network transport (server has 255 tests), Godot rendering output.

---

## Out of Scope

- Card-flip / deal / chip-slide animations.
- XP, save system, class leveling, shop, consumables.
- Multi-hand game loop, game-over detection.
- Opponent card-back rendering (nothing about opponent hands is public).
- Sound effects / music.
- Accessibility pass (color contrast, keyboard nav) — deferred until after vertical slice is playable.
- Pixel-perfect visual polish on the 3D table (plain green felt, no texture assets).

---

## Dependencies

- **Server:** requires the three protocol additions above (`name_set.player_id`, `showdown.damage_breakdown`, `showdown.revealed_hands`) landed before the Godot work can pass its milestone test.
- **Godot 4.6 Forward+** renderer (already selected in `client/project.godot`).
- **Existing WsClient autoload** — no changes required beyond storing `my_player_id` on `name_set`.
- **`lobby.gd` screen swap pattern** — `game.gd` and overlays follow the same programmatic-UI convention (all Controls built in `_build_ui()`, 20/24px fonts, 48px button min-height).

---

## Files to add

```
client/
├── scenes/
│   └── game/
│       ├── game.tscn               # Node3D root, instances Camera/Light/Table/Board/Seats/HUD
│       └── game.gd                 # top-level; apply_state / apply_private_hand
├── components/
│   ├── board_3d.gd                 # Node3D; manages 5 board slot cards
│   ├── seats_3d.gd                 # Node3D; manages seats, nameplates, local hand cards
│   ├── card_3d.gd                  # MeshInstance3D script; set_card / set_face_down
│   ├── card_face.gd                # Control rendered inside SubViewport; uniform face layout
│   ├── nameplate_3d.gd             # worldspace opponent label
│   └── hud.gd                      # CanvasLayer; TopStrip + BetBar + chips + chat toggle
├── overlays/
│   ├── class_reveal.gd             # modal; class + 4 cards + Begin button
│   └── showdown.gd                 # modal; ranked rows, math helper, Leave button
└── tests/
    ├── run_all.gd                  # entrypoint for `godot --headless`
    ├── test_hud.gd
    ├── test_seats.gd
    ├── test_board.gd
    └── test_card_face.gd
```

Plus small edits to:
- `client/autoload/ws_client.gd` — store `my_player_id` on `name_set`.
- `client/scenes/main.gd` — route `game_state` / `your_hand` events to the game screen; handle swap lobby↔game↔main_menu.
- `server/relay_server.py` — add `player_id` field to `name_set` response.
- `server/game_session.py` — include `damage_breakdown` and `revealed_hands` in showdown payload.
- `server/damage_calculator.py` — return breakdown alongside total.
- Relevant server tests updated to cover new fields.

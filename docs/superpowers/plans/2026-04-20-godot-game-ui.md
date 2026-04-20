# Godot Game UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Godot 4.6 in-hand UI (3D table + 2D HUD + overlays) so two clients can play one complete Classic hand end-to-end, matching `scripts/smoke_test_game.py`.

**Architecture:** Three small server additions (`name_set.player_id`, `showdown.damage_breakdown`, `showdown.revealed_hands`) unblock the Godot work. Client side: `main.gd` swaps to a new `game.tscn` (Node3D root, `game.gd`) that owns a 3D scene (table, board, seats, cards) plus a `CanvasLayer` HUD and two modal overlays (class/hand reveal, showdown). Every widget is idempotent — reads the latest snapshot + private hand and rebuilds from inputs.

**Tech Stack:** Python 3.10+, `websockets>=12.0`, `pytest` (server side); Godot 4.6 Forward+ renderer, GDScript (client side). Client UI is constructed programmatically — no designer-built .tscn content beyond the game root.

**Reference spec:** `docs/superpowers/specs/2026-04-20-godot-game-ui-design.md`.

**Test baseline:** 255 server tests passing → target 265+ after server changes. ~15 new Godot headless tests.

**Running server tests:** `cd server && pytest -v`
**Running Godot tests:** `cd client && godot --headless --script res://tests/run_all.gd` (from a Godot-installed shell). Exit code 0 on success.

---

## File Structure

**New server files:** none (modifications only)

**New client files:**
- `client/scenes/game/game.tscn` — Node3D root (empty; `game.gd` builds everything in code for testability)
- `client/scenes/game/game.gd` — top-level game script; `apply_state` / `apply_private_hand`
- `client/components/board_3d.gd` — 5 board slot cards
- `client/components/seats_3d.gd` — seat placement, local hand cards, nameplates
- `client/components/card_3d.gd` — single 3D card (QuadMesh + SubViewport)
- `client/components/card_face.gd` — Control rendered inside SubViewport
- `client/components/nameplate_3d.gd` — worldspace opponent label
- `client/components/hud.gd` — CanvasLayer with TopStrip, BetBar, chips, chat
- `client/overlays/class_reveal.gd` — class + 4 cards modal
- `client/overlays/showdown.gd` — ranked-rows showdown modal
- `client/tests/run_all.gd` — headless test entrypoint
- `client/tests/test_helpers.gd` — tiny assert helpers
- `client/tests/test_card_face.gd`
- `client/tests/test_board.gd`
- `client/tests/test_seats.gd`
- `client/tests/test_hud.gd`

**Modified server files:**
- `server/damage_calculator.py` — add `calculate_damage_breakdown(hand, board) -> dict`
- `server/tests/test_damage_calculator.py` — add breakdown tests
- `server/relay_server.py` — include `player_id` in `name_set` response
- `server/tests/test_relay.py` — assert `name_set` carries `player_id`
- `server/game_session.py` — include `damage_breakdown` + `revealed_hands` in showdown dict
- `server/tests/test_game_session.py` — assert new fields; walkover omits them
- `scripts/smoke_test_game.py` — update if it asserts on the showdown payload shape

**Modified client files:**
- `client/autoload/ws_client.gd` — store `my_player_id` on `name_set`
- `client/scenes/main.gd` — route `game_state` / `your_hand`; swap lobby ↔ game ↔ main_menu
- `client/scenes/screens/lobby.gd` — on `game_state`, emit `game_starting` so `main.gd` swaps

**Modified docs:**
- `docs/map_directories/lobby_networking.md` — new events/fields in the protocol
- `docs/map_directories/damage_calculator.md` — new breakdown helper
- `docs/map_directories/game_state_machine.md` — (no changes, but verify if showdown shape is described)
- `docs/map_directories/map.md` — register new client scripts + session log
- `CLAUDE.md` — build state update, key systems table

---

## Phase 1 — Server protocol additions

### Task 1: Add `calculate_damage_breakdown` to damage calculator

A pure function alongside `calculate_damage` that returns the math parts used by the showdown overlay. No change to `calculate_damage`'s signature or behavior.

**Files:**
- Modify: `server/damage_calculator.py`
- Modify: `server/tests/test_damage_calculator.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_damage_calculator.py`:

```python
# --- Breakdown helper ---

from damage_calculator import calculate_damage_breakdown

def test_breakdown_simple_weapon_plus_class():
    # Greatsword (3 slashing) + Soldier (2+LV=3 slashing) + no items/infusions
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST)
    bd = calculate_damage_breakdown(hand, board)
    assert bd["weapon"] == 3
    assert bd["class"] == 3
    assert bd["items"] == []
    assert bd["mods_sum"] == 0
    assert bd["infusion_mult"] == 1.0
    assert bd["total"] == 6

def test_breakdown_items_listed_individually():
    # Greatsword (3) + Soldier (3) + Blades (1 slashing) + Hammer (2 blunt)
    hand = Hand(weapon=GREATSWORD, items=[BLADES, HAMMER], infusions=[], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST)
    bd = calculate_damage_breakdown(hand, board)
    assert bd["items"] == [1, 2]
    assert bd["weapon"] == 3
    assert bd["class"] == 3
    assert bd["mods_sum"] == 0
    assert bd["total"] == 9

def test_breakdown_mods_sum_folds_positive_and_negative():
    # Greatsword (3 slashing) + Soldier (3 slashing) + mods: +1 slashing, -1 slashing
    # 2 slashing sources * (+1 + -1) = 0 net
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[], class_card=SOLDIER, level=1)
    board = BoardState(
        bounty=BEAST,
        active_bounty_mods=[MOD_VULN_SLASHING, MOD_DEFLECT_SLASHING],
    )
    bd = calculate_damage_breakdown(hand, board)
    assert bd["mods_sum"] == 0
    assert bd["total"] == 6

def test_breakdown_infusion_mult_reflected():
    # Sonic infusion vs Beast (vuln Sonic): multiplier = 1.5
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[THUNDEROUS], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST)
    bd = calculate_damage_breakdown(hand, board)
    assert bd["infusion_mult"] == 1.5
    assert bd["total"] == 9  # ceil(6 * 1.5)

def test_breakdown_total_matches_calculate_damage():
    # Property: breakdown["total"] == calculate_damage(hand, board) for a varied hand
    hand = Hand(weapon=SWORD_AND_BOARD, items=[BLADES], infusions=[THUNDEROUS], class_card=SPELLBLADE, level=2)
    board = BoardState(
        bounty=CONSTRUCT,
        terrain=CAVE,
        active_bounty_mods=[MOD_VULN_SLASHING],
        resistance_dropped=False,
    )
    assert calculate_damage_breakdown(hand, board)["total"] == calculate_damage(hand, board)
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_damage_calculator.py -v -k breakdown`
Expected: 5 tests fail with `ImportError` (no `calculate_damage_breakdown`).

- [ ] **Step 3: Implement `calculate_damage_breakdown`**

Append to `server/damage_calculator.py`:

```python
def calculate_damage_breakdown(hand: Hand, board: BoardState) -> dict:
    """Return the math parts behind calculate_damage for UI display.

    Shape: {weapon, class, items[], mods_sum, infusion_mult, total}
    - weapon: sum of weapon damage amounts
    - class: sum of class formula amounts (multi-class sums)
    - items: list of item bonus_values in hand order
    - mods_sum: net bounty-mod adjustment applied to base damage
    - infusion_mult: final multiplier (floored at 0.5)
    - total: ceil(base * infusion_mult) — matches calculate_damage
    """
    weapon_sum = sum(amount for amount, _ in hand.weapon.damage_types)
    class_sum = sum(_eval_formula(formula, hand.level) for formula, _ in hand.class_card.damage_formulas)
    items_list = [item.bonus_value for item in hand.items]

    sources = _damage_sources(hand)
    mods_sum = 0
    for mod in board.active_bounty_mods:
        matching = sum(1 for dtype, _ in sources if dtype.lower() == mod.affected_type.lower())
        mods_sum += mod.modifier * matching

    vuln_types: set[str] = {board.bounty.vulnerability}
    if board.terrain is not None:
        vuln_types.add(board.terrain.adds_vulnerability)
    resist_types: set[str] = set() if board.resistance_dropped else {board.bounty.resistance}

    multiplier = 1.0
    for infusion in hand.infusions:
        itype = infusion.infusion_type
        is_vuln = itype in vuln_types
        is_resist = itype in resist_types
        if is_vuln and is_resist:
            pass
        elif is_vuln:
            multiplier += 0.5
        elif is_resist:
            multiplier -= 0.5
    multiplier = max(multiplier, _MULTIPLIER_FLOOR)

    base = weapon_sum + class_sum + sum(items_list) + mods_sum
    total = math.ceil(base * multiplier)

    return {
        "weapon": weapon_sum,
        "class": class_sum,
        "items": items_list,
        "mods_sum": mods_sum,
        "infusion_mult": multiplier,
        "total": total,
    }
```

- [ ] **Step 4: Run to confirm PASS**

Run: `cd server && pytest tests/test_damage_calculator.py -v`
Expected: all previous tests + 5 new tests pass (29 total).

- [ ] **Step 5: Commit**

```bash
git add server/damage_calculator.py server/tests/test_damage_calculator.py
git commit -m "feat(damage): add calculate_damage_breakdown for UI math display"
```

---

### Task 2: Add `player_id` to `name_set` response

Client needs its own player_id so it can find itself in `snapshot.players[]` and compare to `current_player_id`.

**Files:**
- Modify: `server/relay_server.py`
- Modify: `server/tests/test_relay.py`

- [ ] **Step 1: Write the failing test**

Find the existing `set_name` test in `server/tests/test_relay.py` — look for a test that asserts the `name_set` response. Append (or adjust) a test that asserts `player_id` is present:

```python
async def test_name_set_includes_player_id(relay):
    async with client_ws(relay) as ws:
        await send(ws, action="set_name", name="Alice")
        reply = await recv(ws)
        assert reply["event"] == "name_set"
        assert reply["name"] == "Alice"
        assert "player_id" in reply
        assert isinstance(reply["player_id"], str)
        assert len(reply["player_id"]) > 0
```

If helpers `client_ws`, `send`, `recv`, and the `relay` fixture don't match the local names, mirror whatever pattern already exists in `test_relay.py`. Don't invent new helpers.

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_relay.py -v -k player_id`
Expected: FAIL — `name_set` payload has no `player_id` field.

- [ ] **Step 3: Add `player_id` in the relay handler**

In `server/relay_server.py`, find the `set_name` branch (around line 62-65):

```python
            if action == "set_name":
                ws.name = str(msg.get("name", "")).strip()[:32] or "Anonymous"
                await _send(ws, "name_set", name=ws.name)
                print(f"[connect] {ws.name}")
```

Change it to:

```python
            if action == "set_name":
                ws.name = str(msg.get("name", "")).strip()[:32] or "Anonymous"
                await _send(ws, "name_set", name=ws.name, player_id=_manager.get_player_id(ws))
                print(f"[connect] {ws.name}")
```

`_manager.get_player_id(ws)` already returns `str(id(ws))` — the same identity used by `RoomManager` and `GameSession`.

- [ ] **Step 4: Run to confirm PASS**

Run: `cd server && pytest tests/test_relay.py -v`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/relay_server.py server/tests/test_relay.py
git commit -m "feat(relay): expose player_id in name_set so clients know their identity"
```

---

### Task 3: Add `damage_breakdown` and `revealed_hands` to showdown snapshot

Extends the `self.showdown` dict in `GameSession._resolve_showdown`.

**Files:**
- Modify: `server/game_session.py`
- Modify: `server/tests/test_game_session.py`
- Possibly modify: `scripts/smoke_test_game.py` (only if it asserts on showdown fields)

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_game_session.py` (match the existing imports and fixtures at the top of that file — construct `GameSession` however the existing tests do):

```python
def test_showdown_includes_damage_breakdown():
    session, pids = _session_two_players()  # reuse whatever helper exists; otherwise build inline
    _play_to_showdown_both_still_in(session, pids)
    sd = session.showdown
    assert "damage_breakdown" in sd
    for pid in pids:
        bd = sd["damage_breakdown"][pid]
        assert set(bd.keys()) == {"weapon", "class", "items", "mods_sum", "infusion_mult", "total"}
        assert bd["total"] == sd["damages"][pid]

def test_showdown_includes_revealed_hands_for_non_folded():
    session, pids = _session_two_players()
    _play_to_showdown_both_still_in(session, pids)
    sd = session.showdown
    assert "revealed_hands" in sd
    for pid in pids:
        rh = sd["revealed_hands"][pid]
        assert set(rh.keys()) == {"weapon", "item", "infusion", "fourth_card", "class_card"}
        for v in rh.values():
            assert isinstance(v, dict)

def test_showdown_revealed_hands_omits_folded_players():
    session, pids = _session_three_players()  # >= 3 so one fold doesn't trigger walkover
    # p0 folds round 1; p1 and p2 proceed to showdown
    _fold_then_play_to_showdown(session, pids, folder=pids[0])
    sd = session.showdown
    assert pids[0] not in sd["revealed_hands"]
    assert pids[1] in sd["revealed_hands"]
    assert pids[2] in sd["revealed_hands"]

def test_walkover_showdown_has_empty_breakdown_and_hands():
    session, pids = _session_two_players()
    # p1 folds → p0 walks over
    session.apply_bet_action(pids[0], "check")  # p0 checks
    session.apply_bet_action(pids[1], "fold")   # p1 folds → walkover
    sd = session.showdown
    assert sd["damages"] == {}
    assert sd["damage_breakdown"] == {}
    assert sd["revealed_hands"] == {}
    assert sd["winner_ids"] == [pids[0]]
```

If helper functions `_session_two_players`, `_session_three_players`, `_play_to_showdown_both_still_in`, `_fold_then_play_to_showdown` don't exist, either reuse existing helpers under different names or add thin ones at the top of the test file that build a seeded `GameSession` and drive it through checks until `session.showdown is not None`. Don't overfit: the body of each helper is whatever already works in neighboring tests.

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_game_session.py -v -k "breakdown or revealed_hands or walkover_showdown"`
Expected: 4 tests fail with `KeyError: 'damage_breakdown'` / `'revealed_hands'`.

- [ ] **Step 3: Extend `_resolve_showdown` in `game_session.py`**

In `server/game_session.py`, the walkover branch and the normal showdown branch both set `self.showdown`. Update both.

Find the walkover branch (currently ending around line 145):

```python
        if len(non_folded) == 1:
            winner = non_folded[0]
            total = sum(p.amount for p in self.last_round_pots)
            self.chips[winner] += total
            self.gsm.force_hand_end_walkover()
            self.showdown = {
                "damages": {},
                "winner_ids": [winner],
                "pot_distribution": {winner: total},
            }
            return
```

Replace with:

```python
        if len(non_folded) == 1:
            winner = non_folded[0]
            total = sum(p.amount for p in self.last_round_pots)
            self.chips[winner] += total
            self.gsm.force_hand_end_walkover()
            self.showdown = {
                "damages": {},
                "winner_ids": [winner],
                "pot_distribution": {winner: total},
                "damage_breakdown": {},
                "revealed_hands": {},
            }
            return
```

Find the normal showdown branch (currently ending around line 155):

```python
        result = self.gsm.resolve_showdown()
        distribution = self._distribute_pots(result.winner_ids, result.damages)
        for pid, amount in distribution.items():
            self.chips[pid] += amount
        self.showdown = {
            "damages": dict(result.damages),
            "winner_ids": list(result.winner_ids),
            "pot_distribution": distribution,
        }
```

Replace with:

```python
        result = self.gsm.resolve_showdown()
        distribution = self._distribute_pots(result.winner_ids, result.damages)
        for pid, amount in distribution.items():
            self.chips[pid] += amount
        self.showdown = {
            "damages": dict(result.damages),
            "winner_ids": list(result.winner_ids),
            "pot_distribution": distribution,
            "damage_breakdown": self._build_damage_breakdown(non_folded),
            "revealed_hands": self._build_revealed_hands(non_folded),
        }
```

Then add both helpers to the class (anywhere after `_resolve_showdown`). Import the breakdown helper at the top of the file:

```python
from damage_calculator import calculate_damage_breakdown
```

```python
    def _build_damage_breakdown(self, non_folded_ids: list) -> dict:
        """Per-player math parts from damage_calculator — UI reads this to show the math line."""
        from damage_calculator import BoardState

        board = BoardState(
            bounty=self.gsm._board.bounty,
            terrain=self.gsm._revealed_terrain,
            active_bounty_mods=list(self.gsm._active_mods),
            resistance_dropped=self.gsm.resistance_dropped,
        )
        out = {}
        for pid in non_folded_ids:
            player = next(p for p in self.gsm.players if p.player_id == pid)
            hand = self.gsm._build_hand(player)
            out[pid] = calculate_damage_breakdown(hand, board)
        return out

    def _build_revealed_hands(self, non_folded_ids: list) -> dict:
        """Reveal each non-folded player's hand + class for the showdown overlay."""
        out = {}
        for pid in non_folded_ids:
            priv = self.private_hand(pid)
            if priv is None:
                continue
            out[pid] = {
                "weapon":      priv["hand"]["weapon"],
                "item":        priv["hand"]["item"],
                "infusion":    priv["hand"]["infusion"],
                "fourth_card": priv["hand"]["fourth_card"],
                "class_card":  priv["class_card"],
            }
        return out
```

Reaching into `self.gsm._board` / `_revealed_terrain` / `_active_mods` / `_build_hand` is the same private-state access `_resolve_showdown` itself uses indirectly; `GameStateMachine` already exposes equivalent public properties (`revealed_bounty`, `revealed_terrain`, `active_mods`) — prefer those if they match exactly. If a matching public property exists for every field, use the public form instead.

Check `server/game_state_machine.py` for any of these public properties — if they exist, swap the underscore accesses for them. `_build_hand` is an internal helper; duplicate its small body inline here rather than reaching through underscores:

```python
    def _build_showdown_hand(self, player) -> "Hand":
        from card_data import ItemCard
        from damage_calculator import Hand

        ph = player.hand
        items = [ph.item]
        infusions = [ph.infusion]
        if isinstance(ph.fourth_card, ItemCard):
            items.append(ph.fourth_card)
        else:
            infusions.append(ph.fourth_card)
        return Hand(
            weapon=ph.weapon,
            items=items,
            infusions=infusions,
            class_card=player.class_card,
            level=1,
        )
```

Then in `_build_damage_breakdown` call `self._build_showdown_hand(player)` instead of `self.gsm._build_hand(player)`.

- [ ] **Step 4: Run to confirm PASS**

Run: `cd server && pytest tests/test_game_session.py -v`
Expected: all tests pass (existing + 4 new).

- [ ] **Step 5: Run full server test suite**

Run: `cd server && pytest -v`
Expected: 259 passing (255 previous + 4 new, assuming Task 1 added 5 earlier for 264 total; adjust as you go).

- [ ] **Step 6: Check smoke_test_game.py**

Run: `head -n 80 scripts/smoke_test_game.py`

If the script prints or asserts on the showdown payload and you'd like it to exercise the new fields, extend its print statements to include `damage_breakdown` and `revealed_hands`. Otherwise leave it alone — the script already drives a full hand and will keep working.

- [ ] **Step 7: Commit**

```bash
git add server/game_session.py server/tests/test_game_session.py
# Only add smoke_test_game.py if you edited it
git commit -m "feat(game_session): add damage_breakdown and revealed_hands to showdown payload"
```

---

## Phase 2 — Client autoload + routing

### Task 4: Store `my_player_id` on `name_set` in WsClient

**Files:**
- Modify: `client/autoload/ws_client.gd`

(No Godot headless tests yet — the test harness lands in Task 6. This task is small and verified by manual inspection; later tests cover the HUD-side consumer.)

- [ ] **Step 1: Add field + intercept message_received**

Replace the contents of `client/autoload/ws_client.gd` with:

```gdscript
extends Node

signal connected
signal disconnected
signal message_received(data: Dictionary)

var my_player_id: String = ""

var _socket: WebSocketPeer = null
var _is_connected: bool = false


func connect_to_server(url: String) -> void:
	_socket = WebSocketPeer.new()
	var err := _socket.connect_to_url(url)
	if err != OK:
		push_error("WsClient: failed to initiate connection to " + url)


func send_message(data: Dictionary) -> void:
	if _socket == null or not _is_connected:
		push_error("WsClient: send called while not connected")
		return
	_socket.send_text(JSON.stringify(data))


func disconnect_from_server() -> void:
	if _socket != null:
		_socket.close()
	my_player_id = ""


func _process(_delta: float) -> void:
	if _socket == null:
		return
	_socket.poll()
	match _socket.get_ready_state():
		WebSocketPeer.STATE_OPEN:
			if not _is_connected:
				_is_connected = true
				connected.emit()
			while _socket.get_available_packet_count() > 0:
				var raw := _socket.get_packet().get_string_from_utf8()
				var parsed = JSON.parse_string(raw)
				if parsed != null:
					_maybe_store_player_id(parsed)
					message_received.emit(parsed)
		WebSocketPeer.STATE_CLOSING:
			pass
		WebSocketPeer.STATE_CLOSED:
			if _is_connected:
				_is_connected = false
				disconnected.emit()
			_socket = null


func _maybe_store_player_id(data) -> void:
	if typeof(data) != TYPE_DICTIONARY:
		return
	if data.get("event") == "name_set":
		my_player_id = str(data.get("player_id", ""))
```

`my_player_id` is reset on disconnect so re-connecting to a different server yields a fresh identity. Subscribers see the `message_received` signal after the store, so any listener can read `WsClient.my_player_id` inside its handler.

- [ ] **Step 2: Sanity-launch the lobby**

Open the Godot project, play the scene, enter a name, watch the relay log — no crashes expected. Confirm the name flow still works (existing functionality).

- [ ] **Step 3: Commit**

```bash
git add client/autoload/ws_client.gd
git commit -m "feat(client): WsClient stores my_player_id from name_set"
```

---

### Task 5: Route `game_state` / `your_hand` in main.gd

Currently `main.gd` only swaps between `name_entry`, `main_menu`, `lobby`. It needs to swap to the game screen when a `game_state` event arrives, and back to `main_menu` on `leave_room` during a game.

**Files:**
- Modify: `client/scenes/main.gd`
- Modify: `client/scenes/screens/lobby.gd` — emit a `game_starting` signal so the swap happens from main.gd, not the lobby itself

- [ ] **Step 1: Add `game_starting` signal to lobby**

In `client/scenes/screens/lobby.gd`, add the signal near the top (after `signal left_room`):

```gdscript
signal left_room
signal game_starting
```

And at the bottom of `_on_message` add a new case — while keeping the existing `player_joined` / `player_left` / `chat` handlers intact:

```gdscript
func _on_message(data: Dictionary) -> void:
	match data.get("event"):
		"player_joined":
			_add_player_label(data["name"])
			_add_chat("[Server]", data["name"] + " joined.")
		"player_left":
			_remove_player_label(data["name"])
			_add_chat("[Server]", data["name"] + " left.")
		"chat":
			_add_chat(data.get("from", "?"), data.get("text", ""))
		"game_state":
			game_starting.emit()
```

This avoids double-subscription: `lobby.gd` keeps listening until the swap happens, then `main.gd` attaches the game screen which takes over.

- [ ] **Step 2: Add game screen swap to main.gd**

Replace the contents of `client/scenes/main.gd` with:

```gdscript
extends Control

var _current_screen: Node = null
var _player_name: String = ""


func _ready() -> void:
	_show_name_entry()


func _show_name_entry() -> void:
	var screen: Control = load("res://scenes/screens/name_entry.gd").new()
	screen.name_confirmed.connect(_on_name_confirmed)
	_swap(screen)


func _show_main_menu() -> void:
	var screen: Control = load("res://scenes/screens/main_menu.gd").new()
	screen.player_name = _player_name
	screen.room_created.connect(_on_room_created)
	screen.room_joined.connect(_on_room_joined)
	_swap(screen)


func _show_lobby(room_code: String, players: Array) -> void:
	var screen: Control = load("res://scenes/screens/lobby.gd").new()
	screen.player_name = _player_name
	screen.room_code = room_code
	screen.initial_players = players
	screen.left_room.connect(_on_left_room)
	screen.game_starting.connect(_on_game_starting)
	_swap(screen)


func _show_game() -> void:
	var screen: Node3D = load("res://scenes/game/game.gd").new()
	screen.left_game.connect(_on_left_game)
	_swap(screen)


func _swap(new_screen: Node) -> void:
	if _current_screen != null:
		_current_screen.queue_free()
	_current_screen = new_screen
	add_child(_current_screen)
	if new_screen is Control:
		(new_screen as Control).set_anchors_preset(Control.PRESET_FULL_RECT)


func _on_name_confirmed(player_name: String) -> void:
	_player_name = player_name
	_show_main_menu()


func _on_room_created(room_code: String) -> void:
	_show_lobby(room_code, [_player_name])


func _on_room_joined(room_code: String, players: Array) -> void:
	_show_lobby(room_code, players)


func _on_left_room() -> void:
	WsClient.disconnect_from_server()
	_show_main_menu()


func _on_game_starting() -> void:
	_show_game()


func _on_left_game() -> void:
	WsClient.send_message({"action": "leave_room"})
	WsClient.disconnect_from_server()
	_show_main_menu()
```

The `_swap` helper is generalized to handle any `Node` (game screen is `Node3D`, others are `Control`); the `set_anchors_preset` call only applies to Controls.

Note: the file will fail to load `res://scenes/game/game.gd` until Task 15 lands. That's OK — the existing `name_entry` / `main_menu` / `lobby` path runs first and the game load only happens via a signal that won't fire until the server sends a `game_state`.

- [ ] **Step 3: Smoke-launch**

Run the project. Confirm name → main_menu → lobby still works. Don't press start_game yet (game screen doesn't exist).

- [ ] **Step 4: Commit**

```bash
git add client/scenes/main.gd client/scenes/screens/lobby.gd
git commit -m "feat(client): route game_state from lobby and swap to game screen"
```

---

## Phase 3 — Test harness + card face

### Task 6: Minimal headless test harness

One runner, one assert helper, zero dependencies. Godot's `--headless --script` can execute any `SceneTree` script. We emit exit code 0 on all-pass, 1 otherwise.

**Files:**
- Create: `client/tests/run_all.gd`
- Create: `client/tests/test_helpers.gd`

- [ ] **Step 1: Create `test_helpers.gd`**

```gdscript
extends RefCounted
class_name TestHelpers


static func assert_eq(actual, expected, label: String) -> bool:
	if actual == expected:
		print("  PASS  ", label)
		return true
	print("  FAIL  ", label, " — expected ", expected, " got ", actual)
	return false


static func assert_true(cond: bool, label: String) -> bool:
	if cond:
		print("  PASS  ", label)
		return true
	print("  FAIL  ", label, " — expected true")
	return false


static func assert_false(cond: bool, label: String) -> bool:
	if not cond:
		print("  PASS  ", label)
		return true
	print("  FAIL  ", label, " — expected false")
	return false


static func assert_in(needle, haystack, label: String) -> bool:
	if needle in haystack:
		print("  PASS  ", label)
		return true
	print("  FAIL  ", label, " — ", needle, " not in ", haystack)
	return false
```

- [ ] **Step 2: Create `run_all.gd` (placeholder that reports 0 suites)**

```gdscript
extends SceneTree


func _initialize() -> void:
	print("Running Godot UI tests...")
	var fails := 0
	# Each suite class_name is added here as tasks land. class_name makes the
	# class globally referenceable; static run() returns the failure count.
	if fails == 0:
		print("ALL TESTS PASSED")
		quit(0)
	else:
		print("TESTS FAILED: ", fails)
		quit(1)
```

- [ ] **Step 3: Run the harness**

From a Godot-installed shell:

Run: `cd client && godot --headless --script res://tests/run_all.gd`
Expected: prints `ALL TESTS PASSED`, exits 0. If Godot isn't on PATH in this shell, skip running this step — but confirm by sight that the file is syntactically valid (no red in the editor).

- [ ] **Step 4: Commit**

```bash
git add client/tests/run_all.gd client/tests/test_helpers.gd
git commit -m "test(client): add minimal headless test runner for Godot UI"
```

---

### Task 7: `card_face.gd` — uniform Control for card faces

A single `Control` drawn inside a SubViewport. Parameterized by a card dict and a type label; the same layout is used for weapon/item/infusion/class.

**Files:**
- Create: `client/components/card_face.gd`
- Create: `client/tests/test_card_face.gd`
- Modify: `client/tests/run_all.gd` — register the suite

- [ ] **Step 1: Write `test_card_face.gd`**

```gdscript
extends RefCounted
class_name TestCardFace

const CardFace := preload("res://components/card_face.gd")


static func run() -> int:
	print("-- test_card_face --")
	var fails := 0
	fails += _test_shows_name_and_stat()
	fails += _test_class_label()
	fails += _test_handles_missing_stat()
	return fails


static func _make_face() -> Node:
	return CardFace.new()


static func _test_shows_name_and_stat() -> int:
	var face := _make_face()
	face.set_card({"name": "Longsword", "damage_types": [[3, "slashing"]]}, "weapon")
	var fails := 0
	if not TestHelpers.assert_eq(face.get_name_text(), "Longsword", "weapon name"): fails += 1
	if not TestHelpers.assert_eq(face.get_type_text(), "WEAPON", "type label upper"): fails += 1
	if not TestHelpers.assert_in("3", face.get_stat_text(), "weapon stat includes damage"): fails += 1
	face.free()
	return fails


static func _test_class_label() -> int:
	var face := _make_face()
	face.set_card({"name": "Paladin", "damage_formulas": [["2+LV", "slashing"]]}, "class")
	var fails := 0
	if not TestHelpers.assert_eq(face.get_name_text(), "Paladin", "class name"): fails += 1
	if not TestHelpers.assert_eq(face.get_type_text(), "CLASS", "class type label"): fails += 1
	if not TestHelpers.assert_in("2+LV", face.get_stat_text(), "class stat shows formula"): fails += 1
	face.free()
	return fails


static func _test_handles_missing_stat() -> int:
	var face := _make_face()
	face.set_card({"name": "Mystery"}, "item")
	var fails := 0
	if not TestHelpers.assert_eq(face.get_name_text(), "Mystery", "name only"): fails += 1
	if not TestHelpers.assert_eq(face.get_stat_text(), "", "stat empty when absent"): fails += 1
	face.free()
	return fails
```

- [ ] **Step 2: Register the suite in `run_all.gd`**

Edit `_initialize()` in `client/tests/run_all.gd` — add the suite call before the pass/fail check:

```gdscript
func _initialize() -> void:
	print("Running Godot UI tests...")
	var fails := 0
	fails += TestCardFace.run()
	if fails == 0:
		print("ALL TESTS PASSED")
		quit(0)
	else:
		print("TESTS FAILED: ", fails)
		quit(1)
```

- [ ] **Step 3: Run to confirm FAIL**

Run: `cd client && godot --headless --script res://tests/run_all.gd`
Expected: fails because `card_face.gd` doesn't exist yet.

- [ ] **Step 4: Implement `card_face.gd`**

```gdscript
extends Control


const FACE_SIZE := Vector2(256, 358)
const COLOR_BG := Color(0.12, 0.14, 0.20, 1.0)
const COLOR_BORDER := Color(0.55, 0.60, 0.75, 1.0)
const COLOR_NAME := Color(1.0, 1.0, 1.0, 1.0)
const COLOR_TYPE := Color(0.90, 0.75, 0.25, 1.0)
const COLOR_STAT := Color(0.90, 0.90, 0.90, 1.0)

var _name_lbl: Label
var _type_lbl: Label
var _stat_lbl: Label


func _init() -> void:
	custom_minimum_size = FACE_SIZE
	size = FACE_SIZE
	var bg := ColorRect.new()
	bg.color = COLOR_BG
	bg.size = FACE_SIZE
	add_child(bg)

	var border := Panel.new()
	border.size = FACE_SIZE
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0, 0, 0, 0)
	sb.border_color = COLOR_BORDER
	sb.border_width_left = 4
	sb.border_width_right = 4
	sb.border_width_top = 4
	sb.border_width_bottom = 4
	sb.corner_radius_top_left = 10
	sb.corner_radius_top_right = 10
	sb.corner_radius_bottom_left = 10
	sb.corner_radius_bottom_right = 10
	border.add_theme_stylebox_override("panel", sb)
	add_child(border)

	_type_lbl = Label.new()
	_type_lbl.position = Vector2(16, 14)
	_type_lbl.size = Vector2(FACE_SIZE.x - 32, 24)
	_type_lbl.add_theme_color_override("font_color", COLOR_TYPE)
	_type_lbl.add_theme_font_size_override("font_size", 18)
	add_child(_type_lbl)

	_name_lbl = Label.new()
	_name_lbl.position = Vector2(16, 52)
	_name_lbl.size = Vector2(FACE_SIZE.x - 32, 40)
	_name_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_name_lbl.add_theme_color_override("font_color", COLOR_NAME)
	_name_lbl.add_theme_font_size_override("font_size", 26)
	add_child(_name_lbl)

	_stat_lbl = Label.new()
	_stat_lbl.position = Vector2(16, FACE_SIZE.y - 60)
	_stat_lbl.size = Vector2(FACE_SIZE.x - 32, 44)
	_stat_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_stat_lbl.add_theme_color_override("font_color", COLOR_STAT)
	_stat_lbl.add_theme_font_size_override("font_size", 20)
	add_child(_stat_lbl)


func set_card(card: Dictionary, type_label: String) -> void:
	_type_lbl.text = type_label.to_upper()
	_name_lbl.text = str(card.get("name", ""))
	_stat_lbl.text = _format_stat(card, type_label)


func get_name_text() -> String:
	return _name_lbl.text


func get_type_text() -> String:
	return _type_lbl.text


func get_stat_text() -> String:
	return _stat_lbl.text


func _format_stat(card: Dictionary, type_label: String) -> String:
	match type_label:
		"weapon":
			return _format_damage_types(card.get("damage_types", []))
		"class":
			return _format_formulas(card.get("damage_formulas", []))
		"item":
			var bonus = card.get("bonus_value", null)
			var dtype := str(card.get("damage_type", ""))
			if bonus == null:
				return ""
			return "+%s %s" % [str(bonus), dtype]
		"infusion":
			var itype := str(card.get("infusion_type", ""))
			if itype == "":
				return ""
			return itype.to_upper()
		_:
			return ""


func _format_damage_types(pairs) -> String:
	if pairs == null or pairs.size() == 0:
		return ""
	var parts := []
	for pair in pairs:
		parts.append("%s %s" % [str(pair[0]), str(pair[1])])
	return ", ".join(parts)


func _format_formulas(pairs) -> String:
	if pairs == null or pairs.size() == 0:
		return ""
	var parts := []
	for pair in pairs:
		parts.append("%s (%s)" % [str(pair[0]), str(pair[1])])
	return ", ".join(parts)
```

- [ ] **Step 5: Run to confirm PASS**

Run: `cd client && godot --headless --script res://tests/run_all.gd`
Expected: `test_card_face` suite passes; overall `ALL TESTS PASSED`.

- [ ] **Step 6: Commit**

```bash
git add client/components/card_face.gd client/tests/test_card_face.gd client/tests/run_all.gd
git commit -m "feat(client): add card_face Control with uniform layout for all card types"
```

---

## Phase 4 — 3D card + board

### Task 8: `card_3d.gd` — MeshInstance3D wrapping a SubViewport face

One script per 3D card mesh. Owns a `SubViewport`, a `Control` (`card_face.gd`) inside it, and a `StandardMaterial3D` whose `albedo_texture` is that viewport's texture. Supports face-down via a shared flat-color back.

No new headless test — the visual is the test (verified manually in Task 15). Behavior is thin.

**Files:**
- Create: `client/components/card_3d.gd`

- [ ] **Step 1: Implement `card_3d.gd`**

```gdscript
extends MeshInstance3D


const CARD_WIDTH := 0.5
const CARD_HEIGHT := 0.7
const FACE_SIZE := Vector2i(256, 358)

const COLOR_BACK := Color(0.18, 0.12, 0.28)
const CardFace := preload("res://components/card_face.gd")

var _viewport: SubViewport
var _face: Control
var _face_material: StandardMaterial3D
var _back_material: StandardMaterial3D
var _current: Dictionary = {}
var _current_type: String = ""
var _face_up: bool = false


func _ready() -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2(CARD_WIDTH, CARD_HEIGHT)
	mesh = quad

	_viewport = SubViewport.new()
	_viewport.size = FACE_SIZE
	_viewport.disable_3d = true
	_viewport.transparent_bg = false
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_viewport)

	_face = CardFace.new()
	_viewport.add_child(_face)

	_face_material = StandardMaterial3D.new()
	_face_material.albedo_texture = _viewport.get_texture()
	_face_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED

	_back_material = StandardMaterial3D.new()
	_back_material.albedo_color = COLOR_BACK
	_back_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED

	set_face_down()


func set_card(card: Dictionary, type_label: String) -> void:
	_current = card
	_current_type = type_label
	_face.set_card(card, type_label)
	material_override = _face_material
	_face_up = true


func set_face_down() -> void:
	material_override = _back_material
	_face_up = false


func is_face_up() -> bool:
	return _face_up


func current_card() -> Dictionary:
	return _current


func current_type() -> String:
	return _current_type
```

- [ ] **Step 2: Commit**

```bash
git add client/components/card_3d.gd
git commit -m "feat(client): add card_3d mesh wrapping SubViewport card face"
```

---

### Task 9: `board_3d.gd` — manage 5 board slot cards

Spawns 5 `card_3d.gd` instances at `_ready` (face-down), then `update(board_dict, resistance_dropped)` swaps in cards for revealed slots.

**Files:**
- Create: `client/components/board_3d.gd`
- Create: `client/tests/test_board.gd`
- Modify: `client/tests/run_all.gd` — register suite

- [ ] **Step 1: Write `test_board.gd`**

```gdscript
extends RefCounted
class_name TestBoard

const Board3D := preload("res://components/board_3d.gd")
const Card3D := preload("res://components/card_3d.gd")


static func run() -> int:
	print("-- test_board --")
	var fails := 0
	fails += _test_starts_all_face_down()
	fails += _test_mods_reveal_in_order()
	fails += _test_bounty_in_slot_1()
	fails += _test_terrain_in_slot_3()
	return fails


static func _make() -> Node3D:
	var b = Board3D.new()
	# Call _ready manually — orphan nodes work for property-only assertions.
	b._ready()
	return b


static func _test_starts_all_face_down() -> int:
	var b := _make()
	b.update({"bounty": null, "terrain": null, "mods_revealed": []}, false)
	var fails := 0
	for i in range(5):
		if not TestHelpers.assert_false(b.slot_face_up(i), "slot %d face-down initially" % i): fails += 1
	b.free()
	return fails


static func _test_mods_reveal_in_order() -> int:
	var b := _make()
	var mod_a := {"name": "ModA", "affected_type": "slashing", "modifier": 1}
	var mod_b := {"name": "ModB", "affected_type": "blunt", "modifier": -1}
	b.update({"bounty": null, "terrain": null, "mods_revealed": [mod_a, mod_b]}, false)
	var fails := 0
	if not TestHelpers.assert_true(b.slot_face_up(0), "slot 0 (mod1) face-up"): fails += 1
	if not TestHelpers.assert_eq(b.slot_card(0).get("name"), "ModA", "slot 0 holds ModA"): fails += 1
	# mod2 goes into slot 2 per round order: mod1 → bounty → mod2 → terrain → mod3
	if not TestHelpers.assert_true(b.slot_face_up(2), "slot 2 (mod2) face-up"): fails += 1
	if not TestHelpers.assert_eq(b.slot_card(2).get("name"), "ModB", "slot 2 holds ModB"): fails += 1
	b.free()
	return fails


static func _test_bounty_in_slot_1() -> int:
	var b := _make()
	var bounty := {"name": "Undead", "vulnerability": "Holy", "resistance": "Shadow"}
	b.update({"bounty": bounty, "terrain": null, "mods_revealed": [{"name": "M1", "affected_type": "slashing", "modifier": 1}]}, false)
	var fails := 0
	if not TestHelpers.assert_true(b.slot_face_up(1), "slot 1 (bounty) face-up"): fails += 1
	if not TestHelpers.assert_eq(b.slot_card(1).get("name"), "Undead", "slot 1 holds bounty"): fails += 1
	b.free()
	return fails


static func _test_terrain_in_slot_3() -> int:
	var b := _make()
	var terrain := {"name": "Graveyard", "adds_vulnerability": "Holy"}
	b.update({
		"bounty": {"name": "Undead", "vulnerability": "Holy", "resistance": "Shadow"},
		"terrain": terrain,
		"mods_revealed": [
			{"name": "M1", "affected_type": "s", "modifier": 1},
			{"name": "M2", "affected_type": "s", "modifier": 1},
		],
	}, false)
	var fails := 0
	if not TestHelpers.assert_true(b.slot_face_up(3), "slot 3 (terrain) face-up"): fails += 1
	if not TestHelpers.assert_eq(b.slot_card(3).get("name"), "Graveyard", "slot 3 holds terrain"): fails += 1
	b.free()
	return fails
```

- [ ] **Step 2: Register the suite**

Add `TestBoard.run()` to `_initialize()` in `client/tests/run_all.gd`:

```gdscript
	fails += TestCardFace.run()
	fails += TestBoard.run()
```

- [ ] **Step 3: Run to confirm FAIL**

Run: `cd client && godot --headless --script res://tests/run_all.gd`
Expected: fails because `board_3d.gd` doesn't exist.

- [ ] **Step 4: Implement `board_3d.gd`**

Slot order (left-to-right at the table): `[mod1, bounty, mod2, terrain, mod3]`.

```gdscript
extends Node3D


const Card3D := preload("res://components/card_3d.gd")

# Slot layout in world space — z=0 is the table center line.
const SLOT_POSITIONS := [
	Vector3(-1.2, 0.02, -0.1),
	Vector3(-0.6, 0.02, -0.1),
	Vector3( 0.0, 0.02, -0.1),
	Vector3( 0.6, 0.02, -0.1),
	Vector3( 1.2, 0.02, -0.1),
]

const SLOT_TYPES := ["mod", "bounty", "mod", "terrain", "mod"]

var _cards: Array = []  # Array of card_3d instances, length 5


func _ready() -> void:
	for i in range(5):
		var c = Card3D.new()
		c.position = SLOT_POSITIONS[i]
		c.rotation_degrees = Vector3(-90, 0, 0)  # face up from table plane
		add_child(c)
		c._ready()  # ensure inner SubViewport spins up even if not yet in a SceneTree
		_cards.append(c)


func update(board: Dictionary, resistance_dropped: bool) -> void:
	# Order of reveal matches round progression:
	#   round_1 reveals mods_revealed[0]          → slot 0
	#   round_2 reveals bounty                    → slot 1
	#   round_3 reveals mods_revealed[1]          → slot 2
	#   round_4 reveals terrain                   → slot 3
	#   round_5 reveals mods_revealed[2]          → slot 4
	var mods = board.get("mods_revealed", []) as Array
	var bounty = board.get("bounty")
	var terrain = board.get("terrain")

	_set_slot(0, mods[0] if mods.size() > 0 else null, "mod")
	_set_slot(1, bounty, "bounty")
	_set_slot(2, mods[1] if mods.size() > 1 else null, "mod")
	_set_slot(3, terrain, "terrain")
	_set_slot(4, mods[2] if mods.size() > 2 else null, "mod")


func slot_face_up(i: int) -> bool:
	return _cards[i].is_face_up()


func slot_card(i: int) -> Dictionary:
	return _cards[i].current_card()


func _set_slot(i: int, card, type_label: String) -> void:
	if card == null:
		_cards[i].set_face_down()
	else:
		_cards[i].set_card(card, type_label)
```

- [ ] **Step 5: Run to confirm PASS**

Run: `cd client && godot --headless --script res://tests/run_all.gd`
Expected: `test_board` suite passes.

- [ ] **Step 6: Commit**

```bash
git add client/components/board_3d.gd client/tests/test_board.gd client/tests/run_all.gd
git commit -m "feat(client): add board_3d with 5 slot cards, mod/bounty/terrain layout"
```

---

## Phase 5 — Nameplate + seats

### Task 10: `nameplate_3d.gd` — worldspace opponent label

One `Sprite3D`-mode `Label3D` or a `SubViewport`-backed Control. Simpler: use Godot's built-in `Label3D` — it handles billboard/outline/shadow and keeps us off another SubViewport.

**Files:**
- Create: `client/components/nameplate_3d.gd`

- [ ] **Step 1: Implement `nameplate_3d.gd`**

```gdscript
extends Node3D


const COLOR_DEFAULT := Color(0.90, 0.90, 0.90)
const COLOR_FOLDED := Color(0.50, 0.50, 0.50)
const COLOR_ALLIN := Color(0.95, 0.35, 0.35)
const COLOR_TURN := Color(0.95, 0.82, 0.30)

var _name_lbl: Label3D
var _class_lbl: Label3D
var _chips_lbl: Label3D
var _badge_lbl: Label3D

var _is_turn: bool = false


func _ready() -> void:
	_name_lbl = Label3D.new()
	_name_lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_name_lbl.font_size = 36
	_name_lbl.outline_size = 4
	_name_lbl.position = Vector3(0, 0.28, 0)
	add_child(_name_lbl)

	_class_lbl = Label3D.new()
	_class_lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_class_lbl.font_size = 26
	_class_lbl.outline_size = 3
	_class_lbl.position = Vector3(0, 0.17, 0)
	_class_lbl.modulate = Color(0.85, 0.80, 0.60)
	add_child(_class_lbl)

	_chips_lbl = Label3D.new()
	_chips_lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_chips_lbl.font_size = 24
	_chips_lbl.outline_size = 3
	_chips_lbl.position = Vector3(0, 0.07, 0)
	add_child(_chips_lbl)

	_badge_lbl = Label3D.new()
	_badge_lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_badge_lbl.font_size = 22
	_badge_lbl.outline_size = 3
	_badge_lbl.position = Vector3(0, -0.04, 0)
	_badge_lbl.visible = false
	add_child(_badge_lbl)


func update(entry: Dictionary, is_turn: bool) -> void:
	_is_turn = is_turn
	_name_lbl.text = str(entry.get("name", "?"))
	_class_lbl.text = str(entry.get("class_name", "") if entry.get("class_name") != null else "")
	_chips_lbl.text = "%d cp  (bet %d)" % [int(entry.get("chips", 0)), int(entry.get("bet_this_round", 0))]

	var folded := bool(entry.get("folded", false))
	var all_in := bool(entry.get("all_in", false))
	if folded:
		_name_lbl.modulate = COLOR_FOLDED
		_badge_lbl.text = "FOLDED"
		_badge_lbl.modulate = COLOR_FOLDED
		_badge_lbl.visible = true
	elif all_in:
		_name_lbl.modulate = COLOR_ALLIN
		_badge_lbl.text = "ALL-IN"
		_badge_lbl.modulate = COLOR_ALLIN
		_badge_lbl.visible = true
	else:
		_name_lbl.modulate = COLOR_TURN if is_turn else COLOR_DEFAULT
		_badge_lbl.visible = false
```

`update` is idempotent — call on every snapshot.

- [ ] **Step 2: Commit**

```bash
git add client/components/nameplate_3d.gd
git commit -m "feat(client): add nameplate_3d Label3D-based opponent label with turn/fold/all-in states"
```

---

### Task 11: `seats_3d.gd` — seats, nameplates, local hand cards

Owns `Seat_0..7` as children — each seat is a `Node3D` with card slots (Marker3D positions) and (for seats 1..7) a `Nameplate3D`. On `update(snap, my_player_id)`: places opponents into seats 1..7 in `players[]` order skipping `my_player_id`, updates their nameplates, highlights the seat whose player has the turn. On `set_local_hand(hand, class_card)`: updates Seat_0's 5 cards face-up.

**Files:**
- Create: `client/components/seats_3d.gd`
- Create: `client/tests/test_seats.gd`
- Modify: `client/tests/run_all.gd`

- [ ] **Step 1: Write `test_seats.gd`**

```gdscript
extends RefCounted
class_name TestSeats

const Seats3D := preload("res://components/seats_3d.gd")


static func run() -> int:
	print("-- test_seats --")
	var fails := 0
	fails += _test_opponents_placed_in_order_skipping_self()
	fails += _test_turn_seat_highlighted()
	fails += _test_local_hand_populates_seat_0()
	fails += _test_folded_opponent_shows_badge()
	return fails


static func _make() -> Node3D:
	var s = Seats3D.new()
	s._ready()
	return s


static func _players(count: int) -> Array:
	var arr := []
	for i in range(count):
		arr.append({
			"player_id": "p%d" % i,
			"name": "P%d" % i,
			"chips": 100,
			"bet_this_round": 0,
			"folded": false,
			"all_in": false,
			"class_name": "Soldier",
		})
	return arr


static func _test_opponents_placed_in_order_skipping_self() -> int:
	var s := _make()
	s.update({"players": _players(3), "current_player_id": null}, "p1")
	# Seat 0 = local (p1). Opponents: p0 at seat 1, p2 at seat 2.
	var fails := 0
	if not TestHelpers.assert_eq(s.opponent_player_id_at_seat(1), "p0", "seat 1 is p0"): fails += 1
	if not TestHelpers.assert_eq(s.opponent_player_id_at_seat(2), "p2", "seat 2 is p2"): fails += 1
	if not TestHelpers.assert_eq(s.opponent_player_id_at_seat(3), "", "seat 3 empty"): fails += 1
	s.free()
	return fails


static func _test_turn_seat_highlighted() -> int:
	var s := _make()
	s.update({"players": _players(3), "current_player_id": "p2"}, "p1")
	var fails := 0
	# p2 is at seat 2
	if not TestHelpers.assert_true(s.seat_is_turn_highlighted(2), "seat 2 highlighted"): fails += 1
	if not TestHelpers.assert_false(s.seat_is_turn_highlighted(1), "seat 1 not highlighted"): fails += 1
	s.free()
	return fails


static func _test_local_hand_populates_seat_0() -> int:
	var s := _make()
	var hand := {
		"weapon": {"name": "Longsword", "damage_types": [[3, "slashing"]]},
		"item": {"name": "Shield", "bonus_value": 1, "damage_type": "blunt"},
		"infusion": {"name": "Holy", "infusion_type": "Holy"},
		"fourth_card": {"name": "Potion", "bonus_value": 1, "damage_type": "blunt"},
	}
	var class_card := {"name": "Paladin", "damage_formulas": [["2+LV", "slashing"]]}
	s.set_local_hand(hand, class_card)
	var fails := 0
	if not TestHelpers.assert_eq(s.local_card_name(0), "Paladin", "slot 0 is class"): fails += 1
	if not TestHelpers.assert_eq(s.local_card_name(1), "Longsword", "slot 1 is weapon"): fails += 1
	if not TestHelpers.assert_eq(s.local_card_name(2), "Shield", "slot 2 is item"): fails += 1
	if not TestHelpers.assert_eq(s.local_card_name(3), "Holy", "slot 3 is infusion"): fails += 1
	if not TestHelpers.assert_eq(s.local_card_name(4), "Potion", "slot 4 is 4th"): fails += 1
	s.free()
	return fails


static func _test_folded_opponent_shows_badge() -> int:
	var s := _make()
	var ps := _players(3)
	ps[0]["folded"] = true
	s.update({"players": ps, "current_player_id": "p2"}, "p1")
	var fails := 0
	if not TestHelpers.assert_eq(s.opponent_badge_text_at_seat(1), "FOLDED", "p0 at seat 1 shows FOLDED"): fails += 1
	s.free()
	return fails
```

- [ ] **Step 2: Register suite**

Add `TestSeats.run()` to `_initialize()` in `client/tests/run_all.gd`:

```gdscript
	fails += TestCardFace.run()
	fails += TestBoard.run()
	fails += TestSeats.run()
```

- [ ] **Step 3: Run to confirm FAIL**

Run: `cd client && godot --headless --script res://tests/run_all.gd`
Expected: fails (seats_3d doesn't exist).

- [ ] **Step 4: Implement `seats_3d.gd`**

```gdscript
extends Node3D


const Card3D := preload("res://components/card_3d.gd")
const Nameplate3D := preload("res://components/nameplate_3d.gd")

const SEAT_COUNT := 8
const TABLE_RADIUS_X := 2.4
const TABLE_RADIUS_Z := 1.4
const LOCAL_SEAT_Z := 1.3   # closer to camera
const SEAT_HEIGHT := 0.1

# Card slot offsets within a seat: [class, weapon, item, infusion, fourth_card]
const LOCAL_CARD_OFFSETS := [
	Vector3(-1.0, 0.02, 0.0),
	Vector3(-0.5, 0.02, 0.0),
	Vector3( 0.0, 0.02, 0.0),
	Vector3( 0.5, 0.02, 0.0),
	Vector3( 1.0, 0.02, 0.0),
]

var _seats: Array = []  # seat Node3Ds
var _nameplates: Array = []  # index 1..7 populated; index 0 stays null
var _local_cards: Array = []  # 5 Card3D for seat 0
var _opponent_pids: Dictionary = {}  # seat_index → player_id ("" when empty)
var _turn_seat_index: int = -1
var _opponent_badges: Dictionary = {}  # seat_index → badge text ("" when none)


func _ready() -> void:
	_seats.resize(SEAT_COUNT)
	_nameplates.resize(SEAT_COUNT)
	for i in range(SEAT_COUNT):
		var seat := Node3D.new()
		seat.position = _seat_position(i)
		add_child(seat)
		_seats[i] = seat
		if i == 0:
			# Build 5 local card slots, start face-down
			for slot in range(5):
				var c = Card3D.new()
				c.position = LOCAL_CARD_OFFSETS[slot]
				c.rotation_degrees = Vector3(-90, 0, 0)
				seat.add_child(c)
				c._ready()
				_local_cards.append(c)
		else:
			var np = Nameplate3D.new()
			seat.add_child(np)
			np._ready()
			_nameplates[i] = np
		_opponent_pids[i] = ""
		_opponent_badges[i] = ""


func _seat_position(i: int) -> Vector3:
	if i == 0:
		return Vector3(0, SEAT_HEIGHT, LOCAL_SEAT_Z)
	# Seats 1..7 fan across the far arc (negative z).
	var count := SEAT_COUNT - 1  # 7 opponent seats
	var t := float(i - 1) / float(count - 1) if count > 1 else 0.5
	var angle := lerp(PI * 0.85, PI * 0.15, t)  # arc from left-back to right-back
	var x := cos(angle) * TABLE_RADIUS_X
	var z := -abs(sin(angle)) * TABLE_RADIUS_Z - 0.4
	return Vector3(x, SEAT_HEIGHT, z)


func update(snap: Dictionary, my_player_id: String) -> void:
	var players = snap.get("players", []) as Array
	var current_pid = snap.get("current_player_id")
	# Clear prior
	_turn_seat_index = -1
	for i in range(1, SEAT_COUNT):
		_opponent_pids[i] = ""
		_opponent_badges[i] = ""
		_nameplates[i].visible = false

	var opponents := []
	for entry in players:
		if str(entry.get("player_id", "")) != my_player_id:
			opponents.append(entry)

	for i in range(opponents.size()):
		var seat_i := i + 1
		if seat_i >= SEAT_COUNT:
			break
		var entry = opponents[i]
		var pid := str(entry.get("player_id", ""))
		_opponent_pids[seat_i] = pid
		var is_turn := current_pid != null and str(current_pid) == pid
		if is_turn:
			_turn_seat_index = seat_i
		_nameplates[seat_i].visible = true
		_nameplates[seat_i].update(entry, is_turn)
		# Track badge text for tests (we don't introspect Label3D color directly)
		if bool(entry.get("folded", false)):
			_opponent_badges[seat_i] = "FOLDED"
		elif bool(entry.get("all_in", false)):
			_opponent_badges[seat_i] = "ALL-IN"


func set_local_hand(hand: Dictionary, class_card: Dictionary) -> void:
	_local_cards[0].set_card(class_card, "class")
	_local_cards[1].set_card(hand.get("weapon", {}), "weapon")
	_local_cards[2].set_card(hand.get("item", {}), "item")
	_local_cards[3].set_card(hand.get("infusion", {}), "infusion")
	var fourth = hand.get("fourth_card", {})
	# Type inferred from shape: if it has "infusion_type" it's an infusion, else item
	var fourth_type := "infusion" if fourth.has("infusion_type") else "item"
	_local_cards[4].set_card(fourth, fourth_type)


func clear_local_hand() -> void:
	for c in _local_cards:
		c.set_face_down()


# --- Introspection for tests ---

func opponent_player_id_at_seat(i: int) -> String:
	return str(_opponent_pids.get(i, ""))


func seat_is_turn_highlighted(i: int) -> bool:
	return _turn_seat_index == i


func local_card_name(slot: int) -> String:
	return str(_local_cards[slot].current_card().get("name", ""))


func opponent_badge_text_at_seat(i: int) -> String:
	return str(_opponent_badges.get(i, ""))
```

- [ ] **Step 5: Run to confirm PASS**

Run: `cd client && godot --headless --script res://tests/run_all.gd`
Expected: all suites pass.

- [ ] **Step 6: Commit**

```bash
git add client/components/seats_3d.gd client/tests/test_seats.gd client/tests/run_all.gd
git commit -m "feat(client): add seats_3d with nameplates, local hand, and turn highlight"
```

---

## Phase 6 — HUD

### Task 12: `hud.gd` — CanvasLayer with TopStrip, BetBar, YourChips, Chat

**Files:**
- Create: `client/components/hud.gd`
- Create: `client/tests/test_hud.gd`
- Modify: `client/tests/run_all.gd`

- [ ] **Step 1: Write `test_hud.gd`**

```gdscript
extends RefCounted
class_name TestHud

const Hud := preload("res://components/hud.gd")


static func run() -> int:
	print("-- test_hud --")
	var fails := 0
	fails += _test_pot_and_phase()
	fails += _test_your_turn_vs_waiting()
	fails += _test_check_vs_call_label()
	fails += _test_raise_bounds()
	fails += _test_resistance_banner_visibility()
	fails += _test_all_in_hidden_when_cant_afford_extra()
	fails += _test_bet_bar_hidden_when_folded()
	return fails


static func _snap(overrides := {}) -> Dictionary:
	var base := {
		"room_code": "ABCD",
		"phase": "round_1",
		"players": [
			{"player_id": "me", "name": "Me", "chips": 80, "bet_this_round": 0, "folded": false, "all_in": false, "class_name": "Soldier"},
			{"player_id": "op", "name": "Opp", "chips": 90, "bet_this_round": 10, "folded": false, "all_in": false, "class_name": "Mage"},
		],
		"current_player_id": "me",
		"current_bet": 0,
		"max_raise": 20,
		"pot": 20,
		"board": {"bounty": null, "terrain": null, "mods_revealed": []},
		"resistance_dropped": false,
		"showdown": null,
	}
	for k in overrides.keys():
		base[k] = overrides[k]
	return base


static func _make() -> Node:
	var h = Hud.new()
	h._ready()
	return h


static func _test_pot_and_phase() -> int:
	var h := _make()
	h.update(_snap(), "me")
	var fails := 0
	if not TestHelpers.assert_in("Pot: 20", h.top_strip_text(), "pot displayed"): fails += 1
	if not TestHelpers.assert_in("Bounty Mod 1", h.top_strip_text(), "phase label"): fails += 1
	if not TestHelpers.assert_in("ABCD", h.top_strip_text(), "room code"): fails += 1
	h.free()
	return fails


static func _test_your_turn_vs_waiting() -> int:
	var h := _make()
	h.update(_snap(), "me")
	var fails := 0
	if not TestHelpers.assert_true(h.bet_bar_interactive(), "your turn enables bar"): fails += 1
	if not TestHelpers.assert_in("YOUR TURN", h.top_strip_text(), "turn badge"): fails += 1
	h.update(_snap({"current_player_id": "op"}), "me")
	if not TestHelpers.assert_false(h.bet_bar_interactive(), "opp turn disables bar"): fails += 1
	if not TestHelpers.assert_in("Opp", h.top_strip_text(), "waiting name"): fails += 1
	h.free()
	return fails


static func _test_check_vs_call_label() -> int:
	var h := _make()
	# No pending bet → Check
	h.update(_snap({"current_bet": 0}), "me")
	var fails := 0
	if not TestHelpers.assert_eq(h.check_call_label(), "Check", "check when bet matches"): fails += 1
	# Pending 10 bet → Call 10cp
	var players := _snap()["players"]
	h.update(_snap({"current_bet": 10, "players": players}), "me")
	if not TestHelpers.assert_eq(h.check_call_label(), "Call 10cp", "call diff"): fails += 1
	h.free()
	return fails


static func _test_raise_bounds() -> int:
	var h := _make()
	h.update(_snap({"current_bet": 5, "max_raise": 15}), "me")
	var fails := 0
	if not TestHelpers.assert_eq(h.raise_min(), 6, "raise min = current_bet+1"): fails += 1
	if not TestHelpers.assert_eq(h.raise_max(), 15, "raise max = max_raise"): fails += 1
	h.free()
	return fails


static func _test_resistance_banner_visibility() -> int:
	var h := _make()
	h.update(_snap({"resistance_dropped": false}), "me")
	var fails := 0
	if not TestHelpers.assert_false(h.resistance_banner_visible(), "banner hidden"): fails += 1
	h.update(_snap({"resistance_dropped": true}), "me")
	if not TestHelpers.assert_true(h.resistance_banner_visible(), "banner visible"): fails += 1
	h.free()
	return fails


static func _test_all_in_hidden_when_cant_afford_extra() -> int:
	var h := _make()
	# Chips = 10, current_bet = 10 → all-in just calls → hide button
	var snap := _snap({"current_bet": 10})
	snap["players"][0]["chips"] = 10
	h.update(snap, "me")
	var fails := 0
	if not TestHelpers.assert_false(h.all_in_visible(), "all-in hidden when chips == bet"): fails += 1
	h.free()
	return fails


static func _test_bet_bar_hidden_when_folded() -> int:
	var h := _make()
	var snap := _snap()
	snap["players"][0]["folded"] = true
	h.update(snap, "me")
	var fails := 0
	if not TestHelpers.assert_false(h.bet_bar_visible(), "bar hidden when folded"): fails += 1
	h.free()
	return fails
```

- [ ] **Step 2: Register suite**

Add `TestHud.run()` to `_initialize()` in `client/tests/run_all.gd`:

```gdscript
	fails += TestCardFace.run()
	fails += TestBoard.run()
	fails += TestSeats.run()
	fails += TestHud.run()
```

- [ ] **Step 3: Run to confirm FAIL**

Run: `cd client && godot --headless --script res://tests/run_all.gd`
Expected: fails (hud.gd doesn't exist).

- [ ] **Step 4: Implement `hud.gd`**

```gdscript
extends CanvasLayer


signal bet_action_requested(action_type: String, amount)  # amount may be null
signal chat_message_sent(text: String)

const FONT_NORMAL := 20
const FONT_HEADER := 24

const PHASE_LABELS := {
	"lobby": "Lobby",
	"class_selection": "Class Selection",
	"round_1": "Bounty Mod 1",
	"round_2": "Bounty",
	"round_3": "Bounty Mod 2",
	"round_4": "Terrain",
	"round_5": "Bounty Mod 3",
	"showdown": "Showdown",
	"hand_end": "Hand Over",
}

# UI
var _top_strip_lbl: Label
var _resistance_banner: Panel
var _resistance_banner_lbl: Label
var _chips_lbl: Label
var _check_call_btn: Button
var _raise_btn: Button
var _fold_btn: Button
var _all_in_btn: Button
var _raise_slider: HSlider
var _raise_commit_btn: Button
var _raise_row: HBoxContainer
var _bet_bar: HBoxContainer

# Latest-state mirror for tests
var _top_strip_text: String = ""
var _check_call_label: String = "Check"
var _raise_min: int = 1
var _raise_max: int = 1
var _all_in_visible: bool = true
var _bet_bar_interactive: bool = false
var _bet_bar_visible: bool = true
var _resistance_banner_visible: bool = false


func _ready() -> void:
	_build_ui()


func _build_ui() -> void:
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)

	# Top strip
	var top := PanelContainer.new()
	top.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	top.offset_bottom = 44
	root.add_child(top)
	var top_row := HBoxContainer.new()
	top_row.add_theme_constant_override("separation", 24)
	top.add_child(top_row)
	_top_strip_lbl = Label.new()
	_top_strip_lbl.add_theme_font_size_override("font_size", FONT_NORMAL)
	top_row.add_child(_top_strip_lbl)

	# Resistance banner
	_resistance_banner = Panel.new()
	_resistance_banner.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	_resistance_banner.offset_top = 44
	_resistance_banner.offset_bottom = 74
	var res_sb := StyleBoxFlat.new()
	res_sb.bg_color = Color(0.60, 0.18, 0.18)
	_resistance_banner.add_theme_stylebox_override("panel", res_sb)
	_resistance_banner.visible = false
	root.add_child(_resistance_banner)
	_resistance_banner_lbl = Label.new()
	_resistance_banner_lbl.text = "⚠ 25% Resistance Dropped!"
	_resistance_banner_lbl.set_anchors_preset(Control.PRESET_FULL_RECT)
	_resistance_banner_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_resistance_banner_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_resistance_banner_lbl.add_theme_font_size_override("font_size", FONT_NORMAL)
	_resistance_banner.add_child(_resistance_banner_lbl)

	# Bottom-left chips panel
	_chips_lbl = Label.new()
	_chips_lbl.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	_chips_lbl.offset_left = 16
	_chips_lbl.offset_top = -96
	_chips_lbl.offset_bottom = -16
	_chips_lbl.offset_right = 240
	_chips_lbl.add_theme_font_size_override("font_size", FONT_NORMAL)
	root.add_child(_chips_lbl)

	# Bet bar, bottom-center
	_bet_bar = HBoxContainer.new()
	_bet_bar.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	_bet_bar.offset_top = -72
	_bet_bar.offset_bottom = -16
	_bet_bar.offset_left = -240
	_bet_bar.offset_right = 240
	_bet_bar.add_theme_constant_override("separation", 12)
	root.add_child(_bet_bar)

	_check_call_btn = Button.new()
	_check_call_btn.custom_minimum_size = Vector2(120, 48)
	_check_call_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_check_call_btn.pressed.connect(func(): _emit_check_or_call())
	_bet_bar.add_child(_check_call_btn)

	_raise_btn = Button.new()
	_raise_btn.text = "Raise"
	_raise_btn.custom_minimum_size = Vector2(96, 48)
	_raise_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_raise_btn.pressed.connect(func(): _raise_row.visible = not _raise_row.visible)
	_bet_bar.add_child(_raise_btn)

	_fold_btn = Button.new()
	_fold_btn.text = "Fold"
	_fold_btn.custom_minimum_size = Vector2(96, 48)
	_fold_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_fold_btn.pressed.connect(func(): bet_action_requested.emit("fold", null))
	_bet_bar.add_child(_fold_btn)

	_all_in_btn = Button.new()
	_all_in_btn.text = "All-In"
	_all_in_btn.custom_minimum_size = Vector2(96, 48)
	_all_in_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_all_in_btn.pressed.connect(func(): bet_action_requested.emit("all_in", null))
	_bet_bar.add_child(_all_in_btn)

	# Raise slider row — hidden by default, sits above bet bar
	_raise_row = HBoxContainer.new()
	_raise_row.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	_raise_row.offset_top = -132
	_raise_row.offset_bottom = -76
	_raise_row.offset_left = -240
	_raise_row.offset_right = 240
	_raise_row.add_theme_constant_override("separation", 12)
	_raise_row.visible = false
	root.add_child(_raise_row)

	_raise_slider = HSlider.new()
	_raise_slider.custom_minimum_size = Vector2(240, 48)
	_raise_slider.step = 1
	_raise_row.add_child(_raise_slider)

	_raise_commit_btn = Button.new()
	_raise_commit_btn.text = "Confirm Raise"
	_raise_commit_btn.custom_minimum_size = Vector2(140, 48)
	_raise_commit_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_raise_commit_btn.pressed.connect(func():
		bet_action_requested.emit("raise", int(_raise_slider.value))
		_raise_row.visible = false
	)
	_raise_row.add_child(_raise_commit_btn)


func update(snap: Dictionary, my_player_id: String) -> void:
	var me = _find_me(snap, my_player_id)
	var current_pid = snap.get("current_player_id")
	var is_my_turn := current_pid != null and str(current_pid) == my_player_id

	# Top strip
	var phase_label := str(PHASE_LABELS.get(str(snap.get("phase", "")), str(snap.get("phase", ""))))
	var turn_text := ""
	if is_my_turn:
		turn_text = "YOUR TURN"
	else:
		var waiting_name := ""
		for p in snap.get("players", []):
			if str(p.get("player_id", "")) == str(current_pid):
				waiting_name = str(p.get("name", ""))
				break
		turn_text = "Waiting for %s" % waiting_name if waiting_name != "" else ""
	_top_strip_text = "Room: %s    %s    Pot: %dcp    %s" % [
		str(snap.get("room_code", "")),
		phase_label,
		int(snap.get("pot", 0)),
		turn_text,
	]
	_top_strip_lbl.text = _top_strip_text

	# Resistance banner
	_resistance_banner_visible = bool(snap.get("resistance_dropped", false))
	_resistance_banner.visible = _resistance_banner_visible

	# Chips panel
	var chips := int(me.get("chips", 0)) if me else 0
	var my_bet := int(me.get("bet_this_round", 0)) if me else 0
	_chips_lbl.text = "Chips: %dcp\nBet: %dcp" % [chips, my_bet]

	# Bet bar visibility — hide entirely if folded or all-in
	var folded := bool(me.get("folded", false)) if me else false
	var all_in := bool(me.get("all_in", false)) if me else false
	_bet_bar_visible = not (folded or all_in)
	_bet_bar.visible = _bet_bar_visible
	_raise_row.visible = _raise_row.visible and _bet_bar_visible

	# Check/Call label
	var current_bet := int(snap.get("current_bet", 0))
	if current_bet == my_bet:
		_check_call_label = "Check"
	else:
		_check_call_label = "Call %dcp" % (current_bet - my_bet)
	_check_call_btn.text = _check_call_label

	# All-in visibility — hide if you'd only be calling
	_all_in_visible = chips > current_bet
	_all_in_btn.visible = _all_in_visible

	# Raise bounds
	_raise_min = current_bet + 1
	_raise_max = int(snap.get("max_raise", _raise_min))
	if _raise_max < _raise_min:
		_raise_max = _raise_min
	_raise_slider.min_value = _raise_min
	_raise_slider.max_value = _raise_max
	if _raise_slider.value < _raise_min:
		_raise_slider.value = _raise_min

	# Interactivity
	_bet_bar_interactive = is_my_turn and _bet_bar_visible
	_check_call_btn.disabled = not _bet_bar_interactive
	_raise_btn.disabled = not _bet_bar_interactive
	_fold_btn.disabled = not _bet_bar_interactive
	_all_in_btn.disabled = not _bet_bar_interactive
	_bet_bar.modulate = Color(1, 1, 1, 1.0 if _bet_bar_interactive else 0.3)


func _find_me(snap: Dictionary, my_player_id: String):
	for p in snap.get("players", []):
		if str(p.get("player_id", "")) == my_player_id:
			return p
	return null


func _emit_check_or_call() -> void:
	if _check_call_label == "Check":
		bet_action_requested.emit("check", null)
	else:
		bet_action_requested.emit("call", null)


# --- Test introspection ---

func top_strip_text() -> String:
	return _top_strip_text


func check_call_label() -> String:
	return _check_call_label


func raise_min() -> int:
	return _raise_min


func raise_max() -> int:
	return _raise_max


func all_in_visible() -> bool:
	return _all_in_visible


func bet_bar_interactive() -> bool:
	return _bet_bar_interactive


func bet_bar_visible() -> bool:
	return _bet_bar_visible


func resistance_banner_visible() -> bool:
	return _resistance_banner_visible
```

- [ ] **Step 5: Run to confirm PASS**

Run: `cd client && godot --headless --script res://tests/run_all.gd`
Expected: all suites pass.

- [ ] **Step 6: Add chat toggle + drawer to the HUD**

The HUD needs a collapsible chat drawer (spec decision #9): toggle button bottom-right, drawer slides up when open, unread dot when a chat arrives while the drawer is closed.

At the top of `client/components/hud.gd`, alongside the other UI fields, add:

```gdscript
var _chat_toggle_btn: Button
var _chat_drawer: PanelContainer
var _chat_log: VBoxContainer
var _chat_scroll: ScrollContainer
var _chat_unread_dot: ColorRect
var _chat_open: bool = false
var _chat_has_unread: bool = false
```

Extend `_build_ui()` — append this block to the end of the function:

```gdscript
	# Chat toggle + drawer (bottom-right)
	_chat_toggle_btn = Button.new()
	_chat_toggle_btn.text = "Chat ▲"
	_chat_toggle_btn.custom_minimum_size = Vector2(120, 48)
	_chat_toggle_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_chat_toggle_btn.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	_chat_toggle_btn.offset_left = -140
	_chat_toggle_btn.offset_right = -16
	_chat_toggle_btn.offset_top = -64
	_chat_toggle_btn.offset_bottom = -16
	_chat_toggle_btn.pressed.connect(_toggle_chat)
	root.add_child(_chat_toggle_btn)

	_chat_unread_dot = ColorRect.new()
	_chat_unread_dot.color = Color(0.95, 0.35, 0.35)
	_chat_unread_dot.custom_minimum_size = Vector2(12, 12)
	_chat_unread_dot.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_chat_unread_dot.position = Vector2(-14, 4)
	_chat_unread_dot.visible = false
	_chat_toggle_btn.add_child(_chat_unread_dot)

	_chat_drawer = PanelContainer.new()
	_chat_drawer.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	_chat_drawer.offset_left = -256
	_chat_drawer.offset_right = -16
	_chat_drawer.offset_top = -260
	_chat_drawer.offset_bottom = -72
	_chat_drawer.visible = false
	root.add_child(_chat_drawer)

	_chat_scroll = ScrollContainer.new()
	_chat_drawer.add_child(_chat_scroll)
	_chat_log = VBoxContainer.new()
	_chat_log.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_chat_log.add_theme_constant_override("separation", 4)
	_chat_scroll.add_child(_chat_log)
```

Add these methods at the bottom of `hud.gd`:

```gdscript
func add_chat_message(from: String, text: String) -> void:
	var lbl := Label.new()
	lbl.text = "%s: %s" % [from, text]
	lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	lbl.add_theme_font_size_override("font_size", 16)
	_chat_log.add_child(lbl)
	_scroll_chat_to_bottom()
	if not _chat_open:
		_chat_has_unread = true
		_chat_unread_dot.visible = true


func _toggle_chat() -> void:
	_chat_open = not _chat_open
	_chat_drawer.visible = _chat_open
	_chat_toggle_btn.text = "Chat ▼" if _chat_open else "Chat ▲"
	if _chat_open:
		_chat_has_unread = false
		_chat_unread_dot.visible = false


func _scroll_chat_to_bottom() -> void:
	await get_tree().process_frame
	if is_instance_valid(_chat_scroll):
		_chat_scroll.scroll_vertical = int(_chat_scroll.get_v_scroll_bar().max_value)


# --- Test introspection (chat) ---

func chat_unread_dot_visible() -> bool:
	return _chat_has_unread


func chat_drawer_open() -> bool:
	return _chat_open
```

- [ ] **Step 7: Add a chat-unread test**

Append to `client/tests/test_hud.gd` the following suite method call inside `run()` before `return fails`:

```gdscript
	fails += _test_chat_unread_dot()
```

And the method itself:

```gdscript
static func _test_chat_unread_dot() -> int:
	var h := _make()
	h.update(_snap(), "me")
	var fails := 0
	# Chat arrives while drawer closed → dot visible
	h.add_chat_message("Opp", "gl hf")
	if not TestHelpers.assert_true(h.chat_unread_dot_visible(), "unread dot after closed-chat"): fails += 1
	# Opening clears the dot
	h._toggle_chat()
	if not TestHelpers.assert_false(h.chat_unread_dot_visible(), "unread cleared on open"): fails += 1
	if not TestHelpers.assert_true(h.chat_drawer_open(), "drawer open after toggle"): fails += 1
	h.free()
	return fails
```

`_scroll_chat_to_bottom` awaits `get_tree().process_frame` — in orphan tests there's no tree. This will noop the scroll line; the test only checks `_chat_has_unread` and `_chat_open` which are set synchronously. If the `await` throws in headless testing, wrap `_scroll_chat_to_bottom` with `if get_tree() == null: return` at the top.

- [ ] **Step 8: Run to confirm PASS**

Run: `cd client && godot --headless --script res://tests/run_all.gd`
Expected: all suites pass (one more test in test_hud).

- [ ] **Step 9: Commit**

```bash
git add client/components/hud.gd client/tests/test_hud.gd client/tests/run_all.gd
git commit -m "feat(client): add HUD CanvasLayer (top strip, bet bar, chips, resistance banner, chat drawer)"
```

---

## Phase 7 — Overlays

### Task 13: `class_reveal.gd` — class + 4 hand cards modal

Centered panel. Emits `dismissed` signal on button press.

**Files:**
- Create: `client/overlays/class_reveal.gd`

- [ ] **Step 1: Implement `class_reveal.gd`**

```gdscript
extends Control


signal dismissed

const FONT_TITLE := 28
const FONT_BUTTON := 22
const CardFace := preload("res://components/card_face.gd")


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)


func show_reveal(priv: Dictionary) -> void:
	for c in get_children():
		if c.name != "_dim_bg":
			pass
	# Clear any previous content besides the dim layer
	for c in get_children().slice(1):
		c.queue_free()

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.offset_left = -360
	panel.offset_right = 360
	panel.offset_top = -260
	panel.offset_bottom = 260
	add_child(panel)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 16)
	panel.add_child(vbox)

	var title := Label.new()
	title.text = "YOUR HAND"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", FONT_TITLE)
	vbox.add_child(title)

	# Single row: class + 4 hand cards
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_child(row)

	var class_card: Dictionary = priv.get("class_card", {})
	var hand: Dictionary = priv.get("hand", {})
	_append_card(row, class_card, "class")
	_append_card(row, hand.get("weapon", {}), "weapon")
	_append_card(row, hand.get("item", {}), "item")
	_append_card(row, hand.get("infusion", {}), "infusion")
	var fourth = hand.get("fourth_card", {})
	var fourth_type := "infusion" if fourth.has("infusion_type") else "item"
	_append_card(row, fourth, fourth_type)

	var begin_btn := Button.new()
	begin_btn.text = "Begin Round 1 ▸"
	begin_btn.custom_minimum_size = Vector2(0, 56)
	begin_btn.add_theme_font_size_override("font_size", FONT_BUTTON)
	begin_btn.pressed.connect(func():
		dismissed.emit()
		queue_free()
	)
	vbox.add_child(begin_btn)


func _append_card(parent: Container, card: Dictionary, type_label: String) -> void:
	var face := CardFace.new()
	# Display size is half the render size; face renders at 256×358 but we fit 128×179 in the overlay
	face.custom_minimum_size = Vector2(128, 179)
	face.set_card(card, type_label)
	parent.add_child(face)
```

(No headless test; the overlay is a straight read of a dict and delegation to `card_face` which is already tested. Verified manually in Task 15.)

- [ ] **Step 2: Commit**

```bash
git add client/overlays/class_reveal.gd
git commit -m "feat(client): add class_reveal overlay (class + 4 cards + Begin button)"
```

---

### Task 14: `showdown.gd` — ranked rows with math helper

**Files:**
- Create: `client/overlays/showdown.gd`

- [ ] **Step 1: Implement `showdown.gd`**

```gdscript
extends Control


signal leave_game_requested

const FONT_TITLE := 26
const FONT_ROW := 18
const FONT_SMALL := 14
const CardFace := preload("res://components/card_face.gd")

const COLOR_WIN_BG := Color(0.32, 0.24, 0.06, 0.65)
const COLOR_WIN_BORDER := Color(0.95, 0.82, 0.30)
const COLOR_FOLDED_FG := Color(0.60, 0.60, 0.60)


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.7)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)


func show_showdown(snap: Dictionary) -> void:
	# Clear any previous content besides the dim layer
	for c in get_children().slice(1):
		c.queue_free()

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.offset_left = -500
	panel.offset_right = 500
	panel.offset_top = -320
	panel.offset_bottom = 320
	add_child(panel)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 10)
	panel.add_child(vbox)

	# Title
	var sd: Dictionary = snap.get("showdown", {})
	var winners: Array = sd.get("winner_ids", []) as Array
	var players: Array = snap.get("players", []) as Array
	var title := Label.new()
	title.text = _title_text(winners, players)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", FONT_TITLE)
	vbox.add_child(title)

	# Board reference strip
	vbox.add_child(_build_board_row(snap))

	# Rows per player
	for p in players:
		vbox.add_child(_build_row(p, sd))

	var leave_btn := Button.new()
	leave_btn.text = "Leave Game"
	leave_btn.custom_minimum_size = Vector2(0, 48)
	leave_btn.add_theme_font_size_override("font_size", FONT_ROW)
	leave_btn.pressed.connect(func(): leave_game_requested.emit())
	vbox.add_child(leave_btn)


func _title_text(winners: Array, players: Array) -> String:
	if winners.is_empty():
		return "Showdown"
	var names := []
	for p in players:
		if str(p.get("player_id", "")) in winners:
			names.append(str(p.get("name", "?")))
	if names.size() == 1:
		return "%s wins the hand" % names[0]
	return "%s split the pot" % ", ".join(names)


func _build_board_row(snap: Dictionary) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	var lbl := Label.new()
	lbl.text = "Board: "
	lbl.add_theme_font_size_override("font_size", FONT_SMALL)
	row.add_child(lbl)
	var board: Dictionary = snap.get("board", {})
	for m in board.get("mods_revealed", []):
		var mlbl := Label.new()
		mlbl.text = "Mod %+d %s" % [int(m.get("modifier", 0)), str(m.get("affected_type", ""))]
		mlbl.add_theme_font_size_override("font_size", FONT_SMALL)
		row.add_child(mlbl)
	if board.get("bounty"):
		var blbl := Label.new()
		blbl.text = "Bounty: %s" % str(board["bounty"].get("name", ""))
		blbl.add_theme_font_size_override("font_size", FONT_SMALL)
		row.add_child(blbl)
	if board.get("terrain"):
		var tlbl := Label.new()
		tlbl.text = "Terrain: %s" % str(board["terrain"].get("name", ""))
		tlbl.add_theme_font_size_override("font_size", FONT_SMALL)
		row.add_child(tlbl)
	if bool(snap.get("resistance_dropped", false)):
		var rlbl := Label.new()
		rlbl.text = "  (25% resistance dropped)"
		rlbl.add_theme_font_size_override("font_size", FONT_SMALL)
		rlbl.modulate = Color(1.0, 0.5, 0.3)
		row.add_child(rlbl)
	return row


func _build_row(player: Dictionary, sd: Dictionary) -> Control:
	var pid := str(player.get("player_id", ""))
	var is_winner := pid in (sd.get("winner_ids", []) as Array)
	var is_folded := bool(player.get("folded", false))

	var pc := PanelContainer.new()
	if is_winner:
		var sb := StyleBoxFlat.new()
		sb.bg_color = COLOR_WIN_BG
		sb.border_color = COLOR_WIN_BORDER
		sb.border_width_left = 4
		pc.add_theme_stylebox_override("panel", sb)

	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	pc.add_child(hbox)

	# Name + class column
	var name_box := VBoxContainer.new()
	name_box.custom_minimum_size = Vector2(140, 0)
	var name_lbl := Label.new()
	name_lbl.text = str(player.get("name", "?"))
	name_lbl.add_theme_font_size_override("font_size", FONT_ROW)
	name_box.add_child(name_lbl)
	var class_lbl := Label.new()
	var cls_name := str(player.get("class_name", "") if player.get("class_name") != null else "")
	class_lbl.text = "%s%s" % [cls_name, "  (folded)" if is_folded else ""]
	class_lbl.add_theme_font_size_override("font_size", FONT_SMALL)
	name_box.add_child(class_lbl)
	hbox.add_child(name_box)

	# 5 cards
	var cards_row := HBoxContainer.new()
	cards_row.add_theme_constant_override("separation", 4)
	hbox.add_child(cards_row)
	if is_folded:
		for i in range(5):
			_append_folded_placeholder(cards_row)
	else:
		var revealed: Dictionary = (sd.get("revealed_hands", {}) as Dictionary).get(pid, {})
		_append_face(cards_row, revealed.get("class_card", {}), "class")
		_append_face(cards_row, revealed.get("weapon", {}), "weapon")
		_append_face(cards_row, revealed.get("item", {}), "item")
		_append_face(cards_row, revealed.get("infusion", {}), "infusion")
		var fourth = revealed.get("fourth_card", {})
		var fourth_type := "infusion" if fourth.has("infusion_type") else "item"
		_append_face(cards_row, fourth, fourth_type)

	# Damage + math helper
	var dmg_box := VBoxContainer.new()
	dmg_box.custom_minimum_size = Vector2(140, 0)
	var dmg_lbl := Label.new()
	var damages: Dictionary = sd.get("damages", {}) as Dictionary
	if is_folded or not damages.has(pid):
		dmg_lbl.text = "—"
	else:
		dmg_lbl.text = "%d dmg" % int(damages[pid])
	dmg_lbl.add_theme_font_size_override("font_size", FONT_ROW)
	dmg_box.add_child(dmg_lbl)

	var math_lbl := Label.new()
	math_lbl.text = _format_math_helper(pid, sd)
	math_lbl.add_theme_font_size_override("font_size", FONT_SMALL)
	math_lbl.modulate = Color(0.75, 0.75, 0.75)
	dmg_box.add_child(math_lbl)
	hbox.add_child(dmg_box)

	# Chips change
	var chips_lbl := Label.new()
	chips_lbl.custom_minimum_size = Vector2(100, 0)
	var won := int((sd.get("pot_distribution", {}) as Dictionary).get(pid, 0))
	chips_lbl.text = ("+%d cp" % won) if won > 0 else "—"
	chips_lbl.add_theme_font_size_override("font_size", FONT_ROW)
	hbox.add_child(chips_lbl)

	if is_folded:
		pc.modulate = Color(1, 1, 1, 0.5)

	return pc


func _append_face(parent: Container, card: Dictionary, type_label: String) -> void:
	var face := CardFace.new()
	face.custom_minimum_size = Vector2(80, 112)
	face.set_card(card, type_label)
	parent.add_child(face)


func _append_folded_placeholder(parent: Container) -> void:
	var rect := ColorRect.new()
	rect.color = Color(0.18, 0.18, 0.18)
	rect.custom_minimum_size = Vector2(80, 112)
	parent.add_child(rect)


func _format_math_helper(pid: String, sd: Dictionary) -> String:
	var bd: Dictionary = (sd.get("damage_breakdown", {}) as Dictionary).get(pid, {})
	if bd.is_empty():
		return ""
	var parts := []
	parts.append(str(int(bd.get("weapon", 0))))
	parts.append(str(int(bd.get("class", 0))))
	for v in bd.get("items", []):
		parts.append(str(int(v)))
	var mods := int(bd.get("mods_sum", 0))
	if mods != 0:
		parts.append("%+d" % mods)
	var base_str := " + ".join(parts)
	var mult = bd.get("infusion_mult", 1.0)
	var total := int(bd.get("total", 0))
	return "%s → %d × %s" % [base_str, total, str(mult)]
```

- [ ] **Step 2: Commit**

```bash
git add client/overlays/showdown.gd
git commit -m "feat(client): add showdown overlay with ranked rows and math helper"
```

---

## Phase 8 — Top-level game wiring

### Task 15: `game.gd` + `game.tscn` — orchestrate everything

The top-level game screen. Builds the 3D scene (camera, light, environment, table, board, seats), adds the HUD and overlays, and subscribes to `WsClient.message_received` to drive everything.

**Files:**
- Create: `client/scenes/game/game.tscn` — minimal Node3D scene that loads `game.gd`
- Create: `client/scenes/game/game.gd`

- [ ] **Step 1: Create `game.tscn`**

```gdscript
# Open Godot's editor → File → New Scene → Root Node Node3D.
# Attach client/scenes/game/game.gd to the root.
# Save as client/scenes/game/game.tscn.
```

If editing outside the editor, the minimal `.tscn` text:

```
[gd_scene load_steps=2 format=3 uid="uid://game_scene_root"]

[ext_resource type="Script" path="res://scenes/game/game.gd" id="1_root"]

[node name="Game" type="Node3D"]
script = ExtResource("1_root")
```

Save as `client/scenes/game/game.tscn`.

- [ ] **Step 2: Implement `game.gd`**

```gdscript
extends Node3D


signal left_game

const Board3D := preload("res://components/board_3d.gd")
const Seats3D := preload("res://components/seats_3d.gd")
const Hud := preload("res://components/hud.gd")
const ClassReveal := preload("res://overlays/class_reveal.gd")
const Showdown := preload("res://overlays/showdown.gd")

var _board: Node3D
var _seats: Node3D
var _hud: CanvasLayer
var _class_reveal: Control = null
var _showdown: Control = null

var _last_snap: Dictionary = {}
var _last_private: Dictionary = {}
var _hand_reveal_shown: bool = false
var _showdown_shown: bool = false

var _message_cb: Callable


func _ready() -> void:
	_build_3d_scene()
	_build_board_and_seats()
	_build_hud()

	_message_cb = func(data): _on_message(data)
	WsClient.message_received.connect(_message_cb)


func _exit_tree() -> void:
	if WsClient.message_received.is_connected(_message_cb):
		WsClient.message_received.disconnect(_message_cb)


func _build_3d_scene() -> void:
	# Camera
	var cam := Camera3D.new()
	cam.position = Vector3(0, 2.0, 3.6)
	cam.rotation_degrees = Vector3(-22, 0, 0)
	cam.current = true
	add_child(cam)

	# Light
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-50, 30, 0)
	light.light_energy = 1.0
	add_child(light)

	# Environment
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.06, 0.08, 0.14)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.30, 0.32, 0.40)
	e.ambient_light_energy = 0.4
	env.environment = e
	add_child(env)

	# Table
	var table := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = 3.0
	mesh.bottom_radius = 3.0
	mesh.height = 0.1
	mesh.radial_segments = 48
	table.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.16, 0.40, 0.20)
	mat.roughness = 0.9
	table.material_override = mat
	table.scale = Vector3(1.0, 1.0, 0.6)  # squash into ellipse
	table.position = Vector3(0, -0.05, 0)
	add_child(table)


func _build_board_and_seats() -> void:
	_board = Board3D.new()
	add_child(_board)
	_board._ready()
	_seats = Seats3D.new()
	add_child(_seats)
	_seats._ready()


func _build_hud() -> void:
	_hud = Hud.new()
	add_child(_hud)
	_hud._ready()
	_hud.bet_action_requested.connect(_on_bet_action_requested)


func _on_message(data) -> void:
	if typeof(data) != TYPE_DICTIONARY:
		return
	match data.get("event"):
		"game_state":
			_apply_state(data)
		"your_hand":
			_apply_private_hand(data)
		"chat":
			_hud.add_chat_message(str(data.get("from", "?")), str(data.get("text", "")))
		"error":
			# Future: toast. For now, push to log.
			push_warning("[game] server error: " + str(data.get("message", "")))


func _apply_state(snap: Dictionary) -> void:
	_last_snap = snap
	var my_pid: String = WsClient.my_player_id
	_board.update(snap.get("board", {}), bool(snap.get("resistance_dropped", false)))
	_seats.update(snap, my_pid)
	_hud.update(snap, my_pid)
	var sd = snap.get("showdown")
	if sd != null and not _showdown_shown:
		_show_showdown(snap)
		_showdown_shown = true


func _apply_private_hand(priv: Dictionary) -> void:
	_last_private = priv
	var hand: Dictionary = priv.get("hand", {})
	var class_card: Dictionary = priv.get("class_card", {})
	_seats.set_local_hand(hand, class_card)
	if not _hand_reveal_shown:
		_show_class_reveal(priv)
		_hand_reveal_shown = true


func _show_class_reveal(priv: Dictionary) -> void:
	_class_reveal = ClassReveal.new()
	# Overlays live on the HUD CanvasLayer so they render above 3D
	_hud.add_child(_class_reveal)
	_class_reveal._ready()
	_class_reveal.show_reveal(priv)
	_class_reveal.dismissed.connect(func():
		if _class_reveal and is_instance_valid(_class_reveal):
			_class_reveal.queue_free()
		_class_reveal = null
	)


func _show_showdown(snap: Dictionary) -> void:
	_showdown = Showdown.new()
	_hud.add_child(_showdown)
	_showdown._ready()
	_showdown.show_showdown(snap)
	_showdown.leave_game_requested.connect(func(): left_game.emit())


func _on_bet_action_requested(action_type: String, amount) -> void:
	var payload := {"action": "bet_action", "type": action_type}
	if amount != null:
		payload["amount"] = int(amount)
	WsClient.send_message(payload)
```

- [ ] **Step 3: Smoke-launch (optional without live server)**

Open Godot, press Play. You should see the name-entry screen → main_menu → lobby. Do not try to start a game yet (need the live server).

- [ ] **Step 4: Live two-client integration test (the milestone)**

This is the manual integration test from the spec. Run:

1. `cd scripts && python start_dev.py` — starts the relay + ngrok, patches `config.gd`.
2. Build the Godot client; run it on machine A → enter name → Create Room → note code.
3. Run the same binary on machine B → enter name → Join Room with that code.
4. Host clicks Start Game (from the lobby). **Note:** the current lobby may not yet have a Start button — if so, add one in a follow-up task or temporarily call `WsClient.send_message({"action": "start_game"})` from a debug console / keybind. (Not a blocker for the plan; see Task 16.)
5. Both clients should see: class/hand reveal overlay with their class + 4 cards → click "Begin Round 1 ▸" → 3D table visible with their 5 cards face-up on Seat 0, opponent nameplate across the table.
6. Play 5 rounds — bet bar should be interactive on your turn, dimmed when waiting.
7. Confirm board reveals step-by-step per round.
8. Confirm resistance banner appears at round 3 when rolled.
9. Reach showdown — overlay shows both hands, math, winner highlighted, pot awarded.
10. Click "Leave Game" — returns to main menu cleanly on both sides.

Expected: milestone passes. Bugs found here go into follow-up tasks.

- [ ] **Step 5: Commit**

```bash
git add client/scenes/game/game.tscn client/scenes/game/game.gd
git commit -m "feat(client): add game screen — 3D scene, HUD, overlays, snapshot routing"
```

---

### Task 16: Lobby Start Game button + map-doc updates

Small loose ends from the milestone test.

**Files:**
- Modify: `client/scenes/screens/lobby.gd` — add a Start Game button visible to the host (first in `initial_players`)
- Modify: `docs/map_directories/lobby_networking.md`
- Modify: `docs/map_directories/damage_calculator.md`
- Modify: `docs/map_directories/map.md`
- Modify: `CLAUDE.md` — update build state, key systems

- [ ] **Step 1: Add Start Game button to lobby**

In `client/scenes/screens/lobby.gd`, inside `_build_ui` — after the `leave_btn` is added — append:

```gdscript
	var start_btn := Button.new()
	start_btn.text = "Start Game"
	start_btn.custom_minimum_size = Vector2(140, 48)
	start_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	start_btn.pressed.connect(func(): WsClient.send_message({"action": "start_game"}))
	header.add_child(start_btn)
```

Every client sees the button; the server rejects non-host starts with an `error` event. For the vertical slice that's acceptable.

- [ ] **Step 2: Update map directory files**

Append to `docs/map_directories/lobby_networking.md` a new section listing:
- `name_set` now includes `player_id` (string).
- `game_state.showdown.damage_breakdown` field (per-player math parts).
- `game_state.showdown.revealed_hands` field (non-folded players' cards).

Append to `docs/map_directories/damage_calculator.md`:
- Public helper `calculate_damage_breakdown(hand, board) -> dict` with shape `{weapon, class, items[], mods_sum, infusion_mult, total}`.

Append to `docs/map_directories/map.md` under a "Client UI" section:
- `client/scenes/game/game.gd` — top-level game screen
- `client/components/board_3d.gd`, `seats_3d.gd`, `card_3d.gd`, `card_face.gd`, `nameplate_3d.gd`, `hud.gd`
- `client/overlays/class_reveal.gd`, `showdown.gd`
- `client/tests/run_all.gd` — headless test entrypoint

Also add a session log entry dated today.

- [ ] **Step 3: Update CLAUDE.md build state**

In `CLAUDE.md`, replace the "Next task" line under Current Build State and add a new "Godot game UI built" entry parallel to the existing system entries (reference `docs/map_directories/map.md` for the file list). Update the Key Systems table so "UI" moves from 🔲 Not built to ✅ Built for the game-in-progress scope.

- [ ] **Step 4: Run full test suite (one last time)**

Run: `cd server && pytest -v`
Run: `cd client && godot --headless --script res://tests/run_all.gd`
Expected: 264+ server tests pass, all Godot suites pass.

- [ ] **Step 5: Commit**

```bash
git add client/scenes/screens/lobby.gd docs/map_directories/*.md CLAUDE.md
git commit -m "docs: add Start Game button and map-doc updates for Godot UI milestone"
```

---

## Closing notes

- Every widget receives a snapshot/private-hand and is idempotent. If a snapshot arrives out of order, the next correct snapshot still restores state.
- Signal cleanup: every widget that connects to `WsClient.message_received` stores the `Callable` and disconnects in `_exit_tree`. `game.gd` follows this convention.
- Animations, opponent card-backs, game-over loops, and polish are all explicitly out of scope — do not bloat tasks with them.
- After the milestone passes: invoke `/wrapup` per `CLAUDE.md` to update the map directories and close the session cleanly.

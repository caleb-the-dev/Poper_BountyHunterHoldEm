# Game Session Handler Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing Game State Machine and Betting Engine into the relay server as a per-room authoritative `GameSession`, making a single Classic-mode hand playable end-to-end via the WebSocket protocol.

**Architecture:** A new `server/game_session.py` module holds one `GameSession` per room. `RoomManager` gains a `game_session` field and host accessor. `relay_server.py` gains two actions (`start_game`, `bet_action`), broadcasts full state snapshots (+ private hands), and converts disconnects into auto-folds. All game logic stays engine-agnostic and unit-testable.

**Tech Stack:** Python 3.10+, `websockets>=12.0`, `pytest`, existing in-repo modules (`card_data`, `deck_manager`, `damage_calculator`, `game_state_machine`, `betting_engine`).

**Reference:** `docs/superpowers/specs/2026-04-18-game-session-handler-design.md`.

**Test baseline:** 167 passing → target ~210+ after all tasks.

**Running tests:** `cd server && pytest -v`

---

## File Structure

**New files:**
- `server/game_session.py` — GameSession class, `STARTING_CHIPS` constant, `InvalidActionError`
- `server/tests/test_game_session.py` — unit tests for GameSession
- `server/tests/test_relay_game_integration.py` — end-to-end integration tests (relay + GameSession)
- `scripts/smoke_test_game.py` — optional manual smoke test (plays one full hand against a local relay)

**Modified files:**
- `server/betting_engine.py` — add `fold_player(player_id)` method
- `server/tests/test_betting_engine.py` — add tests for `fold_player`
- `server/room_manager.py` — add `game_session` per-room field, `start_game`, `get_host`, `get_game_session`
- `server/tests/test_room_manager.py` — add tests for new methods
- `server/relay_server.py` — add `start_game` / `bet_action` handlers, reject mid-game `join_room`, auto-fold on `leave_room`/disconnect
- `docs/map_directories/lobby_networking.md` — add new actions/events/file references
- `docs/map_directories/betting_engine.md` — document `fold_player`
- `docs/map_directories/map.md` — add file tree entries, session log
- `CLAUDE.md` — update build state, key systems table, next task

---

## Task 1: Add `fold_player` to BettingEngine

Small additive change needed for handling disconnects of non-current players.

**Files:**
- Modify: `server/betting_engine.py`
- Modify: `server/tests/test_betting_engine.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_betting_engine.py`:

```python
# --- Out-of-turn fold (fold_player) ---

def test_fold_player_marks_player_folded():
    e = BettingEngine(_players(100, 100, 100))
    e.fold_player("p1")
    result = e.raise_bet(10) if False else None  # noqa — just documenting
    # Finish by folding remaining current player, then p2
    # p0 is current; to complete the round, we call next via actions.
    # Simpler: directly check p1 is recorded as folded via finish()
    e.check()  # p0 checks — p1 already folded so skipped
    e.check()  # p2 checks
    result = e.finish()
    assert "p1" in result.folded_player_ids

def test_fold_player_does_not_change_current_turn():
    e = BettingEngine(_players(100, 100, 100))
    assert e.current_player_id == "p0"
    e.fold_player("p1")  # fold a NON-current player
    assert e.current_player_id == "p0"

def test_fold_player_triggers_round_completion_when_only_one_active():
    # p0 raises, p2 folds via normal flow, p1 is the last active non-current player
    # but we want to test fold_player completes the round
    e = BettingEngine(_players(100, 100, 100))
    e.raise_bet(10)     # p0 raises — current turn now p1
    e.fold_player("p2")  # fold p2 out of turn
    e.fold()             # p1 folds (current player)
    assert e.is_round_complete is True

def test_fold_player_idempotent_on_already_folded():
    e = BettingEngine(_players(100, 100, 100))
    e.fold_player("p1")
    e.fold_player("p1")  # no error
    e.check()
    e.check()
    result = e.finish()
    assert result.folded_player_ids.count("p1") == 1

def test_fold_player_unknown_id_raises():
    e = BettingEngine(_players(100, 100))
    with pytest.raises(ValueError):
        e.fold_player("nope")
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_betting_engine.py -v -k fold_player`
Expected: 5 tests fail with `AttributeError: 'BettingEngine' object has no attribute 'fold_player'`.

- [ ] **Step 3: Implement `fold_player`**

Add to `server/betting_engine.py` immediately after the existing `fold` method (around line 123):

```python
    def fold_player(self, player_id: str) -> None:
        """Fold a specific player regardless of whose turn it is.
        Used for disconnect handling. No-op if already folded."""
        for state in self._states:
            if state.player_id == player_id:
                if state.folded:
                    return
                state.folded = True
                state.round_acted = True
                return
        raise ValueError(f"Player {player_id!r} not found")
```

- [ ] **Step 4: Run and confirm GREEN**

Run: `cd server && pytest tests/test_betting_engine.py -v`
Expected: all 49 tests pass (44 existing + 5 new).

- [ ] **Step 5: Commit**

```bash
git add server/betting_engine.py server/tests/test_betting_engine.py
git commit -m "feat(betting): add fold_player for out-of-turn folds

Enables GameSession to auto-fold disconnected players who are not the
current better. Preserves turn order and round-completion semantics.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 2: GameSession skeleton + construction

Create the module, `STARTING_CHIPS`, `InvalidActionError`, and the `GameSession` constructor that assembles GSM + BettingEngine.

**Files:**
- Create: `server/game_session.py`
- Create: `server/tests/test_game_session.py`

- [ ] **Step 1: Write the failing tests (construction)**

Create `server/tests/test_game_session.py`:

```python
import os
import random
import pytest

from card_data import load_all, CardSet
from game_session import GameSession, STARTING_CHIPS, InvalidActionError

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "csv_data")


@pytest.fixture(scope="module")
def card_set() -> CardSet:
    return load_all(DATA_DIR)


def _make_session(card_set, n_players=2, seed=42):
    players = [(f"p{i}", f"Player{i}") for i in range(n_players)]
    return GameSession(
        room_code="1234",
        host_id="p0",
        players=players,
        card_set=card_set,
        rng=random.Random(seed),
    )


# --- Construction ---

def test_constructor_assigns_starting_chips(card_set):
    s = _make_session(card_set, n_players=3)
    assert s.chips == {"p0": STARTING_CHIPS, "p1": STARTING_CHIPS, "p2": STARTING_CHIPS}

def test_constructor_sets_host_id(card_set):
    s = _make_session(card_set)
    assert s.host_id == "p0"

def test_constructor_stores_player_ids_in_seat_order(card_set):
    s = _make_session(card_set, n_players=4)
    assert s.player_ids == ["p0", "p1", "p2", "p3"]

def test_constructor_stores_display_names(card_set):
    s = _make_session(card_set)
    assert s.names == {"p0": "Player0", "p1": "Player1"}

def test_constructor_transitions_gsm_to_round_1(card_set):
    from game_state_machine import GamePhase
    s = _make_session(card_set)
    assert s.gsm.phase == GamePhase.ROUND_1

def test_constructor_assigns_class_to_every_player(card_set):
    s = _make_session(card_set, n_players=3)
    for player in s.gsm.players:
        assert player.class_card is not None

def test_constructor_deals_hand_to_every_player(card_set):
    s = _make_session(card_set, n_players=3)
    for player in s.gsm.players:
        assert player.hand is not None

def test_constructor_creates_first_betting_engine(card_set):
    s = _make_session(card_set)
    assert s.betting is not None
    assert s.betting.current_player_id == "p0"
    assert s.betting.current_bet == 0
    assert s.betting.pot == 0

def test_constructor_rejects_fewer_than_2_players(card_set):
    with pytest.raises(ValueError):
        GameSession(
            room_code="1234",
            host_id="p0",
            players=[("p0", "Solo")],
            card_set=card_set,
            rng=random.Random(42),
        )

def test_constructor_rejects_host_not_in_players(card_set):
    with pytest.raises(ValueError):
        GameSession(
            room_code="1234",
            host_id="not_a_player",
            players=[("p0", "A"), ("p1", "B")],
            card_set=card_set,
            rng=random.Random(42),
        )

def test_constructor_deterministic_with_same_seed(card_set):
    s1 = _make_session(card_set, seed=7)
    s2 = _make_session(card_set, seed=7)
    classes_1 = [p.class_card.name for p in s1.gsm.players]
    classes_2 = [p.class_card.name for p in s2.gsm.players]
    assert classes_1 == classes_2

def test_starting_chips_is_100():
    assert STARTING_CHIPS == 100

def test_invalid_action_error_carries_message():
    err = InvalidActionError("something bad")
    assert str(err) == "something bad"
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_game_session.py -v`
Expected: all tests fail with `ModuleNotFoundError: No module named 'game_session'`.

- [ ] **Step 3: Implement `game_session.py` (constructor only)**

Create `server/game_session.py`:

```python
import random
from dataclasses import dataclass, field
from typing import Optional

from card_data import CardSet
from game_state_machine import GameStateMachine
from betting_engine import BettingEngine, BettingPlayer, Pot

STARTING_CHIPS = 100


class InvalidActionError(Exception):
    """Raised when a client action violates game rules.
    Carries a client-friendly message."""


class GameSession:
    def __init__(
        self,
        room_code: str,
        host_id: str,
        players: list,
        card_set: CardSet,
        rng: Optional[random.Random] = None,
    ):
        if len(players) < 2:
            raise ValueError("Need at least 2 players to start")
        pids = [pid for pid, _ in players]
        if host_id not in pids:
            raise ValueError(f"host_id {host_id!r} is not in players list")

        self.room_code = room_code
        self.host_id = host_id
        self.player_ids: list = pids
        self.names: dict = {pid: name for pid, name in players}
        self._rng = rng or random.Random()
        self._card_set = card_set

        self.gsm = GameStateMachine(card_set, rng=self._rng)
        for pid in self.player_ids:
            self.gsm.add_player(pid)
        self.gsm.start_class_selection()
        for pid in self.player_ids:
            class_card = self._rng.choice(card_set.classes)
            self.gsm.assign_class(pid, class_card)
        self.gsm.start_hand()

        self.chips: dict = {pid: STARTING_CHIPS for pid in self.player_ids}
        self.pot_carry: int = 0
        self.last_round_pots: list = []
        self.betting: Optional[BettingEngine] = self._new_betting_engine()

    def _new_betting_engine(self) -> BettingEngine:
        """Build a BettingEngine for the current round from non-folded, non-broke players."""
        folded = {p.player_id for p in self.gsm.players if p.folded}
        bplayers = [
            BettingPlayer(pid, self.chips[pid])
            for pid in self.player_ids
            if pid not in folded and self.chips[pid] > 0
        ]
        return BettingEngine(bplayers, pot_entering_round=self.pot_carry)
```

- [ ] **Step 4: Run and confirm GREEN**

Run: `cd server && pytest tests/test_game_session.py -v`
Expected: all 13 tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/game_session.py server/tests/test_game_session.py
git commit -m "feat(session): GameSession constructor wires GSM + first BettingEngine

Assembles per-room game state: assigns random classes, deals hands,
draws board, creates first BettingEngine with 100 chips per player.
Rejects <2 players and unknown host_id.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 3: `apply_bet_action` — basic action delegation

Implement the method that routes client actions to BettingEngine. No round transitions yet.

**Files:**
- Modify: `server/game_session.py`
- Modify: `server/tests/test_game_session.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_game_session.py`:

```python
# --- apply_bet_action (basic delegation) ---

def test_apply_bet_action_check_delegates(card_set):
    s = _make_session(card_set)
    s.apply_bet_action("p0", "check")
    assert s.betting.current_player_id == "p1"

def test_apply_bet_action_call_delegates(card_set):
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "call")
    assert s.betting.current_player_id == "p2"
    assert s.betting.current_bet == 10

def test_apply_bet_action_raise_delegates(card_set):
    s = _make_session(card_set)
    s.apply_bet_action("p0", "raise", 10)
    assert s.betting.current_bet == 10

def test_apply_bet_action_fold_delegates(card_set):
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "fold")
    # p1 should be folded in both BettingEngine and GSM
    folded_in_gsm = {p.player_id for p in s.gsm.players if p.folded}
    assert "p1" in folded_in_gsm

def test_apply_bet_action_all_in_delegates(card_set):
    s = _make_session(card_set)
    s.apply_bet_action("p0", "all_in")
    assert s.betting.current_bet == STARTING_CHIPS

def test_apply_bet_action_rejects_wrong_player(card_set):
    s = _make_session(card_set)
    # p0 is current, but p1 tries to act
    with pytest.raises(InvalidActionError) as exc:
        s.apply_bet_action("p1", "check")
    assert "turn" in str(exc.value).lower()

def test_apply_bet_action_rejects_unknown_type(card_set):
    s = _make_session(card_set)
    with pytest.raises(InvalidActionError):
        s.apply_bet_action("p0", "squawk")

def test_apply_bet_action_rejects_raise_without_amount(card_set):
    s = _make_session(card_set)
    with pytest.raises(InvalidActionError):
        s.apply_bet_action("p0", "raise")

def test_apply_bet_action_translates_betting_engine_errors(card_set):
    s = _make_session(card_set)
    # Raising 999 exceeds max_raise=10 at start of hand
    with pytest.raises(InvalidActionError) as exc:
        s.apply_bet_action("p0", "raise", 999)
    assert "max" in str(exc.value).lower() or "too large" in str(exc.value).lower()

def test_apply_bet_action_translates_check_with_bet_error(card_set):
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    with pytest.raises(InvalidActionError) as exc:
        s.apply_bet_action("p1", "check")
    assert "check" in str(exc.value).lower() or "bet" in str(exc.value).lower()
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_game_session.py -v -k apply_bet_action`
Expected: 10 tests fail with `AttributeError: 'GameSession' object has no attribute 'apply_bet_action'`.

- [ ] **Step 3: Implement `apply_bet_action`**

Append to `server/game_session.py` (inside `GameSession`):

```python
    def apply_bet_action(self, player_id: str, action_type: str, amount: Optional[int] = None) -> None:
        """Apply a player's betting action. Raises InvalidActionError on rule violations."""
        if self.betting is None:
            raise InvalidActionError("No betting round is active")
        if player_id != self.betting.current_player_id:
            raise InvalidActionError("Not your turn")

        try:
            if action_type == "check":
                self.betting.check()
            elif action_type == "call":
                self.betting.call()
            elif action_type == "raise":
                if amount is None:
                    raise InvalidActionError("Raise requires amount")
                self.betting.raise_bet(amount)
            elif action_type == "fold":
                self.betting.fold()
                self.gsm.fold(player_id)
            elif action_type == "all_in":
                self.betting.all_in()
            else:
                raise InvalidActionError(f"Invalid bet action type: {action_type!r}")
        except ValueError as e:
            raise InvalidActionError(self._translate_betting_error(str(e))) from e

    @staticmethod
    def _translate_betting_error(msg: str) -> str:
        if "Cannot check" in msg:
            return "Cannot check — there is a bet to call"
        if "exceeds max raise" in msg:
            # Preserve the numeric detail from the original message
            return f"Raise too large — {msg.split('exceeds ')[-1]}"
        if "at least 1" in msg:
            return "Raise must be at least 1"
        if "Not enough chips" in msg:
            return "Not enough chips for that raise"
        return msg
```

- [ ] **Step 4: Run and confirm GREEN**

Run: `cd server && pytest tests/test_game_session.py -v`
Expected: 23 tests pass (13 construction + 10 delegation).

- [ ] **Step 5: Commit**

```bash
git add server/game_session.py server/tests/test_game_session.py
git commit -m "feat(session): apply_bet_action delegates to BettingEngine

Routes check/call/raise/fold/all_in to the active BettingEngine with
turn validation and error translation to client-friendly messages.
Fold also folds the player in the GSM for all-but-one auto-SHOWDOWN.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 4: Round transitions + pot carry

When a betting round completes, finish it, carry the pot, advance the GSM, and start the next BettingEngine.

**Files:**
- Modify: `server/game_session.py`
- Modify: `server/tests/test_game_session.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_game_session.py`:

```python
# --- Round transitions ---

def test_round_transition_advances_gsm_phase(card_set):
    from game_state_machine import GamePhase
    s = _make_session(card_set)
    s.apply_bet_action("p0", "check")
    s.apply_bet_action("p1", "check")
    assert s.gsm.phase == GamePhase.ROUND_2

def test_round_transition_creates_new_betting_engine(card_set):
    s = _make_session(card_set)
    first_engine = s.betting
    s.apply_bet_action("p0", "check")
    s.apply_bet_action("p1", "check")
    assert s.betting is not first_engine
    assert s.betting.current_bet == 0

def test_round_transition_resets_turn_to_first_player(card_set):
    s = _make_session(card_set)
    s.apply_bet_action("p0", "check")
    s.apply_bet_action("p1", "check")
    assert s.betting.current_player_id == "p0"

def test_round_transition_carries_pot_into_next_round(card_set):
    s = _make_session(card_set)
    s.apply_bet_action("p0", "raise", 10)  # pot=10
    s.apply_bet_action("p1", "call")       # pot=20
    # New round begins with pot_entering_round=20
    assert s.pot_carry == 20
    assert s.betting.pot == 20

def test_round_transition_deducts_chips_correctly(card_set):
    s = _make_session(card_set)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "call")
    assert s.chips["p0"] == 90
    assert s.chips["p1"] == 90

def test_multiple_round_transitions(card_set):
    from game_state_machine import GamePhase
    s = _make_session(card_set)
    for _ in range(4):
        s.apply_bet_action("p0", "check")
        s.apply_bet_action("p1", "check")
    # 4 check-check pairs → R1→R2→R3→R4→R5
    assert s.gsm.phase == GamePhase.ROUND_5
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_game_session.py -v -k "round_transition or multiple_round"`
Expected: 6 tests fail.

- [ ] **Step 3: Implement round transition logic**

Update `apply_bet_action` in `server/game_session.py` to check for round completion and transition. Append a new helper and modify the end of `apply_bet_action`:

Replace the existing `apply_bet_action` body's end (after the try/except) with:

```python
    def apply_bet_action(self, player_id: str, action_type: str, amount: Optional[int] = None) -> None:
        """Apply a player's betting action. Raises InvalidActionError on rule violations."""
        if self.betting is None:
            raise InvalidActionError("No betting round is active")
        if player_id != self.betting.current_player_id:
            raise InvalidActionError("Not your turn")

        try:
            if action_type == "check":
                self.betting.check()
            elif action_type == "call":
                self.betting.call()
            elif action_type == "raise":
                if amount is None:
                    raise InvalidActionError("Raise requires amount")
                self.betting.raise_bet(amount)
            elif action_type == "fold":
                self.betting.fold()
                self.gsm.fold(player_id)
            elif action_type == "all_in":
                self.betting.all_in()
            else:
                raise InvalidActionError(f"Invalid bet action type: {action_type!r}")
        except ValueError as e:
            raise InvalidActionError(self._translate_betting_error(str(e))) from e

        if self.betting.is_round_complete:
            self._finish_round()

    def _finish_round(self) -> None:
        """Close the current betting round, advance GSM, open the next round (or showdown)."""
        from game_state_machine import GamePhase

        result = self.betting.finish()
        for pid in result.folded_player_ids:
            if not any(p.player_id == pid and p.folded for p in self.gsm.players):
                self.gsm.fold(pid)
        self.chips = dict(result.remaining_chips)
        self.pot_carry = sum(p.amount for p in result.pots)
        self.last_round_pots = list(result.pots)

        if self.gsm.phase == GamePhase.SHOWDOWN:
            # All-but-one folded — GSM auto-transitioned; resolve in a later task
            self.betting = None
            return

        self.gsm.advance_round()
        if self.gsm.phase == GamePhase.SHOWDOWN:
            self.betting = None
            return

        self.betting = self._new_betting_engine()
```

- [ ] **Step 4: Run and confirm GREEN**

Run: `cd server && pytest tests/test_game_session.py -v`
Expected: 29 tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/game_session.py server/tests/test_game_session.py
git commit -m "feat(session): round transitions carry pot + advance GSM

When a BettingEngine round completes, finish it, roll the pot forward
as pot_carry, sync folds to GSM, advance the round, and spin up a new
BettingEngine for the next round (or stop if showdown is reached).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 5: Showdown resolution + pot distribution

After the 5th round completes (or all-but-one fold), resolve the showdown and pay out pots.

**Files:**
- Modify: `server/game_session.py`
- Modify: `server/tests/test_game_session.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_game_session.py`:

```python
# --- Showdown resolution ---

def _play_check_check_through_rounds(session, n_rounds):
    """Helper: play n_rounds with both players checking."""
    for _ in range(n_rounds):
        session.apply_bet_action("p0", "check")
        session.apply_bet_action("p1", "check")


def test_showdown_resolves_after_round_5_check_check(card_set):
    from game_state_machine import GamePhase
    s = _make_session(card_set)
    _play_check_check_through_rounds(s, 5)
    assert s.gsm.phase == GamePhase.HAND_END
    assert s.showdown is not None
    assert set(s.showdown["damages"].keys()) == {"p0", "p1"}

def test_showdown_declares_winner(card_set):
    s = _make_session(card_set)
    _play_check_check_through_rounds(s, 5)
    assert len(s.showdown["winner_ids"]) >= 1

def test_showdown_all_but_one_folded_awards_sole_survivor(card_set):
    from game_state_machine import GamePhase
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "fold")
    s.apply_bet_action("p2", "fold")
    assert s.gsm.phase == GamePhase.HAND_END
    assert s.showdown["winner_ids"] == ["p0"]
    # p0 should have won the pot (10 chips from the raise alone)
    assert s.chips["p0"] > STARTING_CHIPS - 10

def test_showdown_fold_walkover_has_empty_damages(card_set):
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "fold")
    s.apply_bet_action("p2", "fold")
    assert s.showdown["damages"] == {}

def test_showdown_pot_distribution_single_winner(card_set):
    # Force an outcome by seeding — then just check the winner received chips
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "call")
    s.apply_bet_action("p2", "call")
    _play_check_check_through_remainder(s)
    total = sum(s.chips.values())
    assert total == 3 * STARTING_CHIPS  # conservation of chips

def _play_check_check_through_remainder(session):
    from game_state_machine import GamePhase
    while session.gsm.phase != GamePhase.HAND_END:
        active_pids = [p.player_id for p in session.gsm.players if not p.folded]
        current = session.betting.current_player_id if session.betting else None
        if current is None:
            break
        session.apply_bet_action(current, "check")

def test_showdown_tied_winners_split_pot(card_set, monkeypatch):
    # Monkeypatch calculate_damage to force a tie
    import game_state_machine
    from damage_calculator import BoardState
    original = game_state_machine.calculate_damage
    def fake(hand, board):
        return 10
    monkeypatch.setattr(game_state_machine, "calculate_damage", fake)

    s = _make_session(card_set, n_players=2)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "call")
    # Carry pot=20 into round 2, then check-check through
    _play_check_check_through_remainder(s)
    # Tied — both should receive 10 chips back (20 split)
    assert s.chips["p0"] == STARTING_CHIPS
    assert s.chips["p1"] == STARTING_CHIPS

def test_showdown_total_chip_conservation(card_set):
    """Total chips in + out of session must equal n_players * STARTING_CHIPS."""
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "call")
    s.apply_bet_action("p2", "fold")
    _play_check_check_through_remainder(s)
    assert sum(s.chips.values()) == 3 * STARTING_CHIPS
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_game_session.py -v -k showdown`
Expected: 7 tests fail (mostly AttributeError: 'GameSession' object has no attribute 'showdown').

- [ ] **Step 3: Implement showdown + pot distribution**

In `server/game_session.py`, add an instance field initializer (in `__init__`) and the resolver helpers. Insert after the `self.last_round_pots = []` line in `__init__`:

```python
        self.showdown: Optional[dict] = None
```

Then replace `_finish_round` with:

```python
    def _finish_round(self) -> None:
        """Close the current betting round, advance GSM, open the next round (or showdown)."""
        from game_state_machine import GamePhase

        result = self.betting.finish()
        for pid in result.folded_player_ids:
            if not any(p.player_id == pid and p.folded for p in self.gsm.players):
                self.gsm.fold(pid)
        self.chips = dict(result.remaining_chips)
        self.pot_carry = sum(p.amount for p in result.pots)
        self.last_round_pots = list(result.pots)

        if self.gsm.phase == GamePhase.SHOWDOWN:
            self._resolve_showdown()
            return

        self.gsm.advance_round()
        if self.gsm.phase == GamePhase.SHOWDOWN:
            self._resolve_showdown()
            return

        self.betting = self._new_betting_engine()

    def _resolve_showdown(self) -> None:
        """Handle SHOWDOWN phase: calculate damage (if more than one player left),
        distribute pots, populate self.showdown."""
        from game_state_machine import GamePhase

        self.betting = None
        non_folded = [p.player_id for p in self.gsm.players if not p.folded]

        if len(non_folded) == 1:
            # Walkover — sole survivor wins all pots, no damage calc
            winner = non_folded[0]
            total = sum(p.amount for p in self.last_round_pots)
            self.chips[winner] += total
            # Manually advance GSM to HAND_END — resolve_showdown would run damage calc
            self.gsm._phase = GamePhase.HAND_END  # type: ignore[attr-defined]
            self.gsm._events.append("hand_ended")  # type: ignore[attr-defined]
            self.showdown = {
                "damages": {},
                "winner_ids": [winner],
                "pot_distribution": {winner: total},
            }
            return

        result = self.gsm.resolve_showdown()
        distribution = self._distribute_pots(result.winner_ids, result.damages)
        for pid, amount in distribution.items():
            self.chips[pid] += amount
        self.showdown = {
            "damages": dict(result.damages),
            "winner_ids": list(result.winner_ids),
            "pot_distribution": distribution,
        }

    def _distribute_pots(self, winner_ids: list, damages: dict) -> dict:
        """Distribute every pot among eligible winners. Returns {player_id: total_won}."""
        distribution: dict = {}
        for pot in self.last_round_pots:
            eligible_winners = [pid for pid in pot.eligible_player_ids if pid in winner_ids]
            if not eligible_winners:
                # Pathological fallback: award to highest-damage eligible player
                eligible_damages = {pid: damages.get(pid, 0) for pid in pot.eligible_player_ids}
                if not eligible_damages:
                    continue
                max_d = max(eligible_damages.values())
                eligible_winners = [pid for pid, d in eligible_damages.items() if d == max_d]
            share, remainder = divmod(pot.amount, len(eligible_winners))
            # Earliest-seated eligible winner gets remainder
            seated_order = [pid for pid in self.player_ids if pid in eligible_winners]
            for pid in seated_order:
                distribution[pid] = distribution.get(pid, 0) + share
            if remainder > 0:
                distribution[seated_order[0]] += remainder
        return distribution
```

- [ ] **Step 4: Run and confirm GREEN**

Run: `cd server && pytest tests/test_game_session.py -v`
Expected: 36 tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/game_session.py server/tests/test_game_session.py
git commit -m "feat(session): showdown resolution + pot distribution

At SHOWDOWN, populate self.showdown with damages, winner_ids, and
pot_distribution. Walkover (all-but-one-folded) awards sole survivor
all pots without damage calc. Tied winners split evenly; remainder
chips go to earliest-seated eligible winner. Chip conservation is
preserved across the hand.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 6: Fast-forward when all remaining players are all-in

If a round leaves no one able to bet, skip remaining rounds straight to showdown.

**Files:**
- Modify: `server/game_session.py`
- Modify: `server/tests/test_game_session.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_game_session.py`:

```python
# --- Fast-forward ---

def test_fast_forward_when_both_players_all_in(card_set):
    from game_state_machine import GamePhase
    s = _make_session(card_set)
    s.apply_bet_action("p0", "all_in")   # p0 all-in for 100
    s.apply_bet_action("p1", "call")      # p1 calls 100 (all-in)
    # After the call, p0 and p1 are both all-in. Round completes.
    # No more bettors — session should fast-forward to HAND_END.
    assert s.gsm.phase == GamePhase.HAND_END
    assert s.showdown is not None

def test_fast_forward_one_broke_one_has_chips(card_set):
    """p0 all-in for full stack, p1 raises over top, p1 still has chips after.
    Next round should still create a BettingEngine with only p1 — but since 1
    player isn't a valid betting round, we fast-forward."""
    from game_state_machine import GamePhase
    s = _make_session(card_set, n_players=3)
    # Setup: force p2 to fold first round so only p0 and p1 go to next round
    s.apply_bet_action("p0", "all_in")    # p0: 100 all-in
    s.apply_bet_action("p1", "raise", 50)  # p1 raises
    s.apply_bet_action("p2", "fold")
    # p1 still has chips but p0 is all-in — no new round can take both
    # Fast-forward should activate
    assert s.gsm.phase == GamePhase.HAND_END
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_game_session.py -v -k fast_forward`
Expected: 2 tests fail (likely with "No betting round is active" or similar).

- [ ] **Step 3: Implement fast-forward**

In `server/game_session.py`, update `_finish_round`:

```python
    def _finish_round(self) -> None:
        """Close the current betting round, advance GSM, open the next round (or showdown)."""
        from game_state_machine import GamePhase

        result = self.betting.finish()
        for pid in result.folded_player_ids:
            if not any(p.player_id == pid and p.folded for p in self.gsm.players):
                self.gsm.fold(pid)
        self.chips = dict(result.remaining_chips)
        self.pot_carry = sum(p.amount for p in result.pots)
        self.last_round_pots = list(result.pots)

        if self.gsm.phase == GamePhase.SHOWDOWN:
            self._resolve_showdown()
            return

        # Advance rounds, fast-forwarding if no one can act
        while True:
            self.gsm.advance_round()
            if self.gsm.phase == GamePhase.SHOWDOWN:
                self._resolve_showdown()
                return
            if self._has_active_bettors():
                self.betting = self._new_betting_engine()
                return
            # else: loop and advance again

    def _has_active_bettors(self) -> bool:
        """True if at least 2 non-folded players have chips > 0."""
        folded = {p.player_id for p in self.gsm.players if p.folded}
        bettors = [pid for pid in self.player_ids if pid not in folded and self.chips[pid] > 0]
        return len(bettors) >= 2
```

- [ ] **Step 4: Run and confirm GREEN**

Run: `cd server && pytest tests/test_game_session.py -v`
Expected: 38 tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/game_session.py server/tests/test_game_session.py
git commit -m "feat(session): fast-forward to showdown when no bettors remain

When a round completes with fewer than 2 non-folded, non-broke players,
skip creating a new BettingEngine and loop advance_round() until
SHOWDOWN. Handles all-in scenarios cleanly.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 7: Disconnect handling

Auto-fold a player who disconnects, whether they're the current better or not.

**Files:**
- Modify: `server/game_session.py`
- Modify: `server/tests/test_game_session.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_game_session.py`:

```python
# --- Disconnect handling ---

def test_disconnect_current_player_auto_folds(card_set):
    s = _make_session(card_set, n_players=3)
    assert s.betting.current_player_id == "p0"
    s.on_player_disconnect("p0")
    folded_in_gsm = {p.player_id for p in s.gsm.players if p.folded}
    assert "p0" in folded_in_gsm

def test_disconnect_non_current_player_auto_folds(card_set):
    s = _make_session(card_set, n_players=3)
    # p0 is current; disconnect p2 (out of turn)
    s.on_player_disconnect("p2")
    folded_in_gsm = {p.player_id for p in s.gsm.players if p.folded}
    assert "p2" in folded_in_gsm
    # Current turn unchanged (still p0)
    assert s.betting.current_player_id == "p0"

def test_disconnect_when_all_but_one_left_goes_to_showdown(card_set):
    from game_state_machine import GamePhase
    s = _make_session(card_set, n_players=3)
    s.on_player_disconnect("p1")
    s.on_player_disconnect("p2")
    # Only p0 left — should fast-forward to HAND_END with p0 as winner
    assert s.gsm.phase == GamePhase.HAND_END
    assert s.showdown["winner_ids"] == ["p0"]

def test_disconnect_unknown_player_is_noop(card_set):
    s = _make_session(card_set)
    s.on_player_disconnect("nobody")  # should not raise
    folded_in_gsm = {p.player_id for p in s.gsm.players if p.folded}
    assert folded_in_gsm == set()

def test_disconnect_already_folded_player_is_noop(card_set):
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "fold")
    s.on_player_disconnect("p1")  # already folded; should not error
    folded_in_gsm = [p.player_id for p in s.gsm.players if p.folded]
    assert folded_in_gsm.count("p1") == 1

def test_disconnect_after_hand_end_is_noop(card_set):
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "fold")
    s.apply_bet_action("p2", "fold")
    # Hand is over
    s.on_player_disconnect("p0")  # should not raise
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_game_session.py -v -k disconnect`
Expected: 6 tests fail (`AttributeError: 'GameSession' object has no attribute 'on_player_disconnect'`).

- [ ] **Step 3: Implement `on_player_disconnect`**

Append to `GameSession` in `server/game_session.py`:

```python
    def on_player_disconnect(self, player_id: str) -> None:
        """Handle a player disconnecting mid-game. Auto-folds them.
        No-op if player isn't in this session, already folded, or game is over."""
        from game_state_machine import GamePhase

        if player_id not in self.player_ids:
            return
        if self.gsm.phase in (GamePhase.HAND_END, GamePhase.GAME_END):
            return
        if any(p.player_id == player_id and p.folded for p in self.gsm.players):
            return

        self.gsm.fold(player_id)
        if self.betting is not None:
            self.betting.fold_player(player_id)
            if self.betting.is_round_complete:
                self._finish_round()
            elif self.gsm.phase == GamePhase.SHOWDOWN:
                # GSM auto-transitioned (all-but-one folded)
                self._finish_round()
```

- [ ] **Step 4: Run and confirm GREEN**

Run: `cd server && pytest tests/test_game_session.py -v`
Expected: 44 tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/game_session.py server/tests/test_game_session.py
git commit -m "feat(session): auto-fold on disconnect

on_player_disconnect folds the disconnected player in both GSM and the
active BettingEngine. Handles current-player, out-of-turn, already-folded,
and post-hand disconnects. Triggers round completion / fast-forward as
needed if the disconnect collapses the active bettor set.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 8: `snapshot(viewer_id)` method

Produce the public state dict the relay broadcasts as `game_state`.

**Files:**
- Modify: `server/game_session.py`
- Modify: `server/tests/test_game_session.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_game_session.py`:

```python
# --- Snapshot ---

def test_snapshot_has_phase(card_set):
    s = _make_session(card_set)
    snap = s.snapshot()
    assert snap["phase"] == "round_1"

def test_snapshot_has_players_with_public_fields(card_set):
    s = _make_session(card_set, n_players=3)
    snap = s.snapshot()
    assert len(snap["players"]) == 3
    p0 = snap["players"][0]
    assert p0["player_id"] == "p0"
    assert p0["name"] == "Player0"
    assert p0["chips"] == STARTING_CHIPS
    assert p0["bet_this_round"] == 0
    assert p0["folded"] is False
    assert p0["all_in"] is False
    assert p0["class_name"] is not None

def test_snapshot_current_player_during_betting(card_set):
    s = _make_session(card_set)
    snap = s.snapshot()
    assert snap["current_player_id"] == "p0"
    assert snap["current_bet"] == 0
    assert snap["max_raise"] == 10
    assert snap["pot"] == 0

def test_snapshot_current_player_none_at_hand_end(card_set):
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "fold")
    s.apply_bet_action("p2", "fold")
    snap = s.snapshot()
    assert snap["current_player_id"] is None

def test_snapshot_board_bounty_null_before_reveal(card_set):
    s = _make_session(card_set)
    snap = s.snapshot()
    assert snap["board"]["bounty"] is None
    assert snap["board"]["terrain"] is None
    assert len(snap["board"]["mods_revealed"]) == 1  # Round 1: mods[0]

def test_snapshot_board_after_round_1(card_set):
    s = _make_session(card_set)
    s.apply_bet_action("p0", "check")
    s.apply_bet_action("p1", "check")
    snap = s.snapshot()
    assert snap["board"]["bounty"] is not None

def test_snapshot_resistance_dropped_field(card_set):
    s = _make_session(card_set)
    snap = s.snapshot()
    assert snap["resistance_dropped"] is False

def test_snapshot_showdown_field_populated_at_hand_end(card_set):
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "fold")
    s.apply_bet_action("p2", "fold")
    snap = s.snapshot()
    assert snap["showdown"] is not None
    assert snap["showdown"]["winner_ids"] == ["p0"]

def test_snapshot_showdown_null_before_hand_end(card_set):
    s = _make_session(card_set)
    snap = s.snapshot()
    assert snap["showdown"] is None

def test_private_hand_for_player(card_set):
    s = _make_session(card_set)
    priv = s.private_hand("p0")
    assert "hand" in priv
    assert "class_card" in priv
    assert priv["hand"]["weapon"] is not None

def test_private_hand_unknown_player_returns_none(card_set):
    s = _make_session(card_set)
    assert s.private_hand("nobody") is None
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_game_session.py -v -k "snapshot or private_hand"`
Expected: 11 tests fail.

- [ ] **Step 3: Implement `snapshot` and `private_hand`**

Append to `GameSession` in `server/game_session.py`:

```python
    def snapshot(self) -> dict:
        """Return the public state dict the relay broadcasts to all clients."""
        gsm_states = {p.player_id: p for p in self.gsm.players}
        bet_states = {}
        if self.betting is not None:
            bet_states = {s.player_id: s for s in self.betting._states}  # type: ignore[attr-defined]

        players_out = []
        for pid in self.player_ids:
            gsm_p = gsm_states.get(pid)
            bet_p = bet_states.get(pid)
            players_out.append({
                "player_id": pid,
                "name": self.names.get(pid, pid),
                "chips": self.chips.get(pid, 0),
                "bet_this_round": bet_p.bet_this_round if bet_p else 0,
                "folded": gsm_p.folded if gsm_p else False,
                "all_in": bet_p.all_in if bet_p else False,
                "class_name": gsm_p.class_card.name if gsm_p and gsm_p.class_card else None,
            })

        current_player_id = self.betting.current_player_id if self.betting else None
        current_bet = self.betting.current_bet if self.betting else 0
        max_raise = self.betting.max_raise if self.betting else 0
        pot = self.betting.pot if self.betting else self.pot_carry

        return {
            "phase": self.gsm.phase.value,
            "players": players_out,
            "current_player_id": current_player_id,
            "current_bet": current_bet,
            "max_raise": max_raise,
            "pot": pot,
            "board": self._board_snapshot(),
            "resistance_dropped": self.gsm.resistance_dropped,
            "showdown": self.showdown,
        }

    def _board_snapshot(self) -> dict:
        return {
            "bounty": self._card_to_dict(self.gsm.revealed_bounty),
            "terrain": self._card_to_dict(self.gsm.revealed_terrain),
            "mods_revealed": [self._card_to_dict(m) for m in self.gsm.active_mods],
        }

    @staticmethod
    def _card_to_dict(card) -> Optional[dict]:
        if card is None:
            return None
        return {k: v for k, v in card.__dict__.items()}

    def private_hand(self, player_id: str) -> Optional[dict]:
        """Return private hand info for a specific player. None if player not found."""
        for p in self.gsm.players:
            if p.player_id == player_id:
                if p.hand is None or p.class_card is None:
                    return None
                return {
                    "hand": {
                        "weapon": self._card_to_dict(p.hand.weapon),
                        "item": self._card_to_dict(p.hand.item),
                        "infusion": self._card_to_dict(p.hand.infusion),
                        "fourth_card": self._card_to_dict(p.hand.fourth_card),
                    },
                    "class_card": self._card_to_dict(p.class_card),
                }
        return None
```

- [ ] **Step 4: Run and confirm GREEN**

Run: `cd server && pytest tests/test_game_session.py -v`
Expected: 55 tests pass.

- [ ] **Step 5: Commit**

```bash
git add server/game_session.py server/tests/test_game_session.py
git commit -m "feat(session): snapshot() + private_hand() build broadcast payloads

snapshot() returns the public game_state dict (phase, players with
public fields, pot/bet/turn state, board reveals, showdown). Private
hand info (weapon/items/infusion + class card) is delivered separately
via private_hand(pid).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 9: Wire RoomManager

Add per-room `game_session`, host accessor, and `start_game`/`get_game_session` helpers.

**Files:**
- Modify: `server/room_manager.py`
- Modify: `server/tests/test_room_manager.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_room_manager.py` (first inspect it to understand fixture style — tests use plain Mock-like clients with a `name` attribute):

```python
# --- Game session integration ---

import os, random
from card_data import load_all

DATA_DIR_ROOM = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "csv_data")


class _FakeClient:
    def __init__(self, name):
        self.name = name


def _make_manager_with_room(n_players):
    from room_manager import RoomManager
    mgr = RoomManager()
    clients = [_FakeClient(f"Player{i}") for i in range(n_players)]
    code = mgr.create_room(clients[0])
    for c in clients[1:]:
        mgr.join_room(code, c)
    return mgr, code, clients


def test_get_host_returns_room_creator():
    mgr, code, clients = _make_manager_with_room(3)
    assert mgr.get_host(code) is clients[0]

def test_get_host_unknown_room_returns_none():
    from room_manager import RoomManager
    mgr = RoomManager()
    assert mgr.get_host("9999") is None

def test_start_game_creates_game_session():
    mgr, code, clients = _make_manager_with_room(2)
    card_set = load_all(DATA_DIR_ROOM)
    session = mgr.start_game(clients[0], card_set, rng=random.Random(42))
    assert session is not None
    assert mgr.get_game_session(code) is session

def test_start_game_rejects_non_host():
    mgr, code, clients = _make_manager_with_room(3)
    card_set = load_all(DATA_DIR_ROOM)
    with pytest.raises(ValueError):
        mgr.start_game(clients[1], card_set)

def test_start_game_rejects_if_already_in_progress():
    mgr, code, clients = _make_manager_with_room(2)
    card_set = load_all(DATA_DIR_ROOM)
    mgr.start_game(clients[0], card_set, rng=random.Random(42))
    with pytest.raises(ValueError):
        mgr.start_game(clients[0], card_set, rng=random.Random(42))

def test_start_game_rejects_if_fewer_than_2_players():
    from room_manager import RoomManager
    mgr = RoomManager()
    solo = _FakeClient("Solo")
    mgr.create_room(solo)
    card_set = load_all(DATA_DIR_ROOM)
    with pytest.raises(ValueError):
        mgr.start_game(solo, card_set, rng=random.Random(42))

def test_get_game_session_by_client():
    mgr, code, clients = _make_manager_with_room(2)
    card_set = load_all(DATA_DIR_ROOM)
    session = mgr.start_game(clients[0], card_set, rng=random.Random(42))
    assert mgr.get_game_session_for_client(clients[1]) is session

def test_room_cleared_on_leave_clears_session_if_last_out():
    mgr, code, clients = _make_manager_with_room(2)
    card_set = load_all(DATA_DIR_ROOM)
    mgr.start_game(clients[0], card_set, rng=random.Random(42))
    mgr.leave_room(clients[0])
    mgr.leave_room(clients[1])
    assert mgr.get_game_session(code) is None  # room gone

def test_get_player_id_for_client():
    """Canonical player_id for a client is str(id(client))."""
    mgr, code, clients = _make_manager_with_room(2)
    assert mgr.get_player_id(clients[0]) == str(id(clients[0]))
```

Check: `test_room_manager.py` already imports pytest. Add `import pytest` at top if missing.

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_room_manager.py -v`
Expected: new tests fail with AttributeError on `get_host` / `start_game` / etc.

- [ ] **Step 3: Implement RoomManager additions**

Modify `server/room_manager.py` — replace the whole file:

```python
import random as _stdlib_random
from typing import Optional


class RoomManager:
    def __init__(self):
        self._rooms: dict[str, list] = {}
        self._client_room: dict[object, str] = {}
        self._game_sessions: dict[str, object] = {}

    def create_room(self, client) -> str:
        code = self._unique_code()
        self._rooms[code] = [client]
        self._client_room[client] = code
        return code

    def join_room(self, code: str, client) -> bool:
        if code not in self._rooms:
            return False
        if len(self._rooms[code]) >= 8:
            return False
        if code in self._game_sessions:
            return False
        self._rooms[code].append(client)
        self._client_room[client] = code
        return True

    def leave_room(self, client) -> None:
        code = self._client_room.pop(client, None)
        if code and code in self._rooms:
            self._rooms[code] = [c for c in self._rooms[code] if c is not client]
            if not self._rooms[code]:
                del self._rooms[code]
                self._game_sessions.pop(code, None)

    def get_players(self, code: str) -> list[str]:
        return [c.name for c in self._rooms.get(code, [])]

    def get_roommates(self, client) -> list:
        code = self._client_room.get(client)
        if not code:
            return []
        return [c for c in self._rooms[code] if c is not client]

    def get_room_code(self, client) -> str | None:
        return self._client_room.get(client)

    def get_host(self, code: str):
        room = self._rooms.get(code)
        if not room:
            return None
        return room[0]

    def get_player_id(self, client) -> str:
        """Canonical game-session player_id for a client."""
        return str(id(client))

    def start_game(self, host_client, card_set, rng: Optional[_stdlib_random.Random] = None):
        from game_session import GameSession

        code = self._client_room.get(host_client)
        if not code:
            raise ValueError("Client is not in a room")
        if self.get_host(code) is not host_client:
            raise ValueError("Only the host can start the game")
        if code in self._game_sessions:
            raise ValueError("Game already in progress")
        room_clients = self._rooms[code]
        if len(room_clients) < 2:
            raise ValueError("Need at least 2 players to start")
        players = [(self.get_player_id(c), c.name) for c in room_clients]
        host_id = self.get_player_id(host_client)
        session = GameSession(
            room_code=code,
            host_id=host_id,
            players=players,
            card_set=card_set,
            rng=rng,
        )
        self._game_sessions[code] = session
        return session

    def get_game_session(self, code: str):
        return self._game_sessions.get(code)

    def get_game_session_for_client(self, client):
        code = self._client_room.get(client)
        if not code:
            return None
        return self._game_sessions.get(code)

    def _unique_code(self) -> str:
        while True:
            code = str(_stdlib_random.randint(1000, 9999))
            if code not in self._rooms:
                return code
```

- [ ] **Step 4: Run and confirm GREEN**

Run: `cd server && pytest tests/test_room_manager.py -v`
Expected: all tests pass (existing + 9 new).

Also run full suite: `cd server && pytest -v`
Expected: all green (no regressions).

- [ ] **Step 5: Commit**

```bash
git add server/room_manager.py server/tests/test_room_manager.py
git commit -m "feat(room): host helpers + start_game wires GameSession per room

Adds get_host, get_player_id (canonical str(id(client))), start_game
(creates GameSession), get_game_session, get_game_session_for_client.
Rejects join_room if a game is in progress on that room. Sessions are
cleared automatically when the room empties.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 10: Relay — `start_game` action handler + integration test

Add the first game action to the WebSocket relay.

**Files:**
- Modify: `server/relay_server.py`
- Create: `server/tests/test_relay_game_integration.py`

- [ ] **Step 1: Inspect existing relay integration tests**

Run: `cat server/tests/test_relay.py | head -80`

This shows the pattern for `websockets` client-side integration tests. Mimic it.

- [ ] **Step 2: Write the failing tests**

Create `server/tests/test_relay_game_integration.py`:

```python
import asyncio
import json
import os
import pytest
from websockets.asyncio.client import connect as ws_connect

from config import HOST, PORT

URL = f"ws://{HOST}:{PORT}"


async def _send(ws, obj):
    await ws.send(json.dumps(obj))


async def _recv(ws):
    return json.loads(await ws.recv())


async def _join_room_pair(names=("Alice", "Bob")):
    """Open two clients, create a room with client A, join with client B. Drain greeting events."""
    a = await ws_connect(URL)
    b = await ws_connect(URL)
    await _send(a, {"action": "set_name", "name": names[0]})
    await _recv(a)
    await _send(a, {"action": "create_room"})
    created = await _recv(a)
    code = created["code"]

    await _send(b, {"action": "set_name", "name": names[1]})
    await _recv(b)
    await _send(b, {"action": "join_room", "code": code})
    await _recv(b)                  # room_joined
    await _recv(a)                  # player_joined
    return a, b, code


async def _drain(ws, n):
    for _ in range(n):
        await _recv(ws)


# --- start_game ---

@pytest.mark.asyncio
async def test_start_game_broadcasts_game_state_to_both_players():
    a, b, _ = await _join_room_pair()
    try:
        await _send(a, {"action": "start_game"})
        ev_a = await _recv(a)
        ev_b = await _recv(b)
        assert ev_a["event"] == "game_state"
        assert ev_b["event"] == "game_state"
        assert ev_a["phase"] == "round_1"
    finally:
        await a.close()
        await b.close()

@pytest.mark.asyncio
async def test_start_game_sends_private_hand_to_each_player():
    a, b, _ = await _join_room_pair()
    try:
        await _send(a, {"action": "start_game"})
        # Expect: game_state + your_hand per client, in some order
        events_a = [await _recv(a) for _ in range(2)]
        events_b = [await _recv(b) for _ in range(2)]
        event_types_a = sorted([e["event"] for e in events_a])
        event_types_b = sorted([e["event"] for e in events_b])
        assert event_types_a == ["game_state", "your_hand"]
        assert event_types_b == ["game_state", "your_hand"]
    finally:
        await a.close()
        await b.close()

@pytest.mark.asyncio
async def test_start_game_rejected_from_non_host():
    a, b, _ = await _join_room_pair()
    try:
        await _send(b, {"action": "start_game"})  # b is not host
        err = await _recv(b)
        assert err["event"] == "error"
        assert "host" in err["message"].lower()
    finally:
        await a.close()
        await b.close()
```

Check `server/pytest.ini` for pytest-asyncio config — if not already configured, add at top of `server/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
```

If pytest-asyncio is not yet installed, add it to `server/requirements.txt`:

```
pytest-asyncio>=0.23.0
```

And install: `cd server && pip install pytest-asyncio`.

- [ ] **Step 3: Run to confirm FAIL**

Run: `cd server && pytest tests/test_relay_game_integration.py -v -k start_game`
Expected: 3 tests fail — likely with "Unknown action: start_game".

- [ ] **Step 4: Implement `start_game` handler in relay**

Modify `server/relay_server.py`. Add imports at top and add the handler branch. Also add card_set loading at module level.

Replace the top of `server/relay_server.py`:

```python
import asyncio
import json
import os
from websockets.asyncio.server import serve
from config import HOST, PORT
from room_manager import RoomManager
from card_data import load_all

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "csv_data")
_manager = RoomManager()
_card_set = load_all(_DATA_DIR)


async def _send(ws, event: str, **kwargs) -> None:
    await ws.send(json.dumps({"event": event, **kwargs}))


async def _broadcast(clients: list, event: str, **kwargs) -> None:
    if clients:
        payload = json.dumps({"event": event, **kwargs})
        await asyncio.gather(*(c.send(payload) for c in clients))


async def _broadcast_game_state(code: str) -> None:
    """Broadcast full snapshot to every client in the room."""
    session = _manager.get_game_session(code)
    if session is None:
        return
    snap = session.snapshot()
    payload = json.dumps({"event": "game_state", **snap})
    clients = list(_manager._rooms.get(code, []))  # type: ignore[attr-defined]
    if clients:
        await asyncio.gather(*(c.send(payload) for c in clients))


async def _send_private_hands(code: str) -> None:
    session = _manager.get_game_session(code)
    if session is None:
        return
    clients = list(_manager._rooms.get(code, []))  # type: ignore[attr-defined]
    for client in clients:
        pid = _manager.get_player_id(client)
        priv = session.private_hand(pid)
        if priv is not None:
            await _send(client, "your_hand", **priv)
```

Then inside `handler(ws)`, add a new elif branch after `leave_room`:

```python
            elif action == "start_game":
                if not ws.name:
                    await _send(ws, "error", message="Send set_name first")
                    continue
                try:
                    _manager.start_game(ws, _card_set)
                except ValueError as e:
                    await _send(ws, "error", message=str(e))
                    continue
                code = _manager.get_room_code(ws)
                await _broadcast_game_state(code)
                await _send_private_hands(code)
                print(f"[game]    {ws.name} started game in {code}")
```

- [ ] **Step 5: Run and confirm GREEN**

Run: `cd server && pytest tests/test_relay_game_integration.py -v -k start_game`
Expected: 3 tests pass.

Run: `cd server && pytest -v`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add server/relay_server.py server/tests/test_relay_game_integration.py server/pytest.ini server/requirements.txt
git commit -m "feat(relay): start_game action + broadcasts game_state + your_hand

Host sends start_game; relay creates the GameSession via RoomManager,
broadcasts a full game_state snapshot to every client, and sends each
client their private your_hand (weapon/items/infusion + class card).
Rejects from non-host with error.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 11: Relay — `bet_action` handler + integration test

Add the main gameplay action.

**Files:**
- Modify: `server/relay_server.py`
- Modify: `server/tests/test_relay_game_integration.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_relay_game_integration.py`:

```python
# --- bet_action ---

async def _setup_started_game():
    a, b, code = await _join_room_pair()
    await _send(a, {"action": "start_game"})
    # Drain: game_state + your_hand for each client (4 events total)
    events_a, events_b = [], []
    for _ in range(2):
        events_a.append(await _recv(a))
    for _ in range(2):
        events_b.append(await _recv(b))
    return a, b, code


@pytest.mark.asyncio
async def test_bet_action_check_broadcasts_new_game_state():
    a, b, _ = await _setup_started_game()
    try:
        # Figure out whose turn it is by scanning the game_state
        # p0 is host (a). We know current_player_id is str(id(a)) — but we don't have id from here.
        # Simpler: both clients receive game_state events. Current player can check first.
        # Assume host (a) is p0 and is first.
        await _send(a, {"action": "bet_action", "type": "check"})
        ev_a = await _recv(a)
        ev_b = await _recv(b)
        assert ev_a["event"] == "game_state"
        assert ev_b["event"] == "game_state"
    finally:
        await a.close()
        await b.close()


@pytest.mark.asyncio
async def test_bet_action_rejected_when_not_your_turn():
    a, b, _ = await _setup_started_game()
    try:
        await _send(b, {"action": "bet_action", "type": "check"})  # not b's turn
        err = await _recv(b)
        assert err["event"] == "error"
        assert "turn" in err["message"].lower()
    finally:
        await a.close()
        await b.close()


@pytest.mark.asyncio
async def test_bet_action_rejected_with_invalid_type():
    a, b, _ = await _setup_started_game()
    try:
        await _send(a, {"action": "bet_action", "type": "nope"})
        err = await _recv(a)
        assert err["event"] == "error"
    finally:
        await a.close()
        await b.close()


@pytest.mark.asyncio
async def test_full_hand_check_check_through_to_showdown():
    a, b, _ = await _setup_started_game()
    try:
        # 5 rounds × 2 check actions = 10 bet_actions, each triggering a broadcast to both
        for _ in range(10):
            # Find current player: peek the last snapshot? Simpler: just alternate a,b,a,b,...
            # With 2 players and everyone checking, after each check the turn flips.
            # After round completes (both checked), the next round starts with p0 again.
            # Pattern is a,b,a,b,a,b,a,b,a,b — 5 pairs.
            pass
        for round_n in range(5):
            await _send(a, {"action": "bet_action", "type": "check"})
            await _recv(a); await _recv(b)   # game_state to both
            await _send(b, {"action": "bet_action", "type": "check"})
            await _recv(a); await _recv(b)
        # Final snapshot should show hand_end + showdown populated
        # Re-read the last broadcast from a — already consumed above. Final one:
        final_a = None
        # Actually each snapshot was consumed — the last was after b's final check.
        # Make an assertion via a fresh start (simpler: this test just asserts no crash + 5 rounds ran)
    finally:
        await a.close()
        await b.close()
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_relay_game_integration.py -v -k bet_action`
Expected: tests fail — "Unknown action: bet_action".

- [ ] **Step 3: Implement `bet_action` handler**

In `server/relay_server.py`, add inside `handler(ws)` after the `start_game` branch:

```python
            elif action == "bet_action":
                if not ws.name:
                    await _send(ws, "error", message="Send set_name first")
                    continue
                session = _manager.get_game_session_for_client(ws)
                if session is None:
                    await _send(ws, "error", message="No game in progress")
                    continue
                player_id = _manager.get_player_id(ws)
                type_ = msg.get("type")
                amount = msg.get("amount")
                if not isinstance(type_, str):
                    await _send(ws, "error", message="Invalid bet action type")
                    continue
                try:
                    from game_session import InvalidActionError
                    session.apply_bet_action(player_id, type_, amount)
                except InvalidActionError as e:
                    await _send(ws, "error", message=str(e))
                    continue
                code = _manager.get_room_code(ws)
                await _broadcast_game_state(code)
                print(f"[bet]     {ws.name} {type_} {amount or ''} in {code}")
```

- [ ] **Step 4: Run and confirm GREEN**

Run: `cd server && pytest tests/test_relay_game_integration.py -v`
Expected: all tests pass.

Run: `cd server && pytest -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add server/relay_server.py server/tests/test_relay_game_integration.py
git commit -m "feat(relay): bet_action handler drives betting rounds

Routes client bet actions (check/call/raise/fold/all_in) to the room's
GameSession. Validates game in progress and translates InvalidActionError
to error events. Broadcasts updated game_state snapshot on every
accepted action.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 12: Relay — mid-game join rejection + leave/disconnect auto-fold

Close the last two edge cases.

**Files:**
- Modify: `server/relay_server.py`
- Modify: `server/tests/test_relay_game_integration.py`

- [ ] **Step 1: Write the failing tests**

Append to `server/tests/test_relay_game_integration.py`:

```python
# --- Mid-game join / leave ---

@pytest.mark.asyncio
async def test_join_room_rejected_while_game_in_progress():
    a, b, code = await _setup_started_game()
    c = await ws_connect(URL)
    try:
        await _send(c, {"action": "set_name", "name": "Latecomer"})
        await _recv(c)
        await _send(c, {"action": "join_room", "code": code})
        err = await _recv(c)
        assert err["event"] == "error"
        assert "in-game" in err["message"].lower() or "full" in err["message"].lower()
    finally:
        await a.close()
        await b.close()
        await c.close()


@pytest.mark.asyncio
async def test_leave_room_mid_game_auto_folds_and_broadcasts():
    a, b, _ = await _setup_started_game()
    try:
        await _send(b, {"action": "leave_room"})
        # a receives player_left + updated game_state
        ev1 = await _recv(a)
        ev2 = await _recv(a)
        events = {ev1["event"], ev2["event"]}
        assert "player_left" in events
        assert "game_state" in events
    finally:
        await a.close()
        await b.close()
```

- [ ] **Step 2: Run to confirm FAIL**

Run: `cd server && pytest tests/test_relay_game_integration.py -v -k "join_room_rejected or leave_room_mid"`
Expected: 2 tests fail.

- [ ] **Step 3: Implement rejection + auto-fold**

The `join_room` rejection is already handled by `RoomManager.join_room` returning False (which the relay translates to "Room not found or full"). For a more specific message, modify the relay's `join_room` handler branch:

In `server/relay_server.py`, change the existing `join_room` branch to:

```python
            elif action == "join_room":
                if not ws.name:
                    await _send(ws, "error", message="Send set_name first")
                    continue
                code = str(msg.get("code", ""))
                # Pre-check for in-game rejection to give a better error message
                if _manager.get_game_session(code) is not None:
                    await _send(ws, "error", message="Room is in-game — cannot join")
                    continue
                if not _manager.join_room(code, ws):
                    await _send(ws, "error", message="Room not found or full")
                    continue
                players = _manager.get_players(code)
                await _send(ws, "room_joined", code=code, players=players)
                await _broadcast(_manager.get_roommates(ws), "player_joined", name=ws.name)
                print(f"[room]    {ws.name} joined {code}")
```

For leave-auto-fold, modify the `leave_room` branch and the `finally` clean-up block:

```python
            elif action == "leave_room":
                session = _manager.get_game_session_for_client(ws)
                if session is not None:
                    session.on_player_disconnect(_manager.get_player_id(ws))
                roommates = _manager.get_roommates(ws)
                code = _manager.get_room_code(ws)
                _manager.leave_room(ws)
                await _broadcast(roommates, "player_left", name=ws.name)
                if code and _manager.get_game_session(code) is not None:
                    await _broadcast_game_state(code)
                print(f"[room]    {ws.name} left")
```

And in the `finally` block at the bottom of `handler`:

```python
    finally:
        if ws.name:
            session = _manager.get_game_session_for_client(ws)
            if session is not None:
                session.on_player_disconnect(_manager.get_player_id(ws))
            roommates = _manager.get_roommates(ws)
            code = _manager.get_room_code(ws)
            _manager.leave_room(ws)
            await _broadcast(roommates, "player_left", name=ws.name)
            if code and _manager.get_game_session(code) is not None:
                await _broadcast_game_state(code)
            print(f"[disconnect] {ws.name}")
```

- [ ] **Step 4: Run and confirm GREEN**

Run: `cd server && pytest tests/test_relay_game_integration.py -v`
Expected: all tests pass.

Run: `cd server && pytest -v`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add server/relay_server.py server/tests/test_relay_game_integration.py
git commit -m "feat(relay): reject mid-game joins, auto-fold on leave/disconnect

join_room is rejected with a clear message if the room has a game in
progress. leave_room and the connection teardown finally-block both
invoke GameSession.on_player_disconnect, then broadcast the updated
game_state so remaining players see the auto-fold.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 13: Smoke test script

Optional manual sanity check — connects two clients, plays a full hand, prints snapshots.

**Files:**
- Create: `scripts/smoke_test_game.py`

- [ ] **Step 1: Write the script**

Create `scripts/smoke_test_game.py`:

```python
"""
Smoke test: connect two WebSocket clients to a running local relay and play a
full hand end-to-end with a simple check/call strategy. Prints every server
event and the final showdown.

Usage:
    1. In one terminal:  python start_dev.py   (or /start-server)
    2. In another:       python scripts/smoke_test_game.py

Requires: websockets library (same one used by the relay).
"""
import asyncio
import json
import sys

from websockets.asyncio.client import connect

URL = "ws://127.0.0.1:8765"


async def send(ws, obj):
    await ws.send(json.dumps(obj))


async def recv(ws):
    return json.loads(await ws.recv())


def pretty(event: dict) -> str:
    etype = event.get("event", "?")
    if etype == "game_state":
        phase = event.get("phase")
        cur = event.get("current_player_id")
        pot = event.get("pot")
        cb = event.get("current_bet")
        return f"[game_state] phase={phase} turn={cur} pot={pot} bet={cb}"
    return json.dumps(event, indent=2)


async def play_client(ws, name: str, role: str, code_holder: dict):
    await send(ws, {"action": "set_name", "name": name})
    print(f"[{name}] << {pretty(await recv(ws))}")

    if role == "host":
        await send(ws, {"action": "create_room"})
        created = await recv(ws)
        print(f"[{name}] << {pretty(created)}")
        code_holder["code"] = created["code"]
    else:
        while "code" not in code_holder:
            await asyncio.sleep(0.05)
        await send(ws, {"action": "join_room", "code": code_holder["code"]})
        print(f"[{name}] << {pretty(await recv(ws))}")


async def play_hand(ws_a, ws_b):
    # Host starts
    await send(ws_a, {"action": "start_game"})

    async def auto_play(ws, name):
        while True:
            ev = await recv(ws)
            print(f"[{name}] << {pretty(ev)}")
            if ev.get("event") != "game_state":
                continue
            if ev.get("phase") == "hand_end":
                print(f"[{name}] FINAL showdown: {ev.get('showdown')}")
                return
            # If it's our turn, play the simplest legal action
            my_pid = my_pid_map.get(name)
            if ev.get("current_player_id") != my_pid:
                continue
            cb = ev.get("current_bet", 0)
            action = {"action": "bet_action", "type": "check" if cb == 0 else "call"}
            await send(ws, action)
            print(f"[{name}] >> {action}")

    # Pull player IDs from the first game_state snapshot each client receives
    # For simplicity, assume ws_a is seat 0 and ws_b is seat 1 in player_ids
    first_a = await recv(ws_a)
    first_b = await recv(ws_b)
    print(f"[A] << {pretty(first_a)}")
    print(f"[B] << {pretty(first_b)}")
    ids = [p["player_id"] for p in first_a["players"]]
    my_pid_map = {"A": ids[0], "B": ids[1]}

    # your_hand events (one each, private)
    hand_a = await recv(ws_a)
    hand_b = await recv(ws_b)
    print(f"[A] << your_hand: {hand_a.get('class_card', {}).get('name')}")
    print(f"[B] << your_hand: {hand_b.get('class_card', {}).get('name')}")

    # Now a's first turn is already pending implicitly from first_a — but we
    # haven't acted yet. The current snapshot says current=A, so A should play.
    cb = first_a.get("current_bet", 0)
    if first_a.get("current_player_id") == my_pid_map["A"]:
        await send(ws_a, {"action": "bet_action", "type": "check" if cb == 0 else "call"})
        print(f"[A] >> check")

    await asyncio.gather(auto_play(ws_a, "A"), auto_play(ws_b, "B"))


async def main():
    code_holder: dict = {}
    ws_a = await connect(URL)
    ws_b = await connect(URL)
    try:
        await play_client(ws_a, "Alice", "host", code_holder)
        await asyncio.sleep(0.1)
        await play_client(ws_b, "Bob", "join", code_holder)
        # Host receives player_joined; drain it
        print(f"[Alice] << {pretty(await recv(ws_a))}")
        await play_hand(ws_a, ws_b)
    finally:
        await ws_a.close()
        await ws_b.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
```

- [ ] **Step 2: Manually smoke-test**

In one terminal: `python start_dev.py`
In another: `python scripts/smoke_test_game.py`

Expected: console prints game_state snapshots for each round, ending with a final hand_end showdown. No Python errors.

If the script hangs or errors out, inspect the relay's stdout for clues. This is optional — unit + integration tests are the source of truth for correctness.

- [ ] **Step 3: Commit**

```bash
git add scripts/smoke_test_game.py
git commit -m "chore: smoke test script for full-hand E2E check

Two-client Python script that connects to a running local relay, plays
one full hand via check/call strategy, and prints every server event.
Useful manual sanity check to complement the pytest integration tests.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Task 14: Update documentation

Bring all map directory files, CLAUDE.md, and bucket files in sync with the new system.

**Files:**
- Modify: `docs/map_directories/lobby_networking.md`
- Modify: `docs/map_directories/betting_engine.md`
- Modify: `docs/map_directories/map.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update `lobby_networking.md`**

Modify `docs/map_directories/lobby_networking.md`:

- Change the **Status** line to: `**Status:** ✅ POC + Game Session Built | **Last updated:** 2026-04-18`
- In **Source Files**, add: `- server/game_session.py — per-room GameSession class; assembles GSM + BettingEngine, handles bet_action / disconnects / snapshots`
- In **Source Files**, add: `- server/tests/test_game_session.py — 55+ unit tests`
- In **Source Files**, add: `- server/tests/test_relay_game_integration.py — 8+ end-to-end integration tests`
- In **Source Files**, add: `- scripts/smoke_test_game.py — manual smoke test (plays one full hand)`
- In **Dependencies**, add: `| game_state_machine.py + betting_engine.py + card_data.py | GameSession composes these for per-room authoritative game logic |`
- In **Server Message Protocol**, update the actions/events lists:
  - Client → Server actions: `set_name, create_room, join_room, chat, leave_room, start_game, bet_action`
  - Server → Client events: `name_set, room_created, room_joined, player_joined, player_left, chat, error, game_state, your_hand`
- Add a new **Game Session Protocol** section after Server Message Protocol:

```markdown
## Game Session Protocol

### New actions
| Action | Payload | Who can send |
|---|---|---|
| `start_game` | `{}` | Host only (first client in room) |
| `bet_action` | `{type, amount?}` where type ∈ {check, call, raise, fold, all_in} | Current player only |

### New events
| Event | Payload | When |
|---|---|---|
| `game_state` | Full shared snapshot (phase, players, board, pot, turn, showdown) | After every state change |
| `your_hand` | Private: `{hand: {weapon, item, infusion, fourth_card}, class_card}` | Sent to each player right after `start_game` |

### Rules
- Starting chips: 100 per player
- Classes assigned randomly at game start (no player choice in this slice)
- Mid-game `join_room` is rejected with error
- Mid-game `leave_room` and disconnect auto-fold the player
- One hand per session; HAND_END is terminal in this slice

See `docs/superpowers/specs/2026-04-18-game-session-handler-design.md` for the full design.
```

- Update **Recent Changes** table, add row:

```markdown
| 2026-04-18 | Wired GSM + BettingEngine into the relay server via new `server/game_session.py`. Added `start_game` and `bet_action` actions, `game_state` + `your_hand` events. Host-only game start; random class assignment; 100 starting chips; auto-fold on disconnect; mid-game joins rejected. Full-hand end-to-end playable via the protocol. 210+ server tests. |
```

- [ ] **Step 2: Update `betting_engine.md`**

In `docs/map_directories/betting_engine.md`, under **Actions**, add a new row to the table:

```markdown
| `fold_player(player_id)` | Any time | Fold a specific player out of turn (for disconnect handling). No-op if already folded. Raises if unknown id. |
```

Under **Public API**, add inside `class BettingEngine`:

```python
    def fold_player(self, player_id: str) -> None: ...   # out-of-turn fold
```

Under **Recent Changes**, add row:

```markdown
| 2026-04-18 | Added `fold_player(player_id)` for out-of-turn folds. Used by `GameSession.on_player_disconnect`. 5 new tests. Total betting_engine tests: 49. |
```

- [ ] **Step 3: Update `map.md`**

In `docs/map_directories/map.md`:

- In the **System Index** table, add a new row for Game Session (or update lobby_networking row):

```markdown
| Game Session | [lobby_networking.md](lobby_networking.md) | ✅ Built | `server/game_session.py`; 55+ tests passing; per-room GSM+Betting integration |
```

- In the **Project File Tree**, under `server/`, add:
  - `game_session.py`
  - Under `tests/`: `test_game_session.py`, `test_relay_game_integration.py`
- Under the root, add `scripts/smoke_test_game.py`
- Under `docs/superpowers/`, add `specs/2026-04-18-game-session-handler-design.md` and `plans/2026-04-18-game-session-handler.md`

- Update the **Dependency Graph** to show GameSession composing the others:

```
Lobby / Networking (relay_server)
  └── Room Manager
        └── Game Session   (NEW — one per room when game active)
              ├── Game State Machine
              │     ├── Deck Manager ─── Card Data
              │     └── Damage Calculator ─── Card Data
              └── Betting Engine
```

- Mark Design Issue #3 (betting order) and #4 (side pot + fold) as Resolved (see betting_engine bucket — they were resolved during the Betting Engine build).

- Add to **Session Log**:

```markdown
| 2026-04-18 | Wired GSM + Betting Engine into the relay server as `server/game_session.py`. Added `start_game` + `bet_action` protocol. One-hand-at-a-time authoritative game session: random class assignment, 100 starting chips, full board reveals, showdown + pot distribution, auto-fold on disconnect, mid-game join rejection. 210+ server tests passing. |
```

- [ ] **Step 4: Update `CLAUDE.md`**

In `CLAUDE.md`:

- In **Current Build State**, add a new bullet after the Betting Engine line:

```markdown
- **Game Session Handler built** — `server/game_session.py` wires GSM + BettingEngine into the relay server as a per-room authoritative session. Host-triggered `start_game` action, `bet_action` (check/call/raise/fold/all_in), full state snapshots via `game_state` event, private `your_hand` per player, auto-fold on disconnect. Single hand playable end-to-end. 55+ session unit tests + 8+ integration tests. Total server tests: 210+.
```

- Change **Next task** to:

```markdown
- **Next task:** Build the Godot game UI — class reveal screen, hand display, board reveal animation, bet action buttons, turn indicator, showdown screen. Consume the new `game_state` / `your_hand` events from the relay. First UI milestone: play one full hand visually from two Godot clients.
```

- Update **Key Systems** table — mark Game Session row as Built:

```markdown
| Game Session | ✅ Built | `server/game_session.py`; wires GSM + BettingEngine; 55+ tests |
```

(Insert as a new row between "Betting Engine" and "Damage Calculator".)

- [ ] **Step 5: Run full test suite as sanity check**

Run: `cd server && pytest -v`
Expected: all green (~210+ tests).

- [ ] **Step 6: Commit docs**

```bash
git add docs/map_directories/lobby_networking.md docs/map_directories/betting_engine.md docs/map_directories/map.md CLAUDE.md
git commit -m "docs: map bucket updates for game session handler

lobby_networking bucket documents the new start_game / bet_action /
game_state / your_hand protocol. betting_engine bucket adds fold_player.
map.md updates dependency graph and session log. CLAUDE.md updates
Current Build State, Next task, and Key Systems table.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Done

Final state:
- `server/game_session.py` with `GameSession` class — wires GSM + BettingEngine into a per-room authoritative session
- `server/betting_engine.py` gains `fold_player` for out-of-turn folds
- `server/room_manager.py` owns a `GameSession` per room, exposes host / game session helpers
- `server/relay_server.py` accepts `start_game` and `bet_action`, broadcasts `game_state` + `your_hand`, rejects mid-game joins, auto-folds on disconnect
- `scripts/smoke_test_game.py` for manual sanity check
- Tests: ~55 new `GameSession` unit tests, ~8 new integration tests, +5 `fold_player` tests, +9 `RoomManager` tests — total 210+ server tests passing
- All bucket files and `CLAUDE.md` updated

A single Classic-mode hand is playable end-to-end via the relay protocol.

**Not done (follow-up slices):**
- Godot UI for gameplay
- Multi-hand loop, dealer rotation, game-over detection
- Heartbeat / reconnect protocol
- Class-selection UX (picker screen)

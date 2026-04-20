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

def _play_check_check_through_remainder(session):
    from game_state_machine import GamePhase
    while session.gsm.phase != GamePhase.HAND_END:
        current = session.betting.current_player_id if session.betting else None
        if current is None:
            break
        session.apply_bet_action(current, "check")

def test_showdown_pot_distribution_single_winner(card_set):
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "call")
    s.apply_bet_action("p2", "call")
    _play_check_check_through_remainder(s)
    total = sum(s.chips.values())
    assert total == 3 * STARTING_CHIPS  # conservation of chips

def test_showdown_tied_winners_split_pot(card_set, monkeypatch):
    # Monkeypatch calculate_damage to force a tie
    import game_state_machine
    original = game_state_machine.calculate_damage
    def fake(hand, board):
        return 10
    monkeypatch.setattr(game_state_machine, "calculate_damage", fake)

    s = _make_session(card_set, n_players=2)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "call")
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
    """p0 all-in for full stack, p1 calls (commits all), p2 has chips but only 1 active.
    Next round should fast-forward since only p2 can act."""
    from game_state_machine import GamePhase
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "all_in")    # p0: 100 all-in
    s.apply_bet_action("p1", "call")      # p1 calls, all-in
    s.apply_bet_action("p2", "call")      # p2 calls, still has chips
    # p0 and p1 are both all-in; p2 still has chips but is alone.
    # Fast-forward should activate
    assert s.gsm.phase == GamePhase.HAND_END

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

def test_distribute_pots_side_pot_fallback_when_damage_winner_ineligible(card_set):
    # Pathological case: a side pot's eligible set doesn't contain any damage
    # winner. Happens when the sole damage winner went all-in early (only
    # eligible for the main pot) and the side pot is contested only among
    # players who lost the damage race. Fallback: highest-damage eligible wins.
    from betting_engine import Pot
    s = _make_session(card_set, n_players=3)
    s.last_round_pots = [
        Pot(amount=30, eligible_player_ids=["p0", "p1", "p2"]),
        Pot(amount=20, eligible_player_ids=["p1", "p2"]),
    ]
    damages = {"p0": 50, "p1": 30, "p2": 20}
    dist = s._distribute_pots(winner_ids=["p0"], damages=damages)
    assert dist["p0"] == 30  # main pot: damage winner is eligible
    assert dist["p1"] == 20  # side pot fallback: p1 has higher damage than p2

def test_distribute_pots_side_pot_fallback_splits_tied_damages(card_set):
    from betting_engine import Pot
    s = _make_session(card_set, n_players=3)
    s.last_round_pots = [
        Pot(amount=21, eligible_player_ids=["p1", "p2"]),
    ]
    damages = {"p0": 50, "p1": 30, "p2": 30}
    dist = s._distribute_pots(winner_ids=["p0"], damages=damages)
    # Tie between p1 and p2 on damage; split 21 → 10 each + 1 remainder to
    # earliest-seated (p1)
    assert dist["p1"] == 11
    assert dist["p2"] == 10

def test_disconnect_mid_raise_remaining_players_finish_round(card_set):
    # p0 raises; p1 disconnects before acting; p2 is still pending.
    # Reopen-after-raise semantics: once p1 is auto-folded, p2 must act to close.
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    assert s.betting.current_player_id == "p1"
    s.on_player_disconnect("p1")
    # p1 folded, turn passed to p2 (non-current disconnect does not shift turn
    # if p1 wasn't current — but p1 was current here, so turn must advance)
    assert s.betting.current_player_id == "p2"
    folded = {p.player_id for p in s.gsm.players if p.folded}
    assert folded == {"p1"}
    # p2 calls, closing round 1; session advances into round 2
    s.apply_bet_action("p2", "call")
    from game_state_machine import GamePhase
    assert s.gsm.phase == GamePhase.ROUND_2
    assert s.chips["p1"] == STARTING_CHIPS  # p1 never bet chips this round


# --- Snapshot ---

def test_snapshot_has_phase(card_set):
    s = _make_session(card_set)
    snap = s.snapshot()
    assert snap["phase"] == "round_1"

def test_snapshot_has_room_code_and_host_id(card_set):
    s = _make_session(card_set)
    snap = s.snapshot()
    assert snap["room_code"] == "1234"
    assert snap["host_id"] == "p0"

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


# --- Showdown payload: damage_breakdown + revealed_hands ---

def test_showdown_includes_damage_breakdown(card_set):
    s = _make_session(card_set)
    _play_check_check_through_rounds(s, 5)
    sd = s.showdown
    assert "damage_breakdown" in sd
    for pid in ("p0", "p1"):
        bd = sd["damage_breakdown"][pid]
        assert set(bd.keys()) == {"weapon", "class", "items", "mods_sum", "infusion_mult", "total"}
        assert bd["total"] == sd["damages"][pid]

def test_showdown_includes_revealed_hands_for_non_folded(card_set):
    s = _make_session(card_set)
    _play_check_check_through_rounds(s, 5)
    sd = s.showdown
    assert "revealed_hands" in sd
    for pid in ("p0", "p1"):
        rh = sd["revealed_hands"][pid]
        assert set(rh.keys()) == {"weapon", "item", "infusion", "fourth_card", "class_card"}
        for v in rh.values():
            assert isinstance(v, dict)

def test_showdown_revealed_hands_omits_folded_players(card_set):
    # 3-player game: p0 folds round 1; p1 and p2 play through to showdown.
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "fold")   # p0 out; p1 and p2 continue
    # Drive remaining two players through to showdown via checks each round
    _play_check_check_through_remainder(s)
    sd = s.showdown
    assert sd is not None
    assert "p0" not in sd["revealed_hands"]
    assert "p1" in sd["revealed_hands"]
    assert "p2" in sd["revealed_hands"]

def test_walkover_showdown_has_empty_breakdown_and_hands(card_set):
    # 3-player game: p1 and p2 fold → p0 walks over (no damage calc).
    s = _make_session(card_set, n_players=3)
    s.apply_bet_action("p0", "raise", 10)
    s.apply_bet_action("p1", "fold")
    s.apply_bet_action("p2", "fold")
    sd = s.showdown
    assert sd["damages"] == {}
    assert sd["damage_breakdown"] == {}
    assert sd["revealed_hands"] == {}
    assert sd["winner_ids"] == ["p0"]

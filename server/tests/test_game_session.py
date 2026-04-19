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

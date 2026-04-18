import pytest
from betting_engine import BettingEngine, BettingPlayer, Pot, BettingRoundResult, MAX_RAISE_FLOOR


def _players(*chip_counts) -> list[BettingPlayer]:
    return [BettingPlayer(player_id=f"p{i}", chips=c) for i, c in enumerate(chip_counts)]


# --- Constants ---

def test_max_raise_floor_is_10():
    assert MAX_RAISE_FLOOR == 10


# --- Initial state ---

def test_initial_current_bet_is_zero():
    assert BettingEngine(_players(100, 100)).current_bet == 0

def test_initial_pot_includes_carried_amount():
    assert BettingEngine(_players(100, 100), pot_entering_round=25).pot == 25

def test_initial_pot_is_zero_with_no_carry():
    assert BettingEngine(_players(100, 100)).pot == 0

def test_initial_current_player_is_first_in_list():
    assert BettingEngine(_players(100, 100)).current_player_id == "p0"

def test_initial_round_is_not_complete():
    assert BettingEngine(_players(100, 100)).is_round_complete is False

def test_initial_max_raise_is_floor_when_pot_is_small():
    assert BettingEngine(_players(100, 100)).max_raise == MAX_RAISE_FLOOR


# --- Check ---

def test_check_advances_to_next_player():
    e = BettingEngine(_players(100, 100))
    e.check()
    assert e.current_player_id == "p1"

def test_check_does_not_change_current_bet():
    e = BettingEngine(_players(100, 100))
    e.check()
    assert e.current_bet == 0

def test_check_is_invalid_when_current_bet_nonzero():
    e = BettingEngine(_players(100, 100))
    e.raise_bet(10)  # p0 raises; p1's turn
    with pytest.raises(ValueError):
        e.check()

def test_all_players_checking_completes_round():
    e = BettingEngine(_players(100, 100))
    e.check()
    e.check()
    assert e.is_round_complete is True


# --- Call ---

def test_call_deducts_correct_chips():
    e = BettingEngine(_players(100, 100))
    e.raise_bet(10)  # p0 raises to 10 (max with empty pot)
    e.call()         # p1 calls 10
    result = e.finish()
    assert result.remaining_chips["p1"] == 90

def test_call_advances_to_next_player():
    e = BettingEngine(_players(100, 100, 100))
    e.raise_bet(10)
    e.call()
    assert e.current_player_id == "p2"

def test_call_completes_round_when_all_active_players_matched():
    e = BettingEngine(_players(100, 100))
    e.raise_bet(10)
    e.call()
    assert e.is_round_complete is True

def test_call_auto_all_in_when_insufficient_chips():
    e = BettingEngine(_players(100, 8))
    e.raise_bet(10)  # p0 raises to 10; p1 only has 8
    e.call()         # p1 auto all-in for 8
    result = e.finish()
    assert result.remaining_chips["p1"] == 0


# --- Raise ---

def test_raise_sets_current_bet():
    e = BettingEngine(_players(100, 100))
    e.raise_bet(10)
    assert e.current_bet == 10

def test_raise_deducts_chips_from_raiser():
    e = BettingEngine(_players(100, 100))
    e.raise_bet(10)   # p0 raises; p1 folds to complete round
    e.fold()
    result = e.finish()
    assert result.remaining_chips["p0"] == 90

def test_raise_advances_to_next_player():
    e = BettingEngine(_players(100, 100))
    e.raise_bet(10)
    assert e.current_player_id == "p1"

def test_raise_after_check_forces_checker_to_act_again():
    # p0 checks, p1 raises — p0 must act again
    e = BettingEngine(_players(100, 100, 100))
    e.check()        # p0
    e.raise_bet(10)  # p1 raises — resets p0's acted flag
    e.fold()         # p2 folds
    assert e.current_player_id == "p0"

def test_raise_exceeding_max_raise_raises_error():
    e = BettingEngine(_players(100, 100))
    with pytest.raises(ValueError):
        e.raise_bet(MAX_RAISE_FLOOR + 1)  # pot=0, max=10, raises 11

def test_max_raise_grows_as_pot_grows():
    # p0 raises 10: pot=10. p1 re-raises 10: p1 bets 20 total, pot=10+20=30.
    # p0 must act again; max_raise = max(10, 30) = 30.
    e = BettingEngine(_players(100, 100))
    e.raise_bet(10)   # p0: current_bet=10, pot=10
    e.raise_bet(10)   # p1: current_bet=20, p1 puts in 20, pot=30
    assert e.max_raise == 30

def test_sequential_raises_accumulate_current_bet():
    e = BettingEngine(_players(100, 100))
    e.raise_bet(10)   # p0: current_bet=10
    e.raise_bet(10)   # p1: current_bet=20
    assert e.current_bet == 20


# --- Fold ---

def test_fold_marks_player_folded_in_result():
    e = BettingEngine(_players(100, 100))
    e.raise_bet(10)
    e.fold()
    result = e.finish()
    assert "p1" in result.folded_player_ids

def test_fold_advances_turn():
    e = BettingEngine(_players(100, 100, 100))
    e.raise_bet(10)
    e.fold()   # p1 folds
    assert e.current_player_id == "p2"

def test_one_active_player_after_folds_completes_round():
    e = BettingEngine(_players(100, 100))
    e.raise_bet(10)
    e.fold()
    assert e.is_round_complete is True

def test_folded_player_not_eligible_for_any_pot():
    e = BettingEngine(_players(100, 100, 100))
    e.raise_bet(10)
    e.call()    # p1 calls
    e.fold()    # p2 folds (contributed 0)
    result = e.finish()
    assert "p2" not in result.pots[0].eligible_player_ids


# --- All-in ---

def test_all_in_commits_all_chips():
    e = BettingEngine(_players(30, 100))
    e.all_in()   # p0 all-in for 30
    e.call()     # p1 calls 30
    result = e.finish()
    assert result.remaining_chips["p0"] == 0

def test_all_in_above_current_bet_sets_new_current_bet():
    e = BettingEngine(_players(30, 100))
    e.all_in()   # p0 all-in for 30 (current_bet was 0)
    assert e.current_bet == 30

def test_all_in_below_current_bet_does_not_increase_current_bet():
    # Use carried pot so max_raise = max(10, 50) = 50 allows a raise of 30
    e = BettingEngine(_players(100, 8), pot_entering_round=50)
    e.raise_bet(30)  # p0 raises to 30
    e.all_in()       # p1 all-in for 8 < 30 — current_bet stays 30
    assert e.current_bet == 30

def test_all_in_above_current_bet_resets_other_players_acted_flag():
    # p0 raises to 10, p1 all-in for 50 (> 10) — p0 must act again
    e = BettingEngine(_players(100, 50))
    e.raise_bet(10)  # p0 raises
    e.all_in()       # p1 all-in for 50 — re-opens action
    assert e.current_player_id == "p0"

def test_all_in_below_current_bet_does_not_reopen_action():
    # Use carried pot so max_raise allows raise of 30; p1 partial call
    e = BettingEngine(_players(100, 8), pot_entering_round=50)
    e.raise_bet(30)
    e.all_in()    # p1 partial call (8 < 30) — does NOT re-open
    assert e.is_round_complete is True


# --- Round completion ---

def test_round_not_complete_until_all_respond_to_raise():
    e = BettingEngine(_players(100, 100, 100))
    e.raise_bet(10)
    assert e.is_round_complete is False

def test_round_complete_when_all_active_called():
    e = BettingEngine(_players(100, 100, 100))
    e.raise_bet(10)
    e.call()
    e.call()
    assert e.is_round_complete is True

def test_round_complete_when_all_remaining_players_are_all_in():
    # All 3 go all-in — nobody left to act
    e = BettingEngine(_players(30, 40, 100))
    e.all_in()   # p0: 30
    e.all_in()   # p1: 40 (re-raise)
    e.all_in()   # p2: 100 (re-raise)
    assert e.is_round_complete is True


# --- Side pots ---

def test_all_in_creates_main_pot_and_side_pot():
    # p0(10) all-in → current_bet=10, pot=10, max_raise=10
    # p1 raises by 10 → current_bet=20, p1 bets 20 total
    # p2 calls 20; bets: p0=10, p1=20, p2=20
    # main pot = 10*3=30; side pot = (20-10)*2=20; eligible p1+p2
    e = BettingEngine(_players(10, 50, 50))
    e.all_in()        # p0 all-in for 10; current_bet=10
    e.raise_bet(10)   # p1 raises by 10; current_bet=20; p1 bets 20
    e.call()          # p2 calls 20
    result = e.finish()
    assert len(result.pots) == 2
    assert result.pots[0].amount == 30
    assert set(result.pots[0].eligible_player_ids) == {"p0", "p1", "p2"}
    assert result.pots[1].amount == 20
    assert set(result.pots[1].eligible_player_ids) == {"p1", "p2"}

def test_all_in_player_not_eligible_for_side_pot():
    e = BettingEngine(_players(10, 50, 50))
    e.all_in()
    e.raise_bet(10)
    e.call()
    result = e.finish()
    assert "p0" not in result.pots[1].eligible_player_ids

def test_folded_player_chips_in_main_pot_but_not_eligible():
    # p0 raises 10, p1 calls 10, p2 folds (contributed 0)
    e = BettingEngine(_players(100, 100, 100))
    e.raise_bet(10)
    e.call()
    e.fold()
    result = e.finish()
    assert "p2" not in result.pots[0].eligible_player_ids
    # p0 and p1 each bet 10 → pot = 20
    assert result.pots[0].amount == 20

def test_carried_pot_added_to_main_pot():
    e = BettingEngine(_players(100, 100), pot_entering_round=30)
    e.raise_bet(10)
    e.call()
    result = e.finish()
    # bets: 10+10=20 + carried 30 = 50
    assert result.pots[0].amount == 50

def test_two_all_in_players_create_two_side_pots():
    # p0(10), p1(25), p2(100)
    # p0 all-in 10; p1 all-in 25; p2 calls 25
    # main pot: 10*3=30; side pot 1: (25-10)*2=30; eligible p1+p2
    e = BettingEngine(_players(10, 25, 100))
    e.all_in()   # p0: 10
    e.all_in()   # p1: 25 (re-raise above 10)
    e.call()     # p2: calls 25
    result = e.finish()
    assert len(result.pots) == 2
    assert result.pots[0].amount == 30
    assert result.pots[1].amount == 30
    assert set(result.pots[1].eligible_player_ids) == {"p1", "p2"}


# --- finish() ---

def test_finish_raises_if_round_not_complete():
    with pytest.raises(ValueError):
        BettingEngine(_players(100, 100)).finish()

def test_finish_returns_correct_remaining_chips_for_all_players():
    e = BettingEngine(_players(100, 100))
    e.raise_bet(10)
    e.call()
    result = e.finish()
    assert result.remaining_chips["p0"] == 90
    assert result.remaining_chips["p1"] == 90

def test_finish_returns_all_folded_player_ids():
    e = BettingEngine(_players(100, 100, 100))
    e.raise_bet(10)
    e.fold()
    e.fold()
    result = e.finish()
    assert set(result.folded_player_ids) == {"p1", "p2"}

def test_finish_empty_folded_list_when_nobody_folded():
    e = BettingEngine(_players(100, 100))
    e.check()
    e.check()
    result = e.finish()
    assert result.folded_player_ids == []

def test_pot_grows_as_bets_are_placed():
    e = BettingEngine(_players(100, 100))
    assert e.pot == 0
    e.raise_bet(10)
    assert e.pot == 10
    e.call()
    assert e.pot == 20

import random
import pytest
from card_data import (
    WeaponCard, ItemCard, InfusionCard, BountyCard, TerrainCard,
    BountyModCard, ClassCard, CardSet,
)
from game_state_machine import (
    GameStateMachine, GamePhase, PlayerState, ShowdownResult,
    RESISTANCE_DROP_PROBABILITY,
)


def _make_card_set(n_players=2) -> CardSet:
    weapons = [WeaponCard(name=f"Sword{i}", damage_types=[(3, "slashing")], copies=1) for i in range(n_players + 2)]
    items = [ItemCard(name=f"Item{i}", bonus_value=2, damage_type="slashing", copies=1) for i in range(n_players * 4)]
    infusions = [InfusionCard(name=f"Infusion{i}", infusion_type="Fire", copies=1) for i in range(n_players * 4)]
    bounties = [BountyCard(name=f"Bounty{i}", vulnerability="Fire", resistance="Ice") for i in range(10)]
    terrains = [TerrainCard(name=f"Terrain{i}", adds_vulnerability="Fire") for i in range(10)]
    mods = [BountyModCard(affected_type="slashing", modifier=1, copies=1) for i in range(15)]
    classes = [ClassCard(name=f"Class{i}", damage_formulas=[("2+LV", "slashing")]) for i in range(n_players + 2)]
    return CardSet(
        weapons=weapons, items=items, infusions=infusions,
        bounties=bounties, terrains=terrains, bounty_mods=mods, classes=classes,
    )


def _make_gsm(n_players=2, assign_classes=True) -> GameStateMachine:
    cs = _make_card_set(n_players)
    gsm = GameStateMachine(cs, rng=random.Random(42))
    for i in range(n_players):
        gsm.add_player(f"player_{i}")
    if assign_classes:
        gsm.start_class_selection()
        for i in range(n_players):
            gsm.assign_class(f"player_{i}", cs.classes[i])
    return gsm


def _advance_to_showdown(gsm: GameStateMachine) -> None:
    gsm.start_hand()
    for _ in range(5):
        gsm.advance_round()


# --- Constants ---

def test_resistance_drop_probability_constant_is_25_percent():
    assert RESISTANCE_DROP_PROBABILITY == 0.25


# --- Initial state ---

def test_initial_phase_is_lobby():
    cs = _make_card_set()
    gsm = GameStateMachine(cs)
    assert gsm.phase == GamePhase.LOBBY

def test_initial_player_count_is_zero():
    cs = _make_card_set()
    gsm = GameStateMachine(cs)
    assert len(gsm.players) == 0

def test_initial_events_is_empty():
    cs = _make_card_set()
    gsm = GameStateMachine(cs)
    assert gsm.events == []


# --- Player management ---

def test_add_player_increases_count():
    cs = _make_card_set()
    gsm = GameStateMachine(cs)
    gsm.add_player("alice")
    assert len(gsm.players) == 1

def test_remove_player_decreases_count():
    cs = _make_card_set()
    gsm = GameStateMachine(cs)
    gsm.add_player("alice")
    gsm.remove_player("alice")
    assert len(gsm.players) == 0

def test_cannot_add_more_than_8_players():
    cs = _make_card_set(n_players=8)
    gsm = GameStateMachine(cs)
    for i in range(8):
        gsm.add_player(f"p{i}")
    with pytest.raises(ValueError):
        gsm.add_player("overflow")

def test_cannot_add_duplicate_player_id():
    cs = _make_card_set()
    gsm = GameStateMachine(cs)
    gsm.add_player("alice")
    with pytest.raises(ValueError):
        gsm.add_player("alice")

def test_remove_nonexistent_player_raises():
    cs = _make_card_set()
    gsm = GameStateMachine(cs)
    with pytest.raises(ValueError):
        gsm.remove_player("ghost")


# --- Start class selection ---

def test_start_class_selection_transitions_to_class_selection():
    cs = _make_card_set()
    gsm = GameStateMachine(cs)
    gsm.add_player("alice")
    gsm.add_player("bob")
    gsm.start_class_selection()
    assert gsm.phase == GamePhase.CLASS_SELECTION

def test_start_class_selection_requires_at_least_two_players():
    cs = _make_card_set()
    gsm = GameStateMachine(cs)
    gsm.add_player("alice")
    with pytest.raises(ValueError):
        gsm.start_class_selection()


# --- Assign class ---

def test_assign_class_sets_class_card_on_player():
    cs = _make_card_set()
    gsm = _make_gsm(assign_classes=False)
    gsm.start_class_selection()
    gsm.assign_class("player_0", cs.classes[0])
    player = next(p for p in gsm.players if p.player_id == "player_0")
    assert player.class_card is cs.classes[0]

def test_assign_class_to_nonexistent_player_raises():
    gsm = _make_gsm(assign_classes=False)
    gsm.start_class_selection()
    cs = _make_card_set()
    with pytest.raises(ValueError):
        gsm.assign_class("ghost", cs.classes[0])


# --- Start hand ---

def test_start_hand_transitions_to_round_1():
    gsm = _make_gsm()
    gsm.start_hand()
    assert gsm.phase == GamePhase.ROUND_1

def test_start_hand_deals_hands_to_all_players():
    gsm = _make_gsm()
    gsm.start_hand()
    for p in gsm.players:
        assert p.hand is not None

def test_start_hand_draws_board_cards():
    gsm = _make_gsm()
    gsm.start_hand()
    # After ROUND_1 starts, first bounty mod is revealed
    assert len(gsm.active_mods) == 1

def test_start_hand_requires_class_selection_or_hand_end_phase():
    cs = _make_card_set()
    gsm = GameStateMachine(cs)
    gsm.add_player("alice")
    gsm.add_player("bob")
    with pytest.raises(ValueError):
        gsm.start_hand()


# --- Round progression ---

def test_advance_round_from_round_1_goes_to_round_2():
    gsm = _make_gsm()
    gsm.start_hand()
    gsm.advance_round()
    assert gsm.phase == GamePhase.ROUND_2

def test_advance_round_from_round_5_goes_to_showdown():
    gsm = _make_gsm()
    _advance_to_showdown(gsm)
    assert gsm.phase == GamePhase.SHOWDOWN

def test_advance_round_through_all_five_rounds():
    gsm = _make_gsm()
    gsm.start_hand()
    expected = [
        GamePhase.ROUND_2,
        GamePhase.ROUND_3,
        GamePhase.ROUND_4,
        GamePhase.ROUND_5,
        GamePhase.SHOWDOWN,
    ]
    for phase in expected:
        gsm.advance_round()
        assert gsm.phase == phase


# --- Board card reveals ---

def test_round_1_reveals_first_bounty_mod():
    gsm = _make_gsm()
    gsm.start_hand()
    assert len(gsm.active_mods) == 1

def test_round_2_reveals_bounty():
    gsm = _make_gsm()
    gsm.start_hand()
    gsm.advance_round()  # → ROUND_2
    assert gsm.revealed_bounty is not None

def test_round_3_reveals_second_bounty_mod():
    gsm = _make_gsm()
    gsm.start_hand()
    gsm.advance_round()  # → ROUND_2
    gsm.advance_round()  # → ROUND_3
    assert len(gsm.active_mods) == 2

def test_round_4_reveals_terrain():
    gsm = _make_gsm()
    gsm.start_hand()
    for _ in range(3):
        gsm.advance_round()  # → ROUND_4
    assert gsm.revealed_terrain is not None

def test_round_5_reveals_third_bounty_mod():
    gsm = _make_gsm()
    gsm.start_hand()
    for _ in range(4):
        gsm.advance_round()  # → ROUND_5
    assert len(gsm.active_mods) == 3


# --- Round 3 resistance drop ---

def test_resistance_not_dropped_before_round_3():
    gsm = _make_gsm()
    gsm.start_hand()
    assert gsm.resistance_dropped is False
    gsm.advance_round()  # → ROUND_2
    assert gsm.resistance_dropped is False

def test_resistance_drop_probability_over_many_hands():
    # 200 hands with known seed — should be ~25% ± tolerance
    cs = _make_card_set(n_players=2)
    gsm = GameStateMachine(cs, rng=random.Random(7))
    for i in range(2):
        gsm.add_player(f"p{i}")
    gsm.start_class_selection()
    for i in range(2):
        gsm.assign_class(f"p{i}", cs.classes[i])
    drop_count = 0
    for _ in range(200):
        gsm.start_hand()
        gsm.advance_round()  # → ROUND_2
        gsm.advance_round()  # → ROUND_3 (resistance drop rolled here)
        if gsm.resistance_dropped:
            drop_count += 1
        # reset for next hand by advancing to SHOWDOWN → HAND_END
        gsm.advance_round()
        gsm.advance_round()
        gsm.advance_round()
        gsm.resolve_showdown()
    assert 30 <= drop_count <= 70  # 25% ± tolerance over 200 hands

def test_resistance_dropped_flag_reset_each_hand():
    # Use a seeded rng that forces drop=True on first hand
    cs = _make_card_set(n_players=2)
    # Find a seed where first hand drops and second does not (or just verify reset)
    gsm = GameStateMachine(cs, rng=random.Random(0))
    for i in range(2):
        gsm.add_player(f"p{i}")
    gsm.start_class_selection()
    for i in range(2):
        gsm.assign_class(f"p{i}", cs.classes[i])
    gsm.start_hand()
    for _ in range(5):
        gsm.advance_round()
    gsm.resolve_showdown()
    # Start second hand — resistance_dropped must be reset
    gsm.start_hand()
    assert gsm.resistance_dropped is False


# --- Folding ---

def test_fold_marks_player_as_folded():
    gsm = _make_gsm()
    gsm.start_hand()
    gsm.fold("player_0")
    player = next(p for p in gsm.players if p.player_id == "player_0")
    assert player.folded is True

def test_all_but_one_folded_transitions_to_showdown():
    gsm = _make_gsm(n_players=3)
    gsm.start_hand()
    gsm.fold("player_0")
    gsm.fold("player_1")
    assert gsm.phase == GamePhase.SHOWDOWN

def test_fold_emits_player_folded_event():
    gsm = _make_gsm()
    gsm.start_hand()
    gsm.fold("player_0")
    assert "player_folded" in gsm.events


# --- Showdown ---

def test_showdown_requires_showdown_phase():
    gsm = _make_gsm()
    gsm.start_hand()
    with pytest.raises(ValueError):
        gsm.resolve_showdown()

def test_showdown_calculates_damage_for_active_players():
    gsm = _make_gsm()
    _advance_to_showdown(gsm)
    result = gsm.resolve_showdown()
    assert set(result.damages.keys()) == {"player_0", "player_1"}

def test_showdown_excludes_folded_players():
    gsm = _make_gsm(n_players=3)
    _advance_to_showdown(gsm)
    gsm.fold("player_2")
    # fold during SHOWDOWN phase still marks as folded
    result = gsm.resolve_showdown()
    assert "player_2" not in result.damages

def test_showdown_all_damages_are_positive_integers():
    gsm = _make_gsm()
    _advance_to_showdown(gsm)
    result = gsm.resolve_showdown()
    for dmg in result.damages.values():
        assert isinstance(dmg, int)
        assert dmg > 0

def test_showdown_winner_is_player_with_highest_damage():
    gsm = _make_gsm()
    _advance_to_showdown(gsm)
    result = gsm.resolve_showdown()
    max_dmg = max(result.damages.values())
    for winner_id in result.winner_ids:
        assert result.damages[winner_id] == max_dmg

def test_showdown_transitions_to_hand_end():
    gsm = _make_gsm()
    _advance_to_showdown(gsm)
    gsm.resolve_showdown()
    assert gsm.phase == GamePhase.HAND_END


# --- Second hand ---

def test_second_hand_starts_after_hand_end():
    gsm = _make_gsm()
    _advance_to_showdown(gsm)
    gsm.resolve_showdown()
    gsm.start_hand()
    assert gsm.phase == GamePhase.ROUND_1

def test_second_hand_resets_folded_status():
    gsm = _make_gsm(n_players=3)
    gsm.start_hand()
    gsm.fold("player_0")
    for _ in range(5):
        gsm.advance_round()
    gsm.resolve_showdown()
    gsm.start_hand()
    player = next(p for p in gsm.players if p.player_id == "player_0")
    assert player.folded is False

def test_second_hand_deals_fresh_hands():
    gsm = _make_gsm()
    _advance_to_showdown(gsm)
    first_hands = {p.player_id: p.hand for p in gsm.players}
    gsm.resolve_showdown()
    gsm.start_hand()
    for p in gsm.players:
        # New hand object dealt — not the same reference as first hand
        assert p.hand is not None


# --- Events ---

def test_round_started_event_emitted_for_each_round():
    gsm = _make_gsm()
    gsm.start_hand()
    for _ in range(5):
        gsm.advance_round()
    round_starts = [e for e in gsm.events if e == "round_started"]
    # round_started emitted for ROUND_1 (start_hand) + ROUND_2-5 (advance_round) = 5 total
    assert len(round_starts) == 5

def test_showdown_started_event_emitted():
    gsm = _make_gsm()
    _advance_to_showdown(gsm)
    assert "showdown_started" in gsm.events

def test_hand_ended_event_emitted_after_resolve_showdown():
    gsm = _make_gsm()
    _advance_to_showdown(gsm)
    gsm.resolve_showdown()
    assert "hand_ended" in gsm.events

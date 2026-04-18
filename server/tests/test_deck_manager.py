import random
import pytest
from card_data import WeaponCard, ItemCard, InfusionCard, BountyCard, TerrainCard, BountyModCard, ClassCard, CardSet
from deck_manager import DeckManager, PlayerHand, BoardDraw, FOURTH_CARD_ITEM_PROBABILITY


def _make_card_set(
    n_weapons=2, n_items=4, n_infusions=4, n_bounties=2, n_terrains=2, n_mods=6
) -> CardSet:
    weapons = [WeaponCard(name=f"Weapon{i}", damage_types=[(2, "slashing")], copies=1) for i in range(n_weapons)]
    items = [ItemCard(name=f"Item{i}", bonus_value=1, damage_type="slashing", copies=1) for i in range(n_items)]
    infusions = [InfusionCard(name=f"Infusion{i}", infusion_type=f"Type{i}", copies=1) for i in range(n_infusions)]
    bounties = [BountyCard(name=f"Bounty{i}", vulnerability="Fire", resistance="Ice") for i in range(n_bounties)]
    terrains = [TerrainCard(name=f"Terrain{i}", adds_vulnerability="Fire") for i in range(n_terrains)]
    bounty_mods = [BountyModCard(affected_type="slashing", modifier=1, copies=1) for i in range(n_mods)]
    classes = [ClassCard(name="Soldier", damage_formulas=[("2+LV", "slashing")])]
    return CardSet(
        weapons=weapons, items=items, infusions=infusions,
        bounties=bounties, terrains=terrains, bounty_mods=bounty_mods,
        classes=classes,
    )


# --- Constants ---

def test_fourth_card_item_probability_constant_is_half():
    assert FOURTH_CARD_ITEM_PROBABILITY == 0.5


# --- deal_hands: structure ---

def test_deal_hands_returns_correct_number_of_hands():
    dm = DeckManager(_make_card_set(), rng=random.Random(0))
    assert len(dm.deal_hands(2)) == 2

def test_each_hand_weapon_is_weapon_card():
    dm = DeckManager(_make_card_set(), rng=random.Random(0))
    for hand in dm.deal_hands(2):
        assert isinstance(hand.weapon, WeaponCard)

def test_each_hand_item_is_item_card():
    dm = DeckManager(_make_card_set(), rng=random.Random(0))
    for hand in dm.deal_hands(2):
        assert isinstance(hand.item, ItemCard)

def test_each_hand_infusion_is_infusion_card():
    dm = DeckManager(_make_card_set(), rng=random.Random(0))
    for hand in dm.deal_hands(2):
        assert isinstance(hand.infusion, InfusionCard)

def test_fourth_card_is_item_or_infusion():
    dm = DeckManager(_make_card_set(n_items=4, n_infusions=4), rng=random.Random(0))
    for hand in dm.deal_hands(2):
        assert isinstance(hand.fourth_card, (ItemCard, InfusionCard))


# --- deal_hands: no duplicates within a single deal ---

def test_deal_hands_each_player_gets_unique_weapon():
    # 2 weapons (copies=1 each), 2 players — no two players share a weapon slot
    dm = DeckManager(_make_card_set(n_weapons=2), rng=random.Random(0))
    names = [h.weapon.name for h in dm.deal_hands(2)]
    assert len(set(names)) == 2

def test_deal_hands_each_player_gets_unique_item():
    # n_items=4: 2 primary slots + 2 available for fourth cards
    dm = DeckManager(_make_card_set(n_items=4), rng=random.Random(0))
    names = [h.item.name for h in dm.deal_hands(2)]
    assert len(set(names)) == 2

def test_deal_hands_each_player_gets_unique_infusion():
    dm = DeckManager(_make_card_set(n_infusions=4), rng=random.Random(0))
    names = [h.infusion.name for h in dm.deal_hands(2)]
    assert len(set(names)) == 2


# --- Fourth card probability ---

def test_fourth_card_probability_roughly_fifty_fifty():
    # 200 deals with seeded rng — expect roughly 50/50, within ±15%
    cs = _make_card_set(n_weapons=1, n_items=210, n_infusions=210, n_bounties=2, n_terrains=2, n_mods=6)
    dm = DeckManager(cs, rng=random.Random(42))
    item_count = sum(
        1 for _ in range(200)
        if isinstance(dm.deal_hands(1)[0].fourth_card, ItemCard)
    )
    assert 70 <= item_count <= 130


# --- draw_board: structure ---

def test_draw_board_bounty_is_bounty_card():
    dm = DeckManager(_make_card_set(), rng=random.Random(0))
    assert isinstance(dm.draw_board().bounty, BountyCard)

def test_draw_board_terrain_is_terrain_card():
    dm = DeckManager(_make_card_set(), rng=random.Random(0))
    assert isinstance(dm.draw_board().terrain, TerrainCard)

def test_draw_board_has_exactly_three_bounty_mods():
    dm = DeckManager(_make_card_set(n_mods=6), rng=random.Random(0))
    assert len(dm.draw_board().bounty_mods) == 3

def test_draw_board_each_mod_is_bounty_mod_card():
    dm = DeckManager(_make_card_set(n_mods=6), rng=random.Random(0))
    for mod in dm.draw_board().bounty_mods:
        assert isinstance(mod, BountyModCard)


# --- draw_board: deck progression ---

def test_successive_draws_consume_different_bounty_cards():
    # 2 bounties in sub-pile; two draws must each take a different bounty
    dm = DeckManager(_make_card_set(n_bounties=2, n_terrains=2, n_mods=6), rng=random.Random(0))
    b1 = dm.draw_board().bounty.name
    b2 = dm.draw_board().bounty.name
    assert b1 != b2


# --- Bounty deck reshuffle ---

def test_bounty_sub_piles_reshuffle_when_depleted():
    # Exactly 1 bounty, 1 terrain, 3 mods — enough for exactly 1 draw.
    # Second draw must auto-reshuffle each sub-pile and succeed.
    cs = _make_card_set(n_weapons=1, n_items=2, n_infusions=2, n_bounties=1, n_terrains=1, n_mods=3)
    dm = DeckManager(cs, rng=random.Random(0))
    dm.draw_board()  # depletes all three sub-piles
    board = dm.draw_board()  # must reshuffle and succeed
    assert isinstance(board.bounty, BountyCard)
    assert isinstance(board.terrain, TerrainCard)
    assert len(board.bounty_mods) == 3

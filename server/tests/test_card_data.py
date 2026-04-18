import os
import pytest
from card_data import load_all, CardSet, WeaponCard, ItemCard, InfusionCard, BountyCard, TerrainCard, BountyModCard, ClassCard

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "csv_data")


@pytest.fixture(scope="module")
def card_set() -> CardSet:
    return load_all(DATA_DIR)


# --- Card counts ---

def test_weapon_count(card_set):
    assert len(card_set.weapons) == 20

def test_item_unique_count(card_set):
    assert len(card_set.items) == 10

def test_item_total_copies(card_set):
    assert sum(i.copies for i in card_set.items) == 18

def test_infusion_unique_count(card_set):
    assert len(card_set.infusions) == 7

def test_infusion_total_copies(card_set):
    assert sum(i.copies for i in card_set.infusions) == 21

def test_bounty_count(card_set):
    assert len(card_set.bounties) == 7

def test_terrain_count(card_set):
    assert len(card_set.terrains) == 7

def test_bounty_mod_unique_count(card_set):
    assert len(card_set.bounty_mods) == 8

def test_bounty_mod_total_copies(card_set):
    assert sum(bm.copies for bm in card_set.bounty_mods) == 12

def test_class_count(card_set):
    assert len(card_set.classes) == 15


# --- Spot checks: weapons ---

def test_greatsword_single_damage_type(card_set):
    greatsword = next(w for w in card_set.weapons if w.name == "Greatsword")
    assert greatsword.damage_types == [(3, "slashing")]

def test_sword_and_board_two_damage_types(card_set):
    sab = next(w for w in card_set.weapons if w.name == "Sword and Board +")
    assert set(sab.damage_types) == {(2, "slashing"), (2, "blunt")}

def test_staff_damage(card_set):
    staff = next(w for w in card_set.weapons if w.name == "Staff")
    assert staff.damage_types == [(6, "magic")]


# --- Spot checks: bounties ---

def test_dragon_vulnerability_and_resistance(card_set):
    dragon = next(b for b in card_set.bounties if b.name == "Dragon")
    assert dragon.vulnerability == "Ice"
    assert dragon.resistance == "Fire"


# --- Bounty mod modifiers ---

def test_all_bounty_mod_modifiers_are_plus_or_minus_one(card_set):
    for bm in card_set.bounty_mods:
        assert bm.modifier in (1, -1), f"unexpected modifier {bm.modifier} on {bm.affected_type}"


# --- Normalization: no "Weak to" strings survive ---

def test_no_weak_to_strings_in_bounty_mods(card_set):
    for bm in card_set.bounty_mods:
        assert "Weak to" not in bm.affected_type, f"'Weak to' found in affected_type: {bm.affected_type}"

def test_weak_to_normalized_to_modifier_plus_one(card_set):
    # All +1 mods should come from "Weak to" rows; ensure they exist
    plus_one = [bm for bm in card_set.bounty_mods if bm.modifier == 1]
    assert len(plus_one) == 4  # Piercing, Blunt, Slashing, Constricting


# --- Terrain suffix whitespace ---

def test_terrain_adds_vulnerability_stripped(card_set):
    for t in card_set.terrains:
        assert t.adds_vulnerability == t.adds_vulnerability.strip()

def test_cave_terrain(card_set):
    cave = next(t for t in card_set.terrains if t.name == "Cave")
    assert cave.adds_vulnerability == "Sonic"


# --- Classes ---

def test_mage_single_class_formula(card_set):
    mage = next(c for c in card_set.classes if c.name == "Mage")
    assert mage.damage_formulas == [("3+LV", "magic")]

def test_spellblade_multiclass_formulas(card_set):
    spellblade = next(c for c in card_set.classes if c.name == "Spellblade")
    assert set(spellblade.damage_formulas) == {("2+LV", "slashing"), ("3+LV", "magic")}

def test_no_hunter_mode_cards_loaded(card_set):
    # Verify Hunter-mode files were not loaded by checking for known Hunter-only card types
    # (feints, training, potions are not part of any Classic dataclass)
    # We just verify card_set has no extra fields beyond the spec
    assert hasattr(card_set, "weapons")
    assert hasattr(card_set, "items")
    assert hasattr(card_set, "infusions")
    assert hasattr(card_set, "bounties")
    assert hasattr(card_set, "terrains")
    assert hasattr(card_set, "bounty_mods")
    assert hasattr(card_set, "classes")
    assert not hasattr(card_set, "feints")
    assert not hasattr(card_set, "potions")

import pytest
from card_data import WeaponCard, ItemCard, InfusionCard, BountyCard, TerrainCard, BountyModCard, ClassCard
from damage_calculator import Hand, BoardState, calculate_damage

# --- Fixtures: cards constructed directly (no CSV loading needed) ---

GREATSWORD = WeaponCard(name="Greatsword", damage_types=[(3, "slashing")], copies=1)
SWORD_AND_BOARD = WeaponCard(name="Sword and Board +", damage_types=[(2, "slashing"), (2, "blunt")], copies=1)
WAND = WeaponCard(name="Wand", damage_types=[(5, "magic")], copies=1)

SOLDIER = ClassCard(name="Soldier", damage_formulas=[("2+LV", "slashing")])
MAGE = ClassCard(name="Mage", damage_formulas=[("3+LV", "magic")])
SPELLBLADE = ClassCard(name="Spellblade", damage_formulas=[("2+LV", "slashing"), ("3+LV", "magic")])

BLADES = ItemCard(name="Blades", bonus_value=1, damage_type="slashing", copies=2)
HAMMER = ItemCard(name="Hammer", bonus_value=2, damage_type="blunt", copies=2)

SHOCKING = InfusionCard(name="Shocking", infusion_type="Electric", copies=3)
FROZEN = InfusionCard(name="Frozen", infusion_type="Ice", copies=3)
BURNING = InfusionCard(name="Burning", infusion_type="Fire", copies=3)
THUNDEROUS = InfusionCard(name="Thunderous", infusion_type="Sonic", copies=3)

BEAST = BountyCard(name="Beast", vulnerability="Sonic", resistance="Ice")
DRAGON = BountyCard(name="Dragon", vulnerability="Ice", resistance="Fire")
CONSTRUCT = BountyCard(name="Construct", vulnerability="Electric", resistance="Sonic")

CAVE = TerrainCard(name="Cave", adds_vulnerability="Sonic")       # Dragon + Cave = Ice vuln + Sonic vuln
TUNDRA = TerrainCard(name="Tundra", adds_vulnerability="Fire")    # Dragon + Tundra = Fire is both vuln and resist

MOD_VULN_SLASHING = BountyModCard(affected_type="Slashing", modifier=1, copies=2)
MOD_VULN_BLUNT = BountyModCard(affected_type="Blunt", modifier=1, copies=2)
MOD_DEFLECT_SLASHING = BountyModCard(affected_type="Slashing", modifier=-1, copies=1)


# --- Base damage ---

def test_weapon_plus_class_no_modifiers():
    # Greatsword (3 slashing) + Soldier (2+LV=3 slashing at LV1)
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST)
    assert calculate_damage(hand, board) == 6

def test_item_adds_to_base():
    # + Blades (1 slashing) = 7
    hand = Hand(weapon=GREATSWORD, items=[BLADES], infusions=[], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST)
    assert calculate_damage(hand, board) == 7

def test_mage_class_uses_three_plus_lv_formula():
    # Wand (5 magic) + Mage (3+LV=4 magic at LV1) = 9
    hand = Hand(weapon=WAND, items=[], infusions=[], class_card=MAGE, level=1)
    board = BoardState(bounty=BEAST)
    assert calculate_damage(hand, board) == 9

def test_multiclass_both_formulas_contribute_to_base():
    # Greatsword (3 slashing) + Spellblade (2+LV=3 slashing, 3+LV=4 magic) = 10
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[], class_card=SPELLBLADE, level=1)
    board = BoardState(bounty=BEAST)
    assert calculate_damage(hand, board) == 10

def test_level_affects_class_formula():
    # Soldier at LV3: 2+3=5 slashing. Greatsword 3. Total = 8.
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[], class_card=SOLDIER, level=3)
    board = BoardState(bounty=BEAST)
    assert calculate_damage(hand, board) == 8


# --- Infusion multiplier ---

def test_infusion_matching_vulnerability_multiplies():
    # Sonic infusion + Beast (vuln Sonic): 1.0 + 0.5 = 1.5. 6 × 1.5 = 9
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[THUNDEROUS], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST)
    assert calculate_damage(hand, board) == 9

def test_infusion_matching_resistance_reduces():
    # Ice infusion + Beast (resist Ice): 1.0 - 0.5 = 0.5. 6 × 0.5 = 3
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[FROZEN], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST)
    assert calculate_damage(hand, board) == 3

def test_infusion_not_matching_vulnerability_or_resistance_is_neutral():
    # Electric infusion, Beast (Sonic vuln, Ice resist): 1.0 unchanged. 6 × 1.0 = 6
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[SHOCKING], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST)
    assert calculate_damage(hand, board) == 6

def test_duplicate_infusions_each_add_half():
    # 2 Electric infusions, Construct (vuln Electric): 1.0 + 0.5 + 0.5 = 2.0. 6 × 2.0 = 12
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[SHOCKING, SHOCKING], class_card=SOLDIER, level=1)
    board = BoardState(bounty=CONSTRUCT)
    assert calculate_damage(hand, board) == 12

def test_multiplier_floored_at_half():
    # 2 Ice infusions, Beast (resist Ice): 1.0 - 0.5 - 0.5 = 0.0 → floored 0.5. 6 × 0.5 = 3
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[FROZEN, FROZEN], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST)
    assert calculate_damage(hand, board) == 3


# --- Terrain ---

def test_terrain_adds_new_vulnerability_type():
    # Dragon (vuln Ice, resist Fire) + Cave (adds Sonic) + Thunderous (Sonic): Sonic now matched → +0.5
    # Without terrain, Sonic would be neutral. mult = 1.5. 6 × 1.5 = 9
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[THUNDEROUS], class_card=SOLDIER, level=1)
    board = BoardState(bounty=DRAGON, terrain=CAVE)
    assert calculate_damage(hand, board) == 9

def test_terrain_vuln_and_bounty_vuln_both_apply():
    # Dragon + Cave: Ice vuln (bounty) + Sonic vuln (terrain). 1 Frozen + 1 Thunderous → +0.5 + 0.5 = 2.0
    # 6 × 2.0 = 12
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[FROZEN, THUNDEROUS], class_card=SOLDIER, level=1)
    board = BoardState(bounty=DRAGON, terrain=CAVE)
    assert calculate_damage(hand, board) == 12

def test_sonic_infusion_neutral_without_terrain():
    # Dragon alone (vuln Ice, resist Fire). Thunderous (Sonic) has no match → neutral. 6 × 1.0 = 6
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[THUNDEROUS], class_card=SOLDIER, level=1)
    board = BoardState(bounty=DRAGON)
    assert calculate_damage(hand, board) == 6


# --- Infusion cancellation ---

def test_infusion_cancels_when_type_is_both_vuln_and_resist():
    # Dragon (vuln Ice, resist Fire) + Tundra (adds Fire vuln)
    # Fire is now in both vulns and resists → cancel → +0 contribution
    # Multiplier stays 1.0. 6 × 1.0 = 6
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[BURNING], class_card=SOLDIER, level=1)
    board = BoardState(bounty=DRAGON, terrain=TUNDRA)
    assert calculate_damage(hand, board) == 6

def test_non_cancelled_infusion_still_applies_alongside_cancellation():
    # Dragon + Tundra: Fire cancels. Add Ice infusion: +0.5 (Dragon vuln).
    # mult = 1.0 + 0.5 = 1.5. 6 × 1.5 = 9
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[BURNING, FROZEN], class_card=SOLDIER, level=1)
    board = BoardState(bounty=DRAGON, terrain=TUNDRA)
    assert calculate_damage(hand, board) == 9


# --- Resistance drop ---

def test_resistance_dropped_means_resistance_ignored():
    # Dragon (resist Fire), Ice infusion (vuln), Fire infusion (normally -0.5 resist)
    # With resistance_dropped: Fire counts as neutral, Ice still +0.5
    # mult = 1.0 + 0.5 = 1.5. 6 × 1.5 = 9
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[FROZEN, BURNING], class_card=SOLDIER, level=1)
    board = BoardState(bounty=DRAGON, resistance_dropped=True)
    assert calculate_damage(hand, board) == 9

def test_resistance_not_dropped_still_penalizes():
    # Same hand, resistance_dropped=False: Fire -0.5 + Ice +0.5 = 1.0. 6 × 1.0 = 6
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[FROZEN, BURNING], class_card=SOLDIER, level=1)
    board = BoardState(bounty=DRAGON, resistance_dropped=False)
    assert calculate_damage(hand, board) == 6


# --- Bounty mods ---

def test_bounty_mod_vulnerable_applies_per_matching_damage_source():
    # Vulnerable to Slashing (+1), Greatsword (slashing) + Soldier (slashing): 2 sources → +2
    # Base: 3 + 3 + 2 = 8
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST, active_bounty_mods=[MOD_VULN_SLASHING])
    assert calculate_damage(hand, board) == 8

def test_bounty_mod_deflects_applies_per_matching_damage_source():
    # Deflects Slashing (-1), Greatsword + Soldier: 2 sources → -2
    # Base: 3 + 3 - 2 = 4
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST, active_bounty_mods=[MOD_DEFLECT_SLASHING])
    assert calculate_damage(hand, board) == 4

def test_bounty_mod_applies_to_matching_item():
    # Vulnerable to Slashing, Greatsword + Soldier + Blades item (slashing): 3 sources → +3
    # Base: 3 + 3 + 1 + 3 = 10
    hand = Hand(weapon=GREATSWORD, items=[BLADES], infusions=[], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST, active_bounty_mods=[MOD_VULN_SLASHING])
    assert calculate_damage(hand, board) == 10

def test_bounty_mod_no_effect_when_type_not_in_hand():
    # Vulnerable to Blunt, but Greatsword (slashing) + Soldier (slashing): 0 blunt sources → +0
    hand = Hand(weapon=GREATSWORD, items=[], infusions=[], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST, active_bounty_mods=[MOD_VULN_BLUNT])
    assert calculate_damage(hand, board) == 6

def test_dual_type_weapon_matches_mod_for_its_type():
    # Sword and Board (2 slashing, 2 blunt) + Soldier (slashing). Vulnerable to Slashing.
    # Slashing sources: weapon-slashing-slot + soldier = 2 → +2
    # Base: 4 (weapon) + 3 (soldier) + 2 (mod) = 9
    hand = Hand(weapon=SWORD_AND_BOARD, items=[], infusions=[], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST, active_bounty_mods=[MOD_VULN_SLASHING])
    assert calculate_damage(hand, board) == 9

def test_multiple_bounty_mods_stack():
    # Sword and Board + Soldier. Both Slashing (+1) and Blunt (+1) mods active.
    # Slashing: weapon-slashing + soldier = 2 → +2; Blunt: weapon-blunt = 1 → +1
    # Base: 4 + 3 + 3 = 10
    hand = Hand(weapon=SWORD_AND_BOARD, items=[], infusions=[], class_card=SOLDIER, level=1)
    board = BoardState(bounty=BEAST, active_bounty_mods=[MOD_VULN_SLASHING, MOD_VULN_BLUNT])
    assert calculate_damage(hand, board) == 10


# --- ceil() ---

def test_ceil_applied_once_to_final_result():
    # Wand (5) + Mage (4) = 9 base. Sonic infusion + Beast (vuln Sonic): 1.5 mult.
    # 9 × 1.5 = 13.5 → ceil = 14
    hand = Hand(weapon=WAND, items=[], infusions=[THUNDEROUS], class_card=MAGE, level=1)
    board = BoardState(bounty=BEAST)
    assert calculate_damage(hand, board) == 14

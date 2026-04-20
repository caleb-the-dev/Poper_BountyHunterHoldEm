import math
from dataclasses import dataclass, field
from typing import Optional, TypedDict

from card_data import WeaponCard, ItemCard, InfusionCard, BountyCard, TerrainCard, BountyModCard, ClassCard

_MULTIPLIER_FLOOR = 0.5


# Functional TypedDict form — the wire key is literally "class" (Python keyword),
# so we cannot use the class-based syntax here.
DamageBreakdown = TypedDict("DamageBreakdown", {
    "weapon": int,
    "class": int,
    "items": list[int],
    "mods_sum": int,
    "infusion_mult": float,
    "total": int,
})


@dataclass
class Hand:
    weapon: WeaponCard
    items: list[ItemCard]
    infusions: list[InfusionCard]
    class_card: ClassCard
    level: int = 1


@dataclass
class BoardState:
    bounty: BountyCard
    terrain: Optional[TerrainCard] = None
    active_bounty_mods: list[BountyModCard] = field(default_factory=list)
    resistance_dropped: bool = False


def _eval_formula(formula: str, level: int) -> int:
    base, _ = formula.split("+")
    return int(base.strip()) + level


def _damage_sources(hand: Hand) -> list[tuple[str, int]]:
    """Return [(damage_type, amount)] for every damage-dealing card in hand."""
    sources = []
    for amount, dtype in hand.weapon.damage_types:
        sources.append((dtype, amount))
    for item in hand.items:
        sources.append((item.damage_type, item.bonus_value))
    for formula, dtype in hand.class_card.damage_formulas:
        sources.append((dtype, _eval_formula(formula, hand.level)))
    return sources


def _compute_mods_sum(sources: list[tuple[str, int]], active_bounty_mods: list[BountyModCard]) -> int:
    """Sum of mod modifiers * number of matching damage-type sources."""
    total = 0
    for mod in active_bounty_mods:
        matching = sum(1 for dtype, _ in sources if dtype.lower() == mod.affected_type.lower())
        total += mod.modifier * matching
    return total


def _compute_infusion_multiplier(hand: Hand, board: BoardState) -> float:
    """Final multiplier after vuln/resist evaluation, clamped at floor."""
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
            pass  # effects cancel
        elif is_vuln:
            multiplier += 0.5
        elif is_resist:
            multiplier -= 0.5

    return max(multiplier, _MULTIPLIER_FLOOR)


def calculate_damage(hand: Hand, board: BoardState) -> int:
    sources = _damage_sources(hand)

    base = sum(amount for _, amount in sources) + _compute_mods_sum(sources, board.active_bounty_mods)
    multiplier = _compute_infusion_multiplier(hand, board)

    return math.ceil(base * multiplier)


def calculate_damage_breakdown(hand: Hand, board: BoardState) -> DamageBreakdown:
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

    mods_sum = _compute_mods_sum(_damage_sources(hand), board.active_bounty_mods)
    multiplier = _compute_infusion_multiplier(hand, board)

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

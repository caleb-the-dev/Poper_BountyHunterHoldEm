import math
from dataclasses import dataclass, field
from typing import Optional

from card_data import WeaponCard, ItemCard, InfusionCard, BountyCard, TerrainCard, BountyModCard, ClassCard

_MULTIPLIER_FLOOR = 0.5


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


def calculate_damage(hand: Hand, board: BoardState) -> int:
    sources = _damage_sources(hand)

    # Step 1: base damage with bounty mod adjustments
    base = sum(amount for _, amount in sources)
    for mod in board.active_bounty_mods:
        matching = sum(1 for dtype, _ in sources if dtype.lower() == mod.affected_type.lower())
        base += mod.modifier * matching

    # Step 2: infusion multiplier
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

    multiplier = max(multiplier, _MULTIPLIER_FLOOR)

    # Step 3: final
    return math.ceil(base * multiplier)

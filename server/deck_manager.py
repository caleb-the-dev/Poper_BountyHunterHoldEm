import random
from dataclasses import dataclass, field
from typing import Union

from card_data import WeaponCard, ItemCard, InfusionCard, BountyCard, TerrainCard, BountyModCard, CardSet

FOURTH_CARD_ITEM_PROBABILITY = 0.5


@dataclass
class PlayerHand:
    weapon: WeaponCard
    item: ItemCard
    infusion: InfusionCard
    fourth_card: Union[ItemCard, InfusionCard]


@dataclass
class BoardDraw:
    bounty: BountyCard
    terrain: TerrainCard
    bounty_mods: list[BountyModCard]


def _expand(cards: list, copies_attr: str = "copies") -> list:
    """Return a flat list with each card repeated according to its copies field."""
    result = []
    for card in cards:
        count = getattr(card, copies_attr, 1)
        result.extend([card] * count)
    return result


class DeckManager:
    def __init__(self, card_set: CardSet, rng: random.Random = None):
        self._rng = rng or random.Random()
        self._card_set = card_set
        self._bounty_pile: list[BountyCard] = []
        self._terrain_pile: list[TerrainCard] = []
        self._mod_pile: list[BountyModCard] = []
        self._bounty_pos = 0
        self._terrain_pos = 0
        self._mod_pos = 0
        self._shuffle_board_piles()

    # --- Public API ---

    def deal_hands(self, num_players: int) -> list[PlayerHand]:
        weapons = _expand(self._card_set.weapons)
        items = _expand(self._card_set.items)
        infusions = _expand(self._card_set.infusions)
        self._rng.shuffle(weapons)
        self._rng.shuffle(items)
        self._rng.shuffle(infusions)

        # Primary slots: first num_players cards from each pile
        weapon_pool = weapons[:num_players]
        item_pool = items[:num_players]
        infusion_pool = infusions[:num_players]

        # Remaining cards are available for each player's fourth slot
        remaining_items = list(items[num_players:])
        remaining_infusions = list(infusions[num_players:])

        hands = []
        for i in range(num_players):
            fourth = self._draw_fourth(remaining_items, remaining_infusions)
            hands.append(PlayerHand(
                weapon=weapon_pool[i],
                item=item_pool[i],
                infusion=infusion_pool[i],
                fourth_card=fourth,
            ))
        return hands

    def draw_board(self) -> BoardDraw:
        self._ensure_board_pile(self._bounty_pile, self._bounty_pos, 1, "bounty")
        self._ensure_board_pile(self._terrain_pile, self._terrain_pos, 1, "terrain")
        self._ensure_board_pile(self._mod_pile, self._mod_pos, 3, "mod")

        bounty = self._bounty_pile[self._bounty_pos]
        self._bounty_pos += 1

        terrain = self._terrain_pile[self._terrain_pos]
        self._terrain_pos += 1

        mods = self._mod_pile[self._mod_pos : self._mod_pos + 3]
        self._mod_pos += 3

        return BoardDraw(bounty=bounty, terrain=terrain, bounty_mods=mods)

    # --- Internal helpers ---

    def _shuffle_board_piles(self):
        self._bounty_pile = _expand(self._card_set.bounties)
        self._terrain_pile = _expand(self._card_set.terrains)
        self._mod_pile = _expand(self._card_set.bounty_mods)
        self._rng.shuffle(self._bounty_pile)
        self._rng.shuffle(self._terrain_pile)
        self._rng.shuffle(self._mod_pile)
        self._bounty_pos = 0
        self._terrain_pos = 0
        self._mod_pos = 0

    def _ensure_board_pile(self, pile: list, pos: int, needed: int, kind: str):
        remaining = len(pile) - pos
        if remaining < needed:
            if kind == "bounty":
                self._bounty_pile = _expand(self._card_set.bounties)
                self._rng.shuffle(self._bounty_pile)
                self._bounty_pos = 0
            elif kind == "terrain":
                self._terrain_pile = _expand(self._card_set.terrains)
                self._rng.shuffle(self._terrain_pile)
                self._terrain_pos = 0
            elif kind == "mod":
                self._mod_pile = _expand(self._card_set.bounty_mods)
                self._rng.shuffle(self._mod_pile)
                self._mod_pos = 0

    def _draw_fourth(
        self, remaining_items: list, remaining_infusions: list
    ) -> Union[ItemCard, InfusionCard]:
        use_item = self._rng.random() < FOURTH_CARD_ITEM_PROBABILITY
        if use_item and remaining_items:
            return remaining_items.pop(0)
        elif not use_item and remaining_infusions:
            return remaining_infusions.pop(0)
        elif remaining_items:
            return remaining_items.pop(0)
        else:
            return remaining_infusions.pop(0)

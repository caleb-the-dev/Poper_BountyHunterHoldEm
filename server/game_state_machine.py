import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from card_data import CardSet, ClassCard, ItemCard, InfusionCard, BountyModCard, BountyCard, TerrainCard
from deck_manager import DeckManager, PlayerHand, BoardDraw
from damage_calculator import Hand, BoardState, calculate_damage

RESISTANCE_DROP_PROBABILITY = 0.25


class GamePhase(Enum):
    LOBBY = "lobby"
    CLASS_SELECTION = "class_selection"
    ROUND_1 = "round_1"
    ROUND_2 = "round_2"
    ROUND_3 = "round_3"
    ROUND_4 = "round_4"
    ROUND_5 = "round_5"
    SHOWDOWN = "showdown"
    HAND_END = "hand_end"
    GAME_END = "game_end"


_ROUND_PHASES = {
    GamePhase.ROUND_1,
    GamePhase.ROUND_2,
    GamePhase.ROUND_3,
    GamePhase.ROUND_4,
    GamePhase.ROUND_5,
}

_ROUND_SEQUENCE = [
    GamePhase.ROUND_1,
    GamePhase.ROUND_2,
    GamePhase.ROUND_3,
    GamePhase.ROUND_4,
    GamePhase.ROUND_5,
]


@dataclass
class PlayerState:
    player_id: str
    class_card: Optional[ClassCard] = None
    hand: Optional[PlayerHand] = None
    folded: bool = False


@dataclass
class ShowdownResult:
    damages: dict   # player_id -> int
    winner_ids: list  # player_ids with max damage


class GameStateMachine:
    def __init__(self, card_set: CardSet, rng: Optional[random.Random] = None):
        self._card_set = card_set
        self._rng = rng or random.Random()
        self._deck_manager = DeckManager(card_set, rng=self._rng)
        self._players: list[PlayerState] = []
        self._phase = GamePhase.LOBBY
        self._board: Optional[BoardDraw] = None
        self._resistance_dropped = False
        self._active_mods: list[BountyModCard] = []
        self._revealed_bounty: Optional[BountyCard] = None
        self._revealed_terrain: Optional[TerrainCard] = None
        self._events: list[str] = []

    # --- Properties ---

    @property
    def phase(self) -> GamePhase:
        return self._phase

    @property
    def players(self) -> list[PlayerState]:
        return list(self._players)

    @property
    def events(self) -> list[str]:
        return list(self._events)

    @property
    def resistance_dropped(self) -> bool:
        return self._resistance_dropped

    @property
    def active_mods(self) -> list[BountyModCard]:
        return list(self._active_mods)

    @property
    def revealed_bounty(self) -> Optional[BountyCard]:
        return self._revealed_bounty

    @property
    def revealed_terrain(self) -> Optional[TerrainCard]:
        return self._revealed_terrain

    @property
    def board_state(self) -> Optional[BoardState]:
        if self._board is None or self._revealed_bounty is None:
            return None
        return BoardState(
            bounty=self._revealed_bounty,
            terrain=self._revealed_terrain,
            active_bounty_mods=list(self._active_mods),
            resistance_dropped=self._resistance_dropped,
        )

    # --- Lobby ---

    def add_player(self, player_id: str) -> None:
        if len(self._players) >= 8:
            raise ValueError("Maximum 8 players")
        if any(p.player_id == player_id for p in self._players):
            raise ValueError(f"Player {player_id!r} already exists")
        self._players.append(PlayerState(player_id=player_id))

    def remove_player(self, player_id: str) -> None:
        for i, p in enumerate(self._players):
            if p.player_id == player_id:
                del self._players[i]
                return
        raise ValueError(f"Player {player_id!r} not found")

    # --- Class selection ---

    def start_class_selection(self) -> None:
        if self._phase != GamePhase.LOBBY:
            raise ValueError(f"Must be in LOBBY phase, currently {self._phase}")
        if len(self._players) < 2:
            raise ValueError("Need at least 2 players to start")
        self._phase = GamePhase.CLASS_SELECTION
        self._events.append("class_selection_started")

    def assign_class(self, player_id: str, class_card: ClassCard) -> None:
        self._get_player(player_id).class_card = class_card

    # --- Hand flow ---

    def start_hand(self) -> None:
        if self._phase not in (GamePhase.CLASS_SELECTION, GamePhase.HAND_END):
            raise ValueError(f"Must be in CLASS_SELECTION or HAND_END phase, currently {self._phase}")
        self._reset_hand_state()
        hands = self._deck_manager.deal_hands(len(self._players))
        for player, hand in zip(self._players, hands):
            player.hand = hand
        self._board = self._deck_manager.draw_board()
        self._active_mods.append(self._board.bounty_mods[0])
        self._phase = GamePhase.ROUND_1
        self._events.append("hand_started")
        self._events.append("round_started")

    def advance_round(self) -> None:
        if self._phase == GamePhase.ROUND_1:
            self._phase = GamePhase.ROUND_2
            self._revealed_bounty = self._board.bounty
            self._events.append("bounty_revealed")
            self._events.append("round_started")
        elif self._phase == GamePhase.ROUND_2:
            self._phase = GamePhase.ROUND_3
            if self._rng.random() < RESISTANCE_DROP_PROBABILITY:
                self._resistance_dropped = True
                self._events.append("resistance_dropped")
            self._active_mods.append(self._board.bounty_mods[1])
            self._events.append("round_started")
        elif self._phase == GamePhase.ROUND_3:
            self._phase = GamePhase.ROUND_4
            self._revealed_terrain = self._board.terrain
            self._events.append("terrain_revealed")
            self._events.append("round_started")
        elif self._phase == GamePhase.ROUND_4:
            self._phase = GamePhase.ROUND_5
            self._active_mods.append(self._board.bounty_mods[2])
            self._events.append("round_started")
        elif self._phase == GamePhase.ROUND_5:
            self._phase = GamePhase.SHOWDOWN
            self._events.append("showdown_started")
        else:
            raise ValueError(f"Cannot advance round from {self._phase}")

    def fold(self, player_id: str) -> None:
        self._get_player(player_id).folded = True
        self._events.append("player_folded")
        active = [p for p in self._players if not p.folded]
        if len(active) == 1 and self._phase in _ROUND_PHASES:
            self._phase = GamePhase.SHOWDOWN
            self._events.append("showdown_started")

    def force_hand_end_walkover(self) -> None:
        """Jump to HAND_END without a damage showdown — used when only one player
        remains (everyone else folded) and the caller has already decided the winner.
        Valid from any in-hand phase (ROUND_1..SHOWDOWN)."""
        if self._phase not in _ROUND_PHASES and self._phase != GamePhase.SHOWDOWN:
            raise ValueError(f"Cannot force hand end from {self._phase}")
        self._phase = GamePhase.HAND_END
        self._events.append("hand_ended")

    def resolve_showdown(self) -> ShowdownResult:
        if self._phase != GamePhase.SHOWDOWN:
            raise ValueError(f"Must be in SHOWDOWN phase, currently {self._phase}")
        active = [p for p in self._players if not p.folded]
        board = BoardState(
            bounty=self._board.bounty,
            terrain=self._revealed_terrain,
            active_bounty_mods=list(self._active_mods),
            resistance_dropped=self._resistance_dropped,
        )
        damages = {}
        for player in active:
            hand = self._build_hand(player)
            damages[player.player_id] = calculate_damage(hand, board)
        max_dmg = max(damages.values()) if damages else 0
        winners = [pid for pid, dmg in damages.items() if dmg == max_dmg]
        self._phase = GamePhase.HAND_END
        self._events.append("hand_ended")
        return ShowdownResult(damages=damages, winner_ids=winners)

    # --- Internal helpers ---

    def _reset_hand_state(self) -> None:
        self._board = None
        self._resistance_dropped = False
        self._active_mods = []
        self._revealed_bounty = None
        self._revealed_terrain = None
        for p in self._players:
            p.folded = False
            p.hand = None

    def _get_player(self, player_id: str) -> PlayerState:
        for p in self._players:
            if p.player_id == player_id:
                return p
        raise ValueError(f"Player {player_id!r} not found")

    def _build_hand(self, player: PlayerState) -> Hand:
        ph = player.hand
        items = [ph.item]
        infusions = [ph.infusion]
        if isinstance(ph.fourth_card, ItemCard):
            items.append(ph.fourth_card)
        else:
            infusions.append(ph.fourth_card)
        return Hand(
            weapon=ph.weapon,
            items=items,
            infusions=infusions,
            class_card=player.class_card,
            level=1,
        )

import random
from typing import Optional

from card_data import CardSet
from game_state_machine import GameStateMachine
from betting_engine import BettingEngine, BettingPlayer

STARTING_CHIPS = 100


class InvalidActionError(Exception):
    """Raised when a client action violates game rules.
    Carries a client-friendly message."""


class GameSession:
    def __init__(
        self,
        room_code: str,
        host_id: str,
        players: list,
        card_set: CardSet,
        rng: Optional[random.Random] = None,
    ):
        if len(players) < 2:
            raise ValueError("Need at least 2 players to start")
        pids = [pid for pid, _ in players]
        if host_id not in pids:
            raise ValueError(f"host_id {host_id!r} is not in players list")

        self.room_code = room_code
        self.host_id = host_id
        self.player_ids: list = pids
        self.names: dict = {pid: name for pid, name in players}
        self._rng = rng or random.Random()
        self._card_set = card_set

        self.gsm = GameStateMachine(card_set, rng=self._rng)
        for pid in self.player_ids:
            self.gsm.add_player(pid)
        self.gsm.start_class_selection()
        for pid in self.player_ids:
            class_card = self._rng.choice(card_set.classes)
            self.gsm.assign_class(pid, class_card)
        self.gsm.start_hand()

        self.chips: dict = {pid: STARTING_CHIPS for pid in self.player_ids}
        self.pot_carry: int = 0
        self.last_round_pots: list = []
        self.betting: Optional[BettingEngine] = self._new_betting_engine()

    def _new_betting_engine(self) -> BettingEngine:
        """Build a BettingEngine for the current round from non-folded, non-broke players."""
        folded = {p.player_id for p in self.gsm.players if p.folded}
        bplayers = [
            BettingPlayer(pid, self.chips[pid])
            for pid in self.player_ids
            if pid not in folded and self.chips[pid] > 0
        ]
        return BettingEngine(bplayers, pot_entering_round=self.pot_carry)

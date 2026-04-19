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

    def apply_bet_action(self, player_id: str, action_type: str, amount: Optional[int] = None) -> None:
        """Apply a player's betting action. Raises InvalidActionError on rule violations."""
        if self.betting is None:
            raise InvalidActionError("No betting round is active")
        if player_id != self.betting.current_player_id:
            raise InvalidActionError("Not your turn")

        try:
            if action_type == "check":
                self.betting.check()
            elif action_type == "call":
                self.betting.call()
            elif action_type == "raise":
                if amount is None:
                    raise InvalidActionError("Raise requires amount")
                self.betting.raise_bet(amount)
            elif action_type == "fold":
                self.betting.fold()
                self.gsm.fold(player_id)
            elif action_type == "all_in":
                self.betting.all_in()
            else:
                raise InvalidActionError(f"Invalid bet action type: {action_type!r}")
        except ValueError as e:
            raise InvalidActionError(self._translate_betting_error(str(e))) from e

    @staticmethod
    def _translate_betting_error(msg: str) -> str:
        if "Cannot check" in msg:
            return "Cannot check — there is a bet to call"
        if "exceeds max raise" in msg:
            return f"Raise too large — {msg.split('exceeds ')[-1]}"
        if "at least 1" in msg:
            return "Raise must be at least 1"
        if "Not enough chips" in msg:
            return "Not enough chips for that raise"
        return msg

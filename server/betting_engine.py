from dataclasses import dataclass, field
from typing import Optional

MAX_RAISE_FLOOR = 10  # minimum max-raise when pot is small


@dataclass
class BettingPlayer:
    player_id: str
    chips: int


@dataclass
class Pot:
    amount: int
    eligible_player_ids: list


@dataclass
class BettingRoundResult:
    pots: list           # list[Pot], main pot first
    remaining_chips: dict  # player_id -> chips remaining
    folded_player_ids: list


class _PlayerState:
    __slots__ = ("player_id", "chips", "bet_this_round", "folded", "all_in", "round_acted")

    def __init__(self, player_id: str, chips: int):
        self.player_id = player_id
        self.chips = chips
        self.bet_this_round = 0
        self.folded = False
        self.all_in = False
        self.round_acted = False


class BettingEngine:
    def __init__(self, players: list, pot_entering_round: int = 0):
        self._states = [_PlayerState(p.player_id, p.chips) for p in players]
        self._pot_entering = pot_entering_round
        self._current_bet = 0
        self._turn_idx = 0

    # --- Properties ---

    @property
    def current_player_id(self) -> str:
        return self._states[self._turn_idx].player_id

    @property
    def current_bet(self) -> int:
        return self._current_bet

    @property
    def pot(self) -> int:
        return self._pot_entering + sum(s.bet_this_round for s in self._states)

    @property
    def max_raise(self) -> int:
        return max(MAX_RAISE_FLOOR, self.pot)

    @property
    def is_round_complete(self) -> bool:
        non_folded = [s for s in self._states if not s.folded]
        if len(non_folded) <= 1:
            return True
        active = [s for s in non_folded if not s.all_in]
        if not active:
            # Everyone still in the hand is all-in — no more betting possible
            return True
        return all(
            s.round_acted and s.bet_this_round == self._current_bet
            for s in active
        )

    # --- Actions (always act on current player) ---

    def check(self) -> None:
        if self._current_bet != 0:
            raise ValueError("Cannot check when there is an outstanding bet")
        state = self._states[self._turn_idx]
        state.round_acted = True
        self._advance_turn()

    def call(self) -> None:
        state = self._states[self._turn_idx]
        to_call = self._current_bet - state.bet_this_round
        if state.chips <= to_call:
            self._go_all_in(state)
        else:
            state.chips -= to_call
            state.bet_this_round = self._current_bet
            state.round_acted = True
            self._advance_turn()

    def raise_bet(self, amount: int) -> None:
        if amount < 1:
            raise ValueError("Raise amount must be at least 1")
        if amount > self.max_raise:
            raise ValueError(
                f"Raise amount {amount} exceeds max raise {self.max_raise}"
            )
        state = self._states[self._turn_idx]
        new_bet = self._current_bet + amount
        to_add = new_bet - state.bet_this_round
        if state.chips < to_add:
            raise ValueError("Not enough chips to raise")
        state.chips -= to_add
        state.bet_this_round = new_bet
        self._current_bet = new_bet
        state.round_acted = True
        for s in self._states:
            if s.player_id != state.player_id and not s.folded and not s.all_in:
                s.round_acted = False
        self._advance_turn()

    def fold(self) -> None:
        state = self._states[self._turn_idx]
        state.folded = True
        state.round_acted = True
        self._advance_turn()

    def fold_player(self, player_id: str) -> None:
        """Fold a specific player regardless of whose turn it is.
        Used for disconnect handling. No-op if already folded."""
        for state in self._states:
            if state.player_id == player_id:
                if state.folded:
                    return
                state.folded = True
                state.round_acted = True
                return
        raise ValueError(f"Player {player_id!r} not found")

    def all_in(self) -> None:
        self._go_all_in(self._states[self._turn_idx])

    def finish(self) -> BettingRoundResult:
        if not self.is_round_complete:
            raise ValueError("Cannot finish: betting round is not complete")
        pots = self._calculate_pots()
        remaining = {s.player_id: s.chips for s in self._states}
        folded = [s.player_id for s in self._states if s.folded]
        return BettingRoundResult(pots=pots, remaining_chips=remaining, folded_player_ids=folded)

    # --- Internal helpers ---

    def _go_all_in(self, state: _PlayerState) -> None:
        state.bet_this_round += state.chips
        state.chips = 0
        state.all_in = True
        state.round_acted = True
        if state.bet_this_round > self._current_bet:
            self._current_bet = state.bet_this_round
            for s in self._states:
                if s.player_id != state.player_id and not s.folded and not s.all_in:
                    s.round_acted = False
        self._advance_turn()

    def _advance_turn(self) -> None:
        next_idx = self._find_next_active(self._turn_idx + 1)
        if next_idx is not None:
            self._turn_idx = next_idx

    def _find_next_active(self, start: int) -> Optional[int]:
        n = len(self._states)
        for i in range(n):
            idx = (start + i) % n
            s = self._states[idx]
            if not s.folded and not s.all_in:
                return idx
        return None

    def _calculate_pots(self) -> list:
        contributions = {s.player_id: s.bet_this_round for s in self._states}
        folded_ids = {s.player_id for s in self._states if s.folded}
        levels = sorted(set(v for v in contributions.values() if v > 0))

        if not levels:
            eligible = [pid for pid in contributions if pid not in folded_ids]
            return [Pot(amount=self._pot_entering, eligible_player_ids=eligible)]

        pots = []
        prev = 0
        for level in levels:
            pot_amount = sum(
                min(amt, level) - min(amt, prev)
                for amt in contributions.values()
            )
            eligible = [
                pid for pid, amt in contributions.items()
                if pid not in folded_ids and amt >= level
            ]
            if pot_amount > 0:
                pots.append(Pot(amount=pot_amount, eligible_player_ids=eligible))
            prev = level

        # Carried-in chips belong to the main pot
        if pots:
            pots[0] = Pot(
                amount=pots[0].amount + self._pot_entering,
                eligible_player_ids=pots[0].eligible_player_ids,
            )
        return pots

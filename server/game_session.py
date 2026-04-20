import random
from typing import Optional

from card_data import CardSet
from game_state_machine import GameStateMachine
from betting_engine import BettingEngine, BettingPlayer, _PlayerState
from damage_calculator import calculate_damage_breakdown

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
        self.showdown: Optional[dict] = None
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

        if self.betting.is_round_complete:
            self._finish_round()

    def _finish_round(self) -> None:
        """Close the current betting round, advance GSM, open the next round (or showdown)."""
        from game_state_machine import GamePhase

        result = self.betting.finish()
        for pid in result.folded_player_ids:
            if not any(p.player_id == pid and p.folded for p in self.gsm.players):
                self.gsm.fold(pid)
        # Merge updated chips into self.chips — preserves folded players from prior rounds
        # who were excluded from this BettingEngine but still hold their chips.
        self.chips.update(result.remaining_chips)
        self.pot_carry = sum(p.amount for p in result.pots)
        self.last_round_pots = list(result.pots)

        if self.gsm.phase == GamePhase.SHOWDOWN:
            self._resolve_showdown()
            return

        # Advance rounds, fast-forwarding if no one can act
        while True:
            self.gsm.advance_round()
            if self.gsm.phase == GamePhase.SHOWDOWN:
                self._resolve_showdown()
                return
            if self._has_active_bettors():
                self.betting = self._new_betting_engine()
                return
            # else: loop and advance again

    def _has_active_bettors(self) -> bool:
        """True if at least 2 non-folded players have chips > 0."""
        folded = {p.player_id for p in self.gsm.players if p.folded}
        bettors = [pid for pid in self.player_ids if pid not in folded and self.chips[pid] > 0]
        return len(bettors) >= 2

    def _resolve_showdown(self) -> None:
        """Handle SHOWDOWN phase: calculate damage (if more than one player left),
        distribute pots, populate self.showdown."""
        from game_state_machine import GamePhase

        self.betting = None
        non_folded = [p.player_id for p in self.gsm.players if not p.folded]

        if len(non_folded) == 1:
            winner = non_folded[0]
            total = sum(p.amount for p in self.last_round_pots)
            self.chips[winner] += total
            self.gsm.force_hand_end_walkover()
            self.showdown = {
                "damages": {},
                "winner_ids": [winner],
                "pot_distribution": {winner: total},
                "damage_breakdown": {},
                "revealed_hands": {},
            }
            return

        result = self.gsm.resolve_showdown()
        distribution = self._distribute_pots(result.winner_ids, result.damages)
        for pid, amount in distribution.items():
            self.chips[pid] += amount
        self.showdown = {
            "damages": dict(result.damages),
            "winner_ids": list(result.winner_ids),
            "pot_distribution": distribution,
            "damage_breakdown": self._build_damage_breakdown(non_folded),
            "revealed_hands": self._build_revealed_hands(non_folded),
        }

    def _build_showdown_hand(self, player) -> "Hand":
        """Construct a damage_calculator.Hand for this player — mirrors GSM's
        private _build_hand so we don't reach into GSM internals."""
        from card_data import ItemCard
        from damage_calculator import Hand

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

    def _build_damage_breakdown(self, non_folded_ids: list) -> dict:
        """Per-player math parts from damage_calculator — UI reads this to show the math line."""
        board = self.gsm.board_state  # public accessor — preferred over poking _board
        out = {}
        for pid in non_folded_ids:
            player = next(p for p in self.gsm.players if p.player_id == pid)
            hand = self._build_showdown_hand(player)
            out[pid] = calculate_damage_breakdown(hand, board)
        return out

    def _build_revealed_hands(self, non_folded_ids: list) -> dict:
        """Reveal each non-folded player's hand + class for the showdown overlay."""
        out = {}
        for pid in non_folded_ids:
            priv = self.private_hand(pid)
            if priv is None:
                continue
            out[pid] = {
                "weapon":      priv["hand"]["weapon"],
                "item":        priv["hand"]["item"],
                "infusion":    priv["hand"]["infusion"],
                "fourth_card": priv["hand"]["fourth_card"],
                "class_card":  priv["class_card"],
            }
        return out

    def _distribute_pots(self, winner_ids: list, damages: dict) -> dict:
        """Distribute every pot among eligible winners. Returns {player_id: total_won}."""
        distribution: dict = {}
        for pot in self.last_round_pots:
            eligible_winners = [pid for pid in pot.eligible_player_ids if pid in winner_ids]
            if not eligible_winners:
                # Pathological fallback: award to highest-damage eligible player
                eligible_damages = {pid: damages.get(pid, 0) for pid in pot.eligible_player_ids}
                if not eligible_damages:
                    continue
                max_d = max(eligible_damages.values())
                eligible_winners = [pid for pid, d in eligible_damages.items() if d == max_d]
            share, remainder = divmod(pot.amount, len(eligible_winners))
            # Earliest-seated eligible winner gets remainder
            seated_order = [pid for pid in self.player_ids if pid in eligible_winners]
            for pid in seated_order:
                distribution[pid] = distribution.get(pid, 0) + share
            if remainder > 0:
                distribution[seated_order[0]] += remainder
        return distribution

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

    def on_player_disconnect(self, player_id: str) -> None:
        """Handle a player disconnecting mid-game. Auto-folds them.
        No-op if player isn't in this session, already folded, or game is over."""
        from game_state_machine import GamePhase

        if player_id not in self.player_ids:
            return
        if self.gsm.phase in (GamePhase.HAND_END, GamePhase.GAME_END):
            return
        if any(p.player_id == player_id and p.folded for p in self.gsm.players):
            return

        self.gsm.fold(player_id)
        if self.betting is not None:
            self.betting.fold_player(player_id)
            if self.betting.is_round_complete:
                self._finish_round()
            elif self.gsm.phase == GamePhase.SHOWDOWN:
                # GSM auto-transitioned (all-but-one folded)
                self._finish_round()

    def snapshot(self) -> dict:
        """Return the public state dict the relay broadcasts to all clients."""
        gsm_states = {p.player_id: p for p in self.gsm.players}
        bet_states = {}
        if self.betting is not None:
            bet_states = {s.player_id: s for s in self.betting._states}  # type: ignore[attr-defined]

        players_out = []
        for pid in self.player_ids:
            gsm_p = gsm_states.get(pid)
            bet_p = bet_states.get(pid)
            players_out.append({
                "player_id": pid,
                "name": self.names.get(pid, pid),
                "chips": self.chips.get(pid, 0),
                "bet_this_round": bet_p.bet_this_round if bet_p else 0,
                "folded": gsm_p.folded if gsm_p else False,
                "all_in": bet_p.all_in if bet_p else False,
                "class_name": gsm_p.class_card.name if gsm_p and gsm_p.class_card else None,
            })

        current_player_id = self.betting.current_player_id if self.betting else None
        current_bet = self.betting.current_bet if self.betting else 0
        max_raise = self.betting.max_raise if self.betting else 0
        pot = self.betting.pot if self.betting else self.pot_carry

        return {
            "room_code": self.room_code,
            "host_id": self.host_id,
            "phase": self.gsm.phase.value,
            "players": players_out,
            "current_player_id": current_player_id,
            "current_bet": current_bet,
            "max_raise": max_raise,
            "pot": pot,
            "board": self._board_snapshot(),
            "resistance_dropped": self.gsm.resistance_dropped,
            "showdown": self.showdown,
        }

    def _board_snapshot(self) -> dict:
        return {
            "bounty": self._card_to_dict(self.gsm.revealed_bounty),
            "terrain": self._card_to_dict(self.gsm.revealed_terrain),
            "mods_revealed": [self._card_to_dict(m) for m in self.gsm.active_mods],
        }

    @staticmethod
    def _card_to_dict(card) -> Optional[dict]:
        if card is None:
            return None
        return {k: v for k, v in card.__dict__.items()}

    def private_hand(self, player_id: str) -> Optional[dict]:
        """Return private hand info for a specific player. None if player not found."""
        for p in self.gsm.players:
            if p.player_id == player_id:
                if p.hand is None or p.class_card is None:
                    return None
                return {
                    "hand": {
                        "weapon": self._card_to_dict(p.hand.weapon),
                        "item": self._card_to_dict(p.hand.item),
                        "infusion": self._card_to_dict(p.hand.infusion),
                        "fourth_card": self._card_to_dict(p.hand.fourth_card),
                    },
                    "class_card": self._card_to_dict(p.class_card),
                }
        return None

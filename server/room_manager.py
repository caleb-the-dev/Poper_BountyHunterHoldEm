import random as _stdlib_random
from typing import Optional


class RoomManager:
    def __init__(self):
        self._rooms: dict[str, list] = {}
        self._client_room: dict[object, str] = {}
        self._game_sessions: dict[str, object] = {}

    def create_room(self, client) -> str:
        code = self._unique_code()
        self._rooms[code] = [client]
        self._client_room[client] = code
        return code

    def join_room(self, code: str, client) -> bool:
        if code not in self._rooms:
            return False
        if len(self._rooms[code]) >= 8:
            return False
        # Reject new joiners if a game is already in progress on this room
        if code in self._game_sessions:
            return False
        self._rooms[code].append(client)
        self._client_room[client] = code
        return True

    def leave_room(self, client) -> None:
        code = self._client_room.pop(client, None)
        if code and code in self._rooms:
            self._rooms[code] = [c for c in self._rooms[code] if c is not client]
            if not self._rooms[code]:
                del self._rooms[code]
                self._game_sessions.pop(code, None)

    def get_players(self, code: str) -> list[str]:
        return [c.name for c in self._rooms.get(code, [])]

    def get_roommates(self, client) -> list:
        code = self._client_room.get(client)
        if not code:
            return []
        return [c for c in self._rooms[code] if c is not client]

    def get_room_code(self, client) -> str | None:
        return self._client_room.get(client)

    def get_host(self, code: str):
        """Return the first client in the room (the creator/host), or None if room doesn't exist."""
        room = self._rooms.get(code)
        if not room:
            return None
        return room[0]

    def get_clients(self, code: str) -> list:
        """Return a copy of the clients in a room, in join order. Empty list if unknown code."""
        return list(self._rooms.get(code, []))

    def get_player_id(self, client) -> str:
        """Canonical game-session player_id for a client — stable for the lifetime of the object."""
        return str(id(client))

    def start_game(self, host_client, card_set, rng: Optional[_stdlib_random.Random] = None):
        """Create a GameSession for the room. Only the host may call this.
        Raises ValueError if not host, already in progress, or fewer than 2 players."""
        from game_session import GameSession

        code = self._client_room.get(host_client)
        if not code:
            raise ValueError("Client is not in a room")
        if self.get_host(code) is not host_client:
            raise ValueError("Only the host can start the game")
        if code in self._game_sessions:
            raise ValueError("Game already in progress")
        room_clients = self._rooms[code]
        if len(room_clients) < 2:
            raise ValueError("Need at least 2 players to start")

        players = [(self.get_player_id(c), c.name) for c in room_clients]
        host_id = self.get_player_id(host_client)
        session = GameSession(
            room_code=code,
            host_id=host_id,
            players=players,
            card_set=card_set,
            rng=rng,
        )
        self._game_sessions[code] = session
        return session

    def get_game_session(self, code: str):
        """Return the active GameSession for a room code, or None."""
        return self._game_sessions.get(code)

    def get_game_session_for_client(self, client):
        """Return the active GameSession for whichever room a client is in, or None."""
        code = self._client_room.get(client)
        if not code:
            return None
        return self._game_sessions.get(code)

    def _unique_code(self) -> str:
        while True:
            code = str(_stdlib_random.randint(1000, 9999))
            if code not in self._rooms:
                return code

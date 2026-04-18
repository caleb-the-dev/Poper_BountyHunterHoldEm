import random


class RoomManager:
    def __init__(self):
        self._rooms: dict[str, list] = {}
        self._client_room: dict[object, str] = {}

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
        self._rooms[code].append(client)
        self._client_room[client] = code
        return True

    def leave_room(self, client) -> None:
        code = self._client_room.pop(client, None)
        if code and code in self._rooms:
            self._rooms[code] = [c for c in self._rooms[code] if c is not client]
            if not self._rooms[code]:
                del self._rooms[code]

    def get_players(self, code: str) -> list[str]:
        return [c.name for c in self._rooms.get(code, [])]

    def get_roommates(self, client) -> list:
        code = self._client_room.get(client)
        if not code:
            return []
        return [c for c in self._rooms[code] if c is not client]

    def get_room_code(self, client) -> str | None:
        return self._client_room.get(client)

    def _unique_code(self) -> str:
        while True:
            code = str(random.randint(1000, 9999))
            if code not in self._rooms:
                return code

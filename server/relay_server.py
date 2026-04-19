import asyncio
import json
import os
from websockets.asyncio.server import serve
from config import HOST, PORT
from room_manager import RoomManager
from card_data import load_all
from game_session import InvalidActionError

_manager = RoomManager()

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "csv_data")
_card_set = load_all(_DATA_DIR)


async def _send(ws, event: str, **kwargs) -> None:
    await ws.send(json.dumps({"event": event, **kwargs}))


async def _broadcast(clients: list, event: str, **kwargs) -> None:
    if clients:
        payload = json.dumps({"event": event, **kwargs})
        await asyncio.gather(*(c.send(payload) for c in clients))


async def _broadcast_game_state(code: str) -> None:
    """Broadcast full snapshot to every client in the room."""
    session = _manager.get_game_session(code)
    if session is None:
        return
    snap = session.snapshot()
    payload = json.dumps({"event": "game_state", **snap})
    clients = _manager.get_clients(code)
    if clients:
        await asyncio.gather(*(c.send(payload) for c in clients))


async def _send_private_hands(code: str) -> None:
    session = _manager.get_game_session(code)
    if session is None:
        return
    clients = _manager.get_clients(code)
    for client in clients:
        pid = _manager.get_player_id(client)
        priv = session.private_hand(pid)
        if priv is not None:
            await _send(client, "your_hand", **priv)


async def handler(ws) -> None:
    ws.name = None
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _send(ws, "error", message="Invalid JSON")
                continue

            action = msg.get("action")

            if action == "set_name":
                ws.name = str(msg.get("name", "")).strip()[:32] or "Anonymous"
                await _send(ws, "name_set", name=ws.name)
                print(f"[connect] {ws.name}")

            elif action == "create_room":
                if not ws.name:
                    await _send(ws, "error", message="Send set_name first")
                    continue
                code = _manager.create_room(ws)
                await _send(ws, "room_created", code=code)
                print(f"[room]    {ws.name} created {code}")

            elif action == "join_room":
                if not ws.name:
                    await _send(ws, "error", message="Send set_name first")
                    continue
                code = str(msg.get("code", ""))
                # Pre-check for in-game rejection to give a better error message
                if _manager.get_game_session(code) is not None:
                    await _send(ws, "error", message="Room is in-game — cannot join")
                    continue
                if not _manager.join_room(code, ws):
                    await _send(ws, "error", message="Room not found or full")
                    continue
                players = _manager.get_players(code)
                await _send(ws, "room_joined", code=code, players=players)
                await _broadcast(_manager.get_roommates(ws), "player_joined", name=ws.name)
                print(f"[room]    {ws.name} joined {code}")

            elif action == "chat":
                if not ws.name:
                    await _send(ws, "error", message="Send set_name first")
                    continue
                text = str(msg.get("text", ""))[:500]
                await _broadcast(_manager.get_roommates(ws), "chat", **{"from": ws.name, "text": text})
                print(f"[chat]    {ws.name}: {text}")

            elif action == "leave_room":
                session = _manager.get_game_session_for_client(ws)
                if session is not None:
                    session.on_player_disconnect(_manager.get_player_id(ws))
                roommates = _manager.get_roommates(ws)
                code = _manager.get_room_code(ws)
                _manager.leave_room(ws)
                await _broadcast(roommates, "player_left", name=ws.name)
                if code and _manager.get_game_session(code) is not None:
                    await _broadcast_game_state(code)
                print(f"[room]    {ws.name} left")

            elif action == "start_game":
                if not ws.name:
                    await _send(ws, "error", message="Send set_name first")
                    continue
                try:
                    _manager.start_game(ws, _card_set)
                except ValueError as e:
                    await _send(ws, "error", message=str(e))
                    continue
                code = _manager.get_room_code(ws)
                await _broadcast_game_state(code)
                await _send_private_hands(code)
                print(f"[game]    {ws.name} started game in {code}")

            elif action == "bet_action":
                if not ws.name:
                    await _send(ws, "error", message="Send set_name first")
                    continue
                session = _manager.get_game_session_for_client(ws)
                if session is None:
                    await _send(ws, "error", message="No game in progress")
                    continue
                player_id = _manager.get_player_id(ws)
                type_ = msg.get("type")
                amount = msg.get("amount")
                if not isinstance(type_, str):
                    await _send(ws, "error", message="Invalid bet action type")
                    continue
                if amount is not None and not isinstance(amount, int):
                    await _send(ws, "error", message="Invalid bet amount")
                    continue
                try:
                    session.apply_bet_action(player_id, type_, amount)
                except InvalidActionError as e:
                    await _send(ws, "error", message=str(e))
                    continue
                code = _manager.get_room_code(ws)
                await _broadcast_game_state(code)
                print(f"[bet]     {ws.name} {type_} {amount or ''} in {code}")

            else:
                await _send(ws, "error", message=f"Unknown action: {action}")

    finally:
        if ws.name:
            session = _manager.get_game_session_for_client(ws)
            if session is not None:
                session.on_player_disconnect(_manager.get_player_id(ws))
            roommates = _manager.get_roommates(ws)
            code = _manager.get_room_code(ws)
            _manager.leave_room(ws)
            await _broadcast(roommates, "player_left", name=ws.name)
            if code and _manager.get_game_session(code) is not None:
                await _broadcast_game_state(code)
            print(f"[disconnect] {ws.name}")


def run() -> None:
    async def _serve():
        print(f"Relay listening on ws://{HOST}:{PORT}")
        async with serve(handler, HOST, PORT):
            await asyncio.Future()  # run forever

    asyncio.run(_serve())


if __name__ == "__main__":
    run()

import asyncio
import json
from websockets.asyncio.server import serve
from config import HOST, PORT
from room_manager import RoomManager

_manager = RoomManager()


async def _send(ws, event: str, **kwargs) -> None:
    await ws.send(json.dumps({"event": event, **kwargs}))


async def _broadcast(clients: list, event: str, **kwargs) -> None:
    if clients:
        payload = json.dumps({"event": event, **kwargs})
        await asyncio.gather(*(c.send(payload) for c in clients))


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
                roommates = _manager.get_roommates(ws)
                _manager.leave_room(ws)
                await _broadcast(roommates, "player_left", name=ws.name)
                print(f"[room]    {ws.name} left")

            else:
                await _send(ws, "error", message=f"Unknown action: {action}")

    finally:
        if ws.name:
            roommates = _manager.get_roommates(ws)
            _manager.leave_room(ws)
            await _broadcast(roommates, "player_left", name=ws.name)
            print(f"[disconnect] {ws.name}")


def run() -> None:
    async def _serve():
        print(f"Relay listening on ws://{HOST}:{PORT}")
        async with serve(handler, HOST, PORT):
            await asyncio.Future()  # run forever

    asyncio.run(_serve())


if __name__ == "__main__":
    run()

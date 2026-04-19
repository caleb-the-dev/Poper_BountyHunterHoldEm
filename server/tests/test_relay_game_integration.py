import asyncio
import json
import os
import pytest
from websockets.asyncio.client import connect as ws_connect

from config import HOST, PORT

URL = f"ws://{HOST}:{PORT}"


async def _send(ws, obj):
    await ws.send(json.dumps(obj))


async def _recv(ws):
    return json.loads(await ws.recv())


async def _join_room_pair(names=("Alice", "Bob")):
    """Open two clients, create a room with client A, join with client B. Drain greeting events."""
    a = await ws_connect(URL)
    b = await ws_connect(URL)
    await _send(a, {"action": "set_name", "name": names[0]})
    await _recv(a)
    await _send(a, {"action": "create_room"})
    created = await _recv(a)
    code = created["code"]

    await _send(b, {"action": "set_name", "name": names[1]})
    await _recv(b)
    await _send(b, {"action": "join_room", "code": code})
    await _recv(b)                  # room_joined
    await _recv(a)                  # player_joined
    return a, b, code


async def _drain(ws, n):
    for _ in range(n):
        await _recv(ws)


# --- start_game ---

@pytest.mark.asyncio
async def test_start_game_broadcasts_game_state_to_both_players():
    a, b, _ = await _join_room_pair()
    try:
        await _send(a, {"action": "start_game"})
        ev_a = await _recv(a)
        ev_b = await _recv(b)
        assert ev_a["event"] == "game_state"
        assert ev_b["event"] == "game_state"
        assert ev_a["phase"] == "round_1"
    finally:
        await a.close()
        await b.close()

@pytest.mark.asyncio
async def test_start_game_sends_private_hand_to_each_player():
    a, b, _ = await _join_room_pair()
    try:
        await _send(a, {"action": "start_game"})
        # Expect: game_state + your_hand per client, in some order
        events_a = [await _recv(a) for _ in range(2)]
        events_b = [await _recv(b) for _ in range(2)]
        event_types_a = sorted([e["event"] for e in events_a])
        event_types_b = sorted([e["event"] for e in events_b])
        assert event_types_a == ["game_state", "your_hand"]
        assert event_types_b == ["game_state", "your_hand"]
    finally:
        await a.close()
        await b.close()

@pytest.mark.asyncio
async def test_start_game_rejected_from_non_host():
    a, b, _ = await _join_room_pair()
    try:
        await _send(b, {"action": "start_game"})  # b is not host
        err = await _recv(b)
        assert err["event"] == "error"
        assert "host" in err["message"].lower()
    finally:
        await a.close()
        await b.close()

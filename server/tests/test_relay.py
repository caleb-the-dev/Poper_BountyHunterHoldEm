import json
import pytest
from websockets.asyncio.client import connect
from config import PORT

URL = f"ws://localhost:{PORT}"


async def make_named_client(name: str):
    """Connect to relay and register a player name. Returns open websocket."""
    ws = await connect(URL)
    await ws.send(json.dumps({"action": "set_name", "name": name}))
    resp = json.loads(await ws.recv())
    assert resp["event"] == "name_set", f"Expected name_set, got {resp}"
    return ws


async def test_set_name():
    async with connect(URL) as ws:
        await ws.send(json.dumps({"action": "set_name", "name": "Alice"}))
        resp = json.loads(await ws.recv())
        assert resp["event"] == "name_set"
        assert resp["name"] == "Alice"


async def test_create_room_returns_4_digit_code():
    ws = await make_named_client("Alice")
    try:
        await ws.send(json.dumps({"action": "create_room"}))
        resp = json.loads(await ws.recv())
        assert resp["event"] == "room_created"
        assert len(resp["code"]) == 4
        assert resp["code"].isdigit()
    finally:
        await ws.close()


async def test_join_room_notifies_both_players():
    alice = await make_named_client("Alice")
    try:
        await alice.send(json.dumps({"action": "create_room"}))
        code = json.loads(await alice.recv())["code"]

        bob = await make_named_client("Bob")
        try:
            await bob.send(json.dumps({"action": "join_room", "code": code}))
            bob_resp = json.loads(await bob.recv())
            assert bob_resp["event"] == "room_joined"
            assert "Alice" in bob_resp["players"]

            alice_notif = json.loads(await alice.recv())
            assert alice_notif["event"] == "player_joined"
            assert alice_notif["name"] == "Bob"
        finally:
            await bob.close()
    finally:
        await alice.close()


async def test_join_invalid_room_returns_error():
    ws = await make_named_client("Charlie")
    try:
        await ws.send(json.dumps({"action": "join_room", "code": "0000"}))
        resp = json.loads(await ws.recv())
        assert resp["event"] == "error"
    finally:
        await ws.close()


async def test_chat_delivered_to_roommate():
    alice = await make_named_client("Alice")
    try:
        await alice.send(json.dumps({"action": "create_room"}))
        code = json.loads(await alice.recv())["code"]

        bob = await make_named_client("Bob")
        try:
            await bob.send(json.dumps({"action": "join_room", "code": code}))
            await bob.recv()   # room_joined
            await alice.recv() # player_joined

            await alice.send(json.dumps({"action": "chat", "text": "hello bob"}))
            msg = json.loads(await bob.recv())
            assert msg["event"] == "chat"
            assert msg["from"] == "Alice"
            assert msg["text"] == "hello bob"
        finally:
            await bob.close()
    finally:
        await alice.close()


async def test_chat_not_echoed_to_sender():
    alice = await make_named_client("Alice")
    try:
        await alice.send(json.dumps({"action": "create_room"}))
        code = json.loads(await alice.recv())["code"]

        bob = await make_named_client("Bob")
        try:
            await bob.send(json.dumps({"action": "join_room", "code": code}))
            await bob.recv()
            await alice.recv()

            await alice.send(json.dumps({"action": "chat", "text": "test"}))
            import asyncio
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(alice.recv(), timeout=0.5)
        finally:
            await bob.close()
    finally:
        await alice.close()


async def test_disconnect_notifies_roommate():
    import asyncio
    alice = await make_named_client("Alice")
    try:
        await alice.send(json.dumps({"action": "create_room"}))
        code = json.loads(await alice.recv())["code"]

        bob = await make_named_client("Bob")
        await bob.send(json.dumps({"action": "join_room", "code": code}))
        await bob.recv()   # room_joined
        await alice.recv() # player_joined

        await bob.close()

        notif = json.loads(await asyncio.wait_for(alice.recv(), timeout=2.0))
        assert notif["event"] == "player_left"
        assert notif["name"] == "Bob"
    finally:
        await alice.close()

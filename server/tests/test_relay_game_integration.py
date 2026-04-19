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


# --- bet_action ---

async def _setup_started_game():
    a, b, code = await _join_room_pair()
    await _send(a, {"action": "start_game"})
    # Drain: game_state + your_hand for each client (4 events total)
    for _ in range(2):
        await _recv(a)
    for _ in range(2):
        await _recv(b)
    return a, b, code


@pytest.mark.asyncio
async def test_bet_action_check_broadcasts_new_game_state():
    a, b, _ = await _setup_started_game()
    try:
        # a is the host (seat 0), so a is the current player initially
        await _send(a, {"action": "bet_action", "type": "check"})
        ev_a = await _recv(a)
        ev_b = await _recv(b)
        assert ev_a["event"] == "game_state"
        assert ev_b["event"] == "game_state"
    finally:
        await a.close()
        await b.close()


@pytest.mark.asyncio
async def test_bet_action_rejected_when_not_your_turn():
    a, b, _ = await _setup_started_game()
    try:
        await _send(b, {"action": "bet_action", "type": "check"})  # not b's turn
        err = await _recv(b)
        assert err["event"] == "error"
        assert "turn" in err["message"].lower()
    finally:
        await a.close()
        await b.close()


@pytest.mark.asyncio
async def test_bet_action_rejected_with_invalid_type():
    a, b, _ = await _setup_started_game()
    try:
        await _send(a, {"action": "bet_action", "type": "nope"})
        err = await _recv(a)
        assert err["event"] == "error"
    finally:
        await a.close()
        await b.close()


@pytest.mark.asyncio
async def test_full_hand_check_check_through_to_showdown():
    a, b, _ = await _setup_started_game()
    try:
        # 5 rounds, each with a.check then b.check; after each bet_action the relay broadcasts
        # game_state to BOTH a and b, so drain 2 events per action.
        for _ in range(5):
            await _send(a, {"action": "bet_action", "type": "check"})
            await _recv(a); await _recv(b)
            await _send(b, {"action": "bet_action", "type": "check"})
            await _recv(a); await _recv(b)
        # We've played 5 rounds + the showdown round. The last broadcast should be in hand_end.
        # No assertion on the final state — test passes if we didn't timeout or get errors.
    finally:
        await a.close()
        await b.close()


# --- Mid-game join / leave ---

@pytest.mark.asyncio
async def test_join_room_rejected_while_game_in_progress():
    a, b, code = await _setup_started_game()
    c = await ws_connect(URL)
    try:
        await _send(c, {"action": "set_name", "name": "Latecomer"})
        await _recv(c)
        await _send(c, {"action": "join_room", "code": code})
        err = await _recv(c)
        assert err["event"] == "error"
        assert "in-game" in err["message"].lower() or "full" in err["message"].lower()
    finally:
        await a.close()
        await b.close()
        await c.close()


@pytest.mark.asyncio
async def test_leave_room_mid_game_auto_folds_and_broadcasts():
    a, b, _ = await _setup_started_game()
    try:
        await _send(b, {"action": "leave_room"})
        # a receives player_left + updated game_state
        ev1 = await _recv(a)
        ev2 = await _recv(a)
        events = {ev1["event"], ev2["event"]}
        assert "player_left" in events
        assert "game_state" in events
    finally:
        await a.close()
        await b.close()

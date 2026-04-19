"""
Smoke test: connect two WebSocket clients to a running local relay and play a
full hand end-to-end with a simple check/call strategy. Prints every server
event and the final showdown.

Usage:
    1. In one terminal:  python start_dev.py   (or /start-server)
    2. In another:       python scripts/smoke_test_game.py

Requires: websockets library (same one used by the relay).
"""
import asyncio
import json
import sys

from websockets.asyncio.client import connect

URL = "ws://127.0.0.1:8765"


async def send(ws, obj):
    await ws.send(json.dumps(obj))


async def recv(ws):
    return json.loads(await ws.recv())


def pretty(event: dict) -> str:
    etype = event.get("event", "?")
    if etype == "game_state":
        phase = event.get("phase")
        cur = event.get("current_player_id")
        pot = event.get("pot")
        cb = event.get("current_bet")
        return f"[game_state] phase={phase} turn={cur} pot={pot} bet={cb}"
    return json.dumps(event, indent=2)


async def play_client(ws, name: str, role: str, code_holder: dict):
    await send(ws, {"action": "set_name", "name": name})
    print(f"[{name}] << {pretty(await recv(ws))}")

    if role == "host":
        await send(ws, {"action": "create_room"})
        created = await recv(ws)
        print(f"[{name}] << {pretty(created)}")
        code_holder["code"] = created["code"]
    else:
        while "code" not in code_holder:
            await asyncio.sleep(0.05)
        await send(ws, {"action": "join_room", "code": code_holder["code"]})
        print(f"[{name}] << {pretty(await recv(ws))}")


async def play_hand(ws_a, ws_b):
    await send(ws_a, {"action": "start_game"})

    first_a = await recv(ws_a)
    first_b = await recv(ws_b)
    print(f"[A] << {pretty(first_a)}")
    print(f"[B] << {pretty(first_b)}")
    ids = [p["player_id"] for p in first_a["players"]]
    my_pid_map = {"A": ids[0], "B": ids[1]}

    hand_a = await recv(ws_a)
    hand_b = await recv(ws_b)
    print(f"[A] << your_hand: {hand_a.get('class_card', {}).get('name')}")
    print(f"[B] << your_hand: {hand_b.get('class_card', {}).get('name')}")

    async def auto_play(ws, name):
        while True:
            ev = await recv(ws)
            print(f"[{name}] << {pretty(ev)}")
            if ev.get("event") != "game_state":
                continue
            if ev.get("phase") == "hand_end":
                print(f"[{name}] FINAL showdown: {ev.get('showdown')}")
                return
            my_pid = my_pid_map.get(name)
            if ev.get("current_player_id") != my_pid:
                continue
            cb = ev.get("current_bet", 0)
            action = {"action": "bet_action", "type": "check" if cb == 0 else "call"}
            await send(ws, action)
            print(f"[{name}] >> {action}")

    cb = first_a.get("current_bet", 0)
    if first_a.get("current_player_id") == my_pid_map["A"]:
        await send(ws_a, {"action": "bet_action", "type": "check" if cb == 0 else "call"})
        print(f"[A] >> check")

    await asyncio.gather(auto_play(ws_a, "A"), auto_play(ws_b, "B"))


async def main():
    code_holder: dict = {}
    ws_a = await connect(URL)
    ws_b = await connect(URL)
    try:
        await play_client(ws_a, "Alice", "host", code_holder)
        await asyncio.sleep(0.1)
        await play_client(ws_b, "Bob", "join", code_holder)
        print(f"[Alice] << {pretty(await recv(ws_a))}")
        await play_hand(ws_a, ws_b)
    finally:
        await ws_a.close()
        await ws_b.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)

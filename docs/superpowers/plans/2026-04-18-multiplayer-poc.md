# Multiplayer POC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a WebSocket relay server + Godot 4 client so two players on separate machines can join a shared lobby by room code and exchange chat messages, with zero port forwarding.

**Architecture:** A Python asyncio WebSocket relay server manages rooms and routes messages between players. Godot 4 clients connect outbound to a public URL (local dev: ngrok tunnel). Three GDScript screens handle name entry, room create/join, and the live lobby. All game logic will eventually run server-side under this same authoritative-host model.

**Tech Stack:** Python 3.10+ · `websockets>=12.0` · `pytest>=8.0` · `pytest-asyncio>=0.23` · Godot 4 (latest stable) · GDScript

---

## Message Protocol

This is the contract between server and client. Every file in this plan depends on it — do not deviate.

**Client → Server (JSON):**

| `action` | extra fields | meaning |
|---|---|---|
| `set_name` | `name` | Register player name — must be first message sent |
| `create_room` | — | Create a room; server returns a code |
| `join_room` | `code` | Join room by 4-digit numeric code |
| `chat` | `text` | Send chat message to all room members |
| `leave_room` | — | Leave current room gracefully |

**Server → Client (JSON):**

| `event` | extra fields | meaning |
|---|---|---|
| `name_set` | `name` | Name accepted |
| `room_created` | `code` | Room created; here is the code |
| `room_joined` | `code`, `players` | Joined successfully; `players` is array of name strings |
| `player_joined` | `name` | Another player entered your room |
| `player_left` | `name` | A player left or disconnected |
| `chat` | `from`, `text` | Incoming chat |
| `error` | `message` | Something went wrong |

---

## File Map

```
Poper_BountyHunterHoldEm/
├── server/
│   ├── config.py                        # HOST, PORT — only place to change these
│   ├── requirements.txt                 # websockets, pytest, pytest-asyncio
│   ├── pytest.ini                       # asyncio_mode = auto
│   ├── room_manager.py                  # pure Python room logic, no WebSocket dependency
│   ├── relay_server.py                  # WebSocket handler wired to RoomManager
│   └── tests/
│       ├── __init__.py                  # empty
│       ├── conftest.py                  # starts server in background thread for integration tests
│       ├── test_room_manager.py         # unit tests — pure Python, no sockets
│       └── test_relay.py               # integration tests — real WebSocket connections
├── client/
│   ├── project.godot                    # declares autoloads, main scene
│   ├── autoload/
│   │   ├── config.gd                   # SERVER_URL constant (one line to change)
│   │   └── ws_client.gd                # WebSocketPeer wrapper, Autoload singleton
│   └── scenes/
│       ├── main.tscn                   # root scene: bare Control + main.gd
│       ├── main.gd                     # screen switcher
│       └── screens/
│           ├── name_entry.gd           # Screen 1: enter player name
│           ├── main_menu.gd            # Screen 2: create or join room
│           └── lobby.gd                # Screen 3: live player list + chat
└── TESTING.md                          # step-by-step instructions for end-to-end test
```

---

### Task 1: Server scaffolding

**Files:**
- Create: `server/config.py`
- Create: `server/requirements.txt`
- Create: `server/pytest.ini`
- Create: `server/tests/__init__.py`

- [ ] **Step 1: Create `server/config.py`**

```python
HOST = "localhost"
PORT = 8765
```

- [ ] **Step 2: Create `server/requirements.txt`**

```
websockets>=12.0
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 3: Create `server/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 4: Create `server/tests/__init__.py`**

Empty file — no content needed.

- [ ] **Step 5: Install dependencies**

```bash
cd server
pip install -r requirements.txt
```

Expected: all packages install without error.

- [ ] **Step 6: Commit**

```bash
git add server/config.py server/requirements.txt server/pytest.ini server/tests/__init__.py
git commit -m "feat: server scaffolding and dependencies"
```

---

### Task 2: RoomManager — tests then implementation

**Files:**
- Create: `server/tests/test_room_manager.py`
- Create: `server/room_manager.py`

- [ ] **Step 1: Write failing tests**

Create `server/tests/test_room_manager.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from room_manager import RoomManager


class FakeClient:
    def __init__(self, name="Alice"):
        self.name = name


@pytest.fixture
def rm():
    return RoomManager()


def test_create_room_returns_4_digit_code(rm):
    code = rm.create_room(FakeClient("Alice"))
    assert len(code) == 4
    assert code.isdigit()


def test_create_room_codes_are_unique(rm):
    codes = {rm.create_room(FakeClient(f"P{i}")) for i in range(20)}
    assert len(codes) == 20


def test_join_room_valid_code(rm):
    code = rm.create_room(FakeClient("Host"))
    assert rm.join_room(code, FakeClient("Joiner")) is True


def test_join_room_invalid_code(rm):
    assert rm.join_room("0000", FakeClient("Joiner")) is False


def test_join_room_max_8_players(rm):
    clients = [FakeClient(f"P{i}") for i in range(9)]
    code = rm.create_room(clients[0])
    for c in clients[1:8]:
        rm.join_room(code, c)
    assert rm.join_room(code, clients[8]) is False


def test_get_players_lists_all_names(rm):
    host = FakeClient("Host")
    code = rm.create_room(host)
    rm.join_room(code, FakeClient("Joiner"))
    players = rm.get_players(code)
    assert "Host" in players
    assert "Joiner" in players


def test_leave_room_removes_player(rm):
    host = FakeClient("Host")
    joiner = FakeClient("Joiner")
    code = rm.create_room(host)
    rm.join_room(code, joiner)
    rm.leave_room(joiner)
    assert "Joiner" not in rm.get_players(code)


def test_leave_room_empty_room_is_cleaned_up(rm):
    host = FakeClient("Host")
    code = rm.create_room(host)
    rm.leave_room(host)
    assert rm.get_room_code(host) is None


def test_get_room_code_for_client(rm):
    host = FakeClient("Host")
    code = rm.create_room(host)
    assert rm.get_room_code(host) == code


def test_get_roommates_excludes_self(rm):
    host = FakeClient("Host")
    joiner = FakeClient("Joiner")
    code = rm.create_room(host)
    rm.join_room(code, joiner)
    roommates = rm.get_roommates(host)
    assert joiner in roommates
    assert host not in roommates


def test_get_roommates_returns_empty_when_not_in_room(rm):
    assert rm.get_roommates(FakeClient("Nobody")) == []
```

- [ ] **Step 2: Run — confirm all tests fail**

```bash
cd server
pytest tests/test_room_manager.py -v
```

Expected: `ModuleNotFoundError: No module named 'room_manager'`

- [ ] **Step 3: Implement RoomManager**

Create `server/room_manager.py`:

```python
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
```

- [ ] **Step 4: Run — confirm all tests pass**

```bash
cd server
pytest tests/test_room_manager.py -v
```

Expected: 11 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add server/room_manager.py server/tests/test_room_manager.py
git commit -m "feat: RoomManager with full unit test coverage"
```

---

### Task 3: Relay server — tests then implementation

**Files:**
- Create: `server/tests/conftest.py`
- Create: `server/tests/test_relay.py`
- Create: `server/relay_server.py`

- [ ] **Step 1: Create the test conftest**

Create `server/tests/conftest.py`:

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import threading
import time


@pytest.fixture(scope="session", autouse=True)
def start_relay_server():
    import relay_server
    t = threading.Thread(target=relay_server.run, daemon=True)
    t.start()
    time.sleep(0.4)  # give server time to bind port
    yield
```

- [ ] **Step 2: Write failing integration tests**

Create `server/tests/test_relay.py`:

```python
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
            # Alice should not receive her own message back
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
```

- [ ] **Step 3: Run — confirm all tests fail**

```bash
cd server
pytest tests/test_relay.py -v
```

Expected: `ModuleNotFoundError: No module named 'relay_server'`

- [ ] **Step 4: Implement relay_server.py**

Create `server/relay_server.py`:

```python
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
```

- [ ] **Step 5: Run — confirm all tests pass**

```bash
cd server
pytest tests/test_relay.py -v
```

Expected: 7 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add server/relay_server.py server/tests/conftest.py server/tests/test_relay.py
git commit -m "feat: WebSocket relay server with integration tests"
```

---

### Task 4: Godot project scaffold + autoloads

**Files:**
- Create: `client/project.godot`
- Create: `client/autoload/config.gd`
- Create: `client/autoload/ws_client.gd`

- [ ] **Step 1: Create `client/project.godot`**

```ini
; Engine configuration file.
config_version=5

[application]

config/name="Poper BountyHunter PoC"
run/main_scene="res://scenes/main.tscn"
config/features=PackedStringArray("4.3", "Forward Plus")

[autoload]

Config="*res://autoload/config.gd"
WsClient="*res://autoload/ws_client.gd"

[display]

window/size/viewport_width=1152
window/size/viewport_height=648
```

- [ ] **Step 2: Create `client/autoload/config.gd`**

```gdscript
extends Node

# Change this one line to switch between local dev and ngrok.
# Local:  ws://localhost:8765
# ngrok:  wss://xxxx-xx-xx-xx-xx.ngrok-free.app
const SERVER_URL: String = "ws://localhost:8765"
```

- [ ] **Step 3: Create `client/autoload/ws_client.gd`**

```gdscript
extends Node

signal connected
signal disconnected
signal message_received(data: Dictionary)

var _socket: WebSocketPeer = null
var _is_connected: bool = false


func connect_to_server(url: String) -> void:
    _socket = WebSocketPeer.new()
    var err := _socket.connect_to_url(url)
    if err != OK:
        push_error("WsClient: failed to initiate connection to " + url)


func send_message(data: Dictionary) -> void:
    if _socket == null or not _is_connected:
        push_error("WsClient: send called while not connected")
        return
    _socket.send_text(JSON.stringify(data))


func disconnect_from_server() -> void:
    if _socket != null:
        _socket.close()


func _process(_delta: float) -> void:
    if _socket == null:
        return
    _socket.poll()
    match _socket.get_ready_state():
        WebSocketPeer.STATE_OPEN:
            if not _is_connected:
                _is_connected = true
                connected.emit()
            while _socket.get_available_packet_count() > 0:
                var raw := _socket.get_packet().get_string_from_utf8()
                var parsed = JSON.parse_string(raw)
                if parsed != null:
                    message_received.emit(parsed)
        WebSocketPeer.STATE_CLOSING:
            pass
        WebSocketPeer.STATE_CLOSED:
            if _is_connected:
                _is_connected = false
                disconnected.emit()
            _socket = null
```

- [ ] **Step 4: Commit**

```bash
git add client/project.godot client/autoload/config.gd client/autoload/ws_client.gd
git commit -m "feat: Godot project with WebSocket autoload singleton"
```

---

### Task 5: Main scene (screen switcher)

**Files:**
- Create: `client/scenes/main.tscn`
- Create: `client/scenes/main.gd`

- [ ] **Step 1: Create `client/scenes/main.tscn`**

```
[gd_scene load_steps=2 format=3 uid="uid://pocmain0001"]

[ext_resource type="Script" path="res://scenes/main.gd" id="1_pocmain"]

[node name="Main" type="Control"]
layout_mode = 3
anchors_preset = 15
anchor_right = 1.0
anchor_bottom = 1.0
grow_horizontal = 2
grow_vertical = 2
script = ExtResource("1_pocmain")
```

- [ ] **Step 2: Create `client/scenes/main.gd`**

```gdscript
extends Control

var _current_screen: Control = null
var _player_name: String = ""


func _ready() -> void:
    _show_name_entry()


func _show_name_entry() -> void:
    var screen: Control = load("res://scenes/screens/name_entry.gd").new()
    screen.name_confirmed.connect(_on_name_confirmed)
    _swap(screen)


func _show_main_menu() -> void:
    var screen: Control = load("res://scenes/screens/main_menu.gd").new()
    screen.player_name = _player_name
    screen.room_created.connect(_on_room_created)
    screen.room_joined.connect(_on_room_joined)
    _swap(screen)


func _show_lobby(room_code: String, players: Array) -> void:
    var screen: Control = load("res://scenes/screens/lobby.gd").new()
    screen.player_name = _player_name
    screen.room_code = room_code
    screen.initial_players = players
    screen.left_room.connect(_on_left_room)
    _swap(screen)


func _swap(new_screen: Control) -> void:
    if _current_screen != null:
        _current_screen.queue_free()
    _current_screen = new_screen
    add_child(_current_screen)
    _current_screen.set_anchors_preset(Control.PRESET_FULL_RECT)


func _on_name_confirmed(player_name: String) -> void:
    _player_name = player_name
    _show_main_menu()


func _on_room_created(room_code: String) -> void:
    _show_lobby(room_code, [_player_name])


func _on_room_joined(room_code: String, players: Array) -> void:
    _show_lobby(room_code, players)


func _on_left_room() -> void:
    WsClient.disconnect_from_server()
    _show_main_menu()
```

- [ ] **Step 3: Commit**

```bash
git add client/scenes/main.tscn client/scenes/main.gd
git commit -m "feat: main scene screen switcher"
```

---

### Task 6: Name Entry screen

**Files:**
- Create: `client/scenes/screens/name_entry.gd`

- [ ] **Step 1: Create `client/scenes/screens/name_entry.gd`**

```gdscript
extends Control

signal name_confirmed(player_name: String)

var _name_input: LineEdit
var _continue_btn: Button


func _ready() -> void:
    var center := CenterContainer.new()
    center.set_anchors_preset(Control.PRESET_FULL_RECT)
    add_child(center)

    var vbox := VBoxContainer.new()
    vbox.custom_minimum_size = Vector2(400, 0)
    center.add_child(vbox)

    var title := Label.new()
    title.text = "Poper: Bounty Hunter Hold'em"
    title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    vbox.add_child(title)

    vbox.add_child(_spacer(24))

    var lbl := Label.new()
    lbl.text = "Enter your name:"
    vbox.add_child(lbl)

    _name_input = LineEdit.new()
    _name_input.placeholder_text = "Your name"
    _name_input.max_length = 32
    _name_input.text_changed.connect(_on_text_changed)
    _name_input.text_submitted.connect(func(_t): _submit())
    vbox.add_child(_name_input)

    vbox.add_child(_spacer(8))

    _continue_btn = Button.new()
    _continue_btn.text = "Continue"
    _continue_btn.disabled = true
    _continue_btn.pressed.connect(_submit)
    vbox.add_child(_continue_btn)


func _spacer(height: int) -> Control:
    var s := Control.new()
    s.custom_minimum_size = Vector2(0, height)
    return s


func _on_text_changed(text: String) -> void:
    _continue_btn.disabled = text.strip_edges().is_empty()


func _submit() -> void:
    var name := _name_input.text.strip_edges()
    if not name.is_empty():
        name_confirmed.emit(name)
```

- [ ] **Step 2: Commit**

```bash
git add client/scenes/screens/name_entry.gd
git commit -m "feat: name entry screen"
```

---

### Task 7: Main Menu screen

**Files:**
- Create: `client/scenes/screens/main_menu.gd`

- [ ] **Step 1: Create `client/scenes/screens/main_menu.gd`**

```gdscript
extends Control

signal room_created(room_code: String)
signal room_joined(room_code: String, players: Array)

var player_name: String = ""

var _url_input: LineEdit
var _code_input: LineEdit
var _status_label: Label
var _pending_action: String = ""   # "create" or "join"
var _pending_code: String = ""


func _ready() -> void:
    WsClient.message_received.connect(_on_message)
    WsClient.disconnected.connect(func(): _set_status("Disconnected from server."))
    _build_ui()


func _build_ui() -> void:
    var center := CenterContainer.new()
    center.set_anchors_preset(Control.PRESET_FULL_RECT)
    add_child(center)

    var vbox := VBoxContainer.new()
    vbox.custom_minimum_size = Vector2(520, 0)
    center.add_child(vbox)

    var title := Label.new()
    title.text = "Welcome, " + player_name
    title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    vbox.add_child(title)

    vbox.add_child(_spacer(20))

    var url_lbl := Label.new()
    url_lbl.text = "Server URL:"
    vbox.add_child(url_lbl)

    _url_input = LineEdit.new()
    _url_input.text = Config.SERVER_URL
    vbox.add_child(_url_input)

    vbox.add_child(_spacer(12))

    var create_btn := Button.new()
    create_btn.text = "Create Room"
    create_btn.pressed.connect(_on_create_pressed)
    vbox.add_child(create_btn)

    vbox.add_child(_spacer(12))

    var join_row := HBoxContainer.new()
    vbox.add_child(join_row)

    _code_input = LineEdit.new()
    _code_input.placeholder_text = "4-digit room code"
    _code_input.max_length = 4
    _code_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    join_row.add_child(_code_input)

    var join_btn := Button.new()
    join_btn.text = "Join Room"
    join_btn.pressed.connect(_on_join_pressed)
    join_row.add_child(join_btn)

    vbox.add_child(_spacer(12))

    _status_label = Label.new()
    _status_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
    _status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    vbox.add_child(_status_label)


func _spacer(height: int) -> Control:
    var s := Control.new()
    s.custom_minimum_size = Vector2(0, height)
    return s


func _set_status(msg: String) -> void:
    _status_label.text = msg


func _on_create_pressed() -> void:
    _pending_action = "create"
    _pending_code = ""
    _set_status("Connecting...")
    WsClient.connected.connect(_on_ws_connected, CONNECT_ONE_SHOT)
    WsClient.connect_to_server(_url_input.text.strip_edges())


func _on_join_pressed() -> void:
    var code := _code_input.text.strip_edges()
    if code.length() != 4 or not code.is_numeric():
        _set_status("Please enter a valid 4-digit room code.")
        return
    _pending_action = "join"
    _pending_code = code
    _set_status("Connecting...")
    WsClient.connected.connect(_on_ws_connected, CONNECT_ONE_SHOT)
    WsClient.connect_to_server(_url_input.text.strip_edges())


func _on_ws_connected() -> void:
    WsClient.send_message({"action": "set_name", "name": player_name})


func _on_message(data: Dictionary) -> void:
    match data.get("event"):
        "name_set":
            if _pending_action == "create":
                WsClient.send_message({"action": "create_room"})
            elif _pending_action == "join":
                WsClient.send_message({"action": "join_room", "code": _pending_code})
        "room_created":
            _pending_action = ""
            room_created.emit(data["code"])
        "room_joined":
            _pending_action = ""
            room_joined.emit(data["code"], data.get("players", []))
        "error":
            _set_status("Error: " + data.get("message", "unknown error"))
            _pending_action = ""
```

- [ ] **Step 2: Commit**

```bash
git add client/scenes/screens/main_menu.gd
git commit -m "feat: main menu screen (create/join room)"
```

---

### Task 8: Lobby screen

**Files:**
- Create: `client/scenes/screens/lobby.gd`

- [ ] **Step 1: Create `client/scenes/screens/lobby.gd`**

```gdscript
extends Control

signal left_room

var player_name: String = ""
var room_code: String = ""
var initial_players: Array = []

var _player_list: VBoxContainer
var _chat_log: VBoxContainer
var _chat_scroll: ScrollContainer
var _chat_input: LineEdit


func _ready() -> void:
    WsClient.message_received.connect(_on_message)
    WsClient.disconnected.connect(func(): _add_chat("[Server]", "Connection lost."))
    _build_ui()
    for p in initial_players:
        _add_player_label(p)


func _build_ui() -> void:
    var root := VBoxContainer.new()
    root.set_anchors_preset(Control.PRESET_FULL_RECT)
    add_child(root)

    # Header row
    var header := HBoxContainer.new()
    root.add_child(header)

    var room_lbl := Label.new()
    room_lbl.text = "Room: " + room_code
    room_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    header.add_child(room_lbl)

    var leave_btn := Button.new()
    leave_btn.text = "Leave Room"
    leave_btn.pressed.connect(_on_leave_pressed)
    header.add_child(leave_btn)

    # Body: player list (left) + chat (right)
    var body := HBoxContainer.new()
    body.size_flags_vertical = Control.SIZE_EXPAND_FILL
    root.add_child(body)

    # --- Player list panel ---
    var player_panel := VBoxContainer.new()
    player_panel.custom_minimum_size = Vector2(200, 0)
    body.add_child(player_panel)

    var players_lbl := Label.new()
    players_lbl.text = "Players"
    player_panel.add_child(players_lbl)

    _player_list = VBoxContainer.new()
    _player_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
    player_panel.add_child(_player_list)

    # --- Chat panel ---
    var chat_panel := VBoxContainer.new()
    chat_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    body.add_child(chat_panel)

    var chat_lbl := Label.new()
    chat_lbl.text = "Chat"
    chat_panel.add_child(chat_lbl)

    _chat_scroll = ScrollContainer.new()
    _chat_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
    chat_panel.add_child(_chat_scroll)

    _chat_log = VBoxContainer.new()
    _chat_log.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    _chat_scroll.add_child(_chat_log)

    var input_row := HBoxContainer.new()
    chat_panel.add_child(input_row)

    _chat_input = LineEdit.new()
    _chat_input.placeholder_text = "Type a message..."
    _chat_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
    _chat_input.text_submitted.connect(func(t): _send_chat(t))
    input_row.add_child(_chat_input)

    var send_btn := Button.new()
    send_btn.text = "Send"
    send_btn.pressed.connect(func(): _send_chat(_chat_input.text))
    input_row.add_child(send_btn)


func _add_player_label(name: String) -> void:
    var lbl := Label.new()
    lbl.text = "• " + name
    lbl.name = "p_" + name
    _player_list.add_child(lbl)


func _remove_player_label(name: String) -> void:
    var node := _player_list.find_child("p_" + name, false, false)
    if node:
        node.queue_free()


func _add_chat(from: String, text: String) -> void:
    var lbl := Label.new()
    lbl.text = from + ": " + text
    lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
    _chat_log.add_child(lbl)
    _scroll_to_bottom()


func _scroll_to_bottom() -> void:
    await get_tree().process_frame
    if is_instance_valid(_chat_scroll):
        _chat_scroll.scroll_vertical = int(_chat_scroll.get_v_scroll_bar().max_value)


func _send_chat(text: String) -> void:
    text = text.strip_edges()
    if text.is_empty():
        return
    WsClient.send_message({"action": "chat", "text": text})
    _add_chat(player_name, text)
    _chat_input.text = ""


func _on_leave_pressed() -> void:
    WsClient.send_message({"action": "leave_room"})
    left_room.emit()


func _on_message(data: Dictionary) -> void:
    match data.get("event"):
        "player_joined":
            _add_player_label(data["name"])
            _add_chat("[Server]", data["name"] + " joined.")
        "player_left":
            _remove_player_label(data["name"])
            _add_chat("[Server]", data["name"] + " left.")
        "chat":
            _add_chat(data.get("from", "?"), data.get("text", ""))
```

- [ ] **Step 2: Commit**

```bash
git add client/scenes/screens/lobby.gd
git commit -m "feat: lobby screen with player list and chat"
```

---

### Task 9: TESTING.md + end-to-end verification

**Files:**
- Create: `TESTING.md`

- [ ] **Step 1: Create `TESTING.md`**

```markdown
# Multiplayer POC — Test Instructions

## Prerequisites
- Python 3.10+
- Godot 4 (latest stable) installed
- ngrok installed and authenticated (`ngrok config add-authtoken <your-token>`)

## 1. Start the relay server

```bash
cd server
pip install -r requirements.txt
python relay_server.py
```

Expected output:
```
Relay listening on ws://localhost:8765
```

## 2. Run automated tests

In a second terminal:

```bash
cd server
pytest -v
```

Expected: all tests pass.

## 3. Expose via ngrok (for cross-machine testing)

```bash
ngrok http 8765
```

ngrok will print a Forwarding line like:
```
Forwarding  https://abc1-23-45-67-89.ngrok-free.app -> http://localhost:8765
```

Copy that URL and change `https://` to `wss://`:
```
wss://abc1-23-45-67-89.ngrok-free.app
```

## 4. Update the Godot client

Open `client/autoload/config.gd` and set:

```gdscript
const SERVER_URL: String = "wss://abc1-23-45-67-89.ngrok-free.app"
```

For local-only testing (both players on the same machine), leave it as `ws://localhost:8765`.

## 5. Open the Godot project

- Open Godot 4
- Import project from the `client/` directory
- Press F5 (or the Play button) to run

## 6. End-to-end test (two players)

**Machine A:**
1. Enter name → Continue
2. Click "Create Room"
3. Note the 4-digit room code shown in the lobby

**Machine B:**
1. Enter name → Continue
2. Paste the ngrok WSS URL into the Server URL field (if not already set in config.gd)
3. Type the room code → Join Room
4. Machine A should see Machine B's name appear in the player list

**Chat test:**
- Type a message on either machine → click Send
- Message should appear on the other machine within ~1 second

**Disconnect test:**
- Close one client window
- The other player should see a "[Server]: [name] left." message

## Success Criteria

- [ ] Both players see each other in the player list
- [ ] Chat messages are delivered in ~1 second
- [ ] Closing one client notifies the other
- [ ] No port forwarding was configured on either machine
```

- [ ] **Step 2: Commit**

```bash
git add TESTING.md
git commit -m "docs: end-to-end testing instructions"
```

---

### Task 10: Post-build documentation updates

Run the verification skill before this task. Only mark success after the end-to-end test passes.

**Files to update:**
- `docs/map_directories/lobby_networking.md`
- `docs/map_directories/map.md`
- `CLAUDE.md`

- [ ] **Step 1: Update `docs/map_directories/lobby_networking.md`**

Replace the entire file with accurate post-build content. Fill in:
- Architecture section: WebSocket relay model, why it was chosen (zero port forwarding, matches authoritative-host design, easy cloud deployment)
- Signals / Events: every signal from `ws_client.gd` (`connected`, `disconnected`, `message_received`)
- Public API: `WsClient.connect_to_server(url)`, `WsClient.send_message(data)`, `WsClient.disconnect_from_server()`
- Key Patterns & Gotchas: anything discovered during implementation that would surprise a future developer
- Recent Changes: dated entry for this session

- [ ] **Step 2: Update `docs/map_directories/map.md`**

- Add `server/` and `client/` to the file tree
- Add a session log entry dated today summarizing what was built
- Update Lobby / Networking status to ✅ Built

- [ ] **Step 3: Update `CLAUDE.md`**

- Engine line: `Godot 4`
- Repo line: `https://github.com/caleb-the-dev/Poper_BountyHunterHoldEm.git`
- Lobby / Networking row in Key Systems table: status `✅ Built`
- Current Build State section: update Working to reflect the relay server + lobby POC

- [ ] **Step 4: Commit**

```bash
git add docs/map_directories/lobby_networking.md docs/map_directories/map.md CLAUDE.md
git commit -m "docs: post-build map and CLAUDE.md updates"
```

- [ ] **Step 5: Push**

```bash
git push origin main
```

---

## Self-Review

**Spec coverage check:**
- ✅ Player A creates lobby → gets 4-digit room code (Task 3 server + Task 7 client)
- ✅ Player B joins by code (Task 3 server + Task 7 client)
- ✅ Both see live player list (Task 8 lobby screen)
- ✅ Chat messages delivered in real time (Task 3 server + Task 8 client)
- ✅ Zero port forwarding (WebSocket outbound only, ngrok tunnel)
- ✅ Disconnect notification (Task 3 `finally` block + Task 8 `player_left` handler)
- ✅ Max 8 players (Task 2 RoomManager)
- ✅ SERVER_URL in one place only (Task 4 config.gd)
- ✅ TESTING.md (Task 9)
- ✅ Post-build doc updates (Task 10)

**Type/name consistency check:**
- `room_created(room_code: String)` — emitted in main_menu.gd, received in main.gd ✅
- `room_joined(room_code: String, players: Array)` — emitted in main_menu.gd, received in main.gd ✅
- `left_room` — emitted in lobby.gd, received in main.gd ✅
- `WsClient.send_message` — called in main_menu.gd and lobby.gd, defined in ws_client.gd ✅
- `WsClient.connected` signal — used in main_menu.gd, defined in ws_client.gd ✅
- `player_name` var — set in main.gd, passed to each screen before `_swap()` ✅

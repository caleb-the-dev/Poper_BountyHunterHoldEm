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

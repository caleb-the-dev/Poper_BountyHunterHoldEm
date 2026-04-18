"""
Dev startup: launches relay server + ngrok, patches config.gd with the live wss:// URL,
and restores config.gd to localhost on exit (Ctrl+C or error).
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.join(REPO_ROOT, "server")
CONFIG_PATH = os.path.join(REPO_ROOT, "client", "autoload", "config.gd")
NGROK_API = "http://127.0.0.1:4040/api/tunnels"
LOCAL_URL = "ws://localhost:8765"
POLL_INTERVAL = 1.0   # seconds between ngrok API checks
POLL_TIMEOUT = 30.0   # seconds before giving up


CONFIG_TEMPLATE = """\
extends Node

# Change this one line to switch between local dev and ngrok.
# Local:  ws://localhost:8765
# ngrok:  wss://xxxx-xx-xx-xx-xx.ngrok-free.app
const SERVER_URL: String = "{url}"
"""


def write_config(url: str) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(CONFIG_TEMPLATE.format(url=url))


def poll_ngrok_url(timeout: float) -> str:
    """Block until ngrok exposes a public https tunnel, then return the wss:// URL."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(NGROK_API, timeout=2) as resp:
                data = json.loads(resp.read())
            for tunnel in data.get("tunnels", []):
                public_url: str = tunnel.get("public_url", "")
                if public_url.startswith("https://"):
                    return "wss://" + public_url[len("https://"):]
        except (urllib.error.URLError, json.JSONDecodeError):
            pass
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"ngrok tunnel not available after {timeout}s")


def main() -> None:
    relay_proc = None
    ngrok_proc = None

    def cleanup(signum=None, frame=None) -> None:
        print("\n[start_dev] Shutting down...")
        for proc in (relay_proc, ngrok_proc):
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        print(f"[start_dev] Restoring config.gd -> {LOCAL_URL}")
        write_config(LOCAL_URL)
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # --- start relay server ---
    print("[start_dev] Starting relay server...")
    relay_proc = subprocess.Popen(
        [sys.executable, "relay_server.py"],
        cwd=SERVER_DIR,
    )
    time.sleep(0.5)  # give the server a moment to bind the port
    if relay_proc.poll() is not None:
        print("[start_dev] ERROR: relay server exited immediately. Check server/relay_server.py.")
        sys.exit(1)

    # --- start ngrok ---
    print("[start_dev] Starting ngrok http 8765...")
    ngrok_proc = subprocess.Popen(
        ["ngrok", "http", "8765"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # --- wait for public URL ---
    print(f"[start_dev] Waiting up to {int(POLL_TIMEOUT)}s for ngrok tunnel...")
    try:
        wss_url = poll_ngrok_url(POLL_TIMEOUT)
    except TimeoutError as exc:
        print(f"[start_dev] ERROR: {exc}")
        cleanup()
        return

    print(f"\n[start_dev] Tunnel ready: {wss_url}")
    write_config(wss_url)
    print("[start_dev] config.gd updated")
    print("[start_dev] Press Ctrl+C to stop and restore config.gd.\n")

    # --- keep alive ---
    while True:
        # restart relay if it dies unexpectedly
        if relay_proc.poll() is not None:
            print("[start_dev] WARNING: relay server died. Restarting...")
            relay_proc = subprocess.Popen(
                [sys.executable, "relay_server.py"],
                cwd=SERVER_DIR,
            )
        if ngrok_proc.poll() is not None:
            print("[start_dev] WARNING: ngrok died. Restarting...")
            ngrok_proc = subprocess.Popen(
                ["ngrok", "http", "8765"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        time.sleep(2)


if __name__ == "__main__":
    main()

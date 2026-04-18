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
    time.sleep(0.4)
    yield

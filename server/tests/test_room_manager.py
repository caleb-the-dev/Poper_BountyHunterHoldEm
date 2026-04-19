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


# --- Game session integration ---

import os as _os, random as _random
from card_data import load_all as _load_all

_DATA_DIR_ROOM = _os.path.join(_os.path.dirname(__file__), "..", "..", "docs", "csv_data")


class _FakeClient:
    def __init__(self, name):
        self.name = name


def _make_manager_with_room(n_players):
    from room_manager import RoomManager
    mgr = RoomManager()
    clients = [_FakeClient(f"Player{i}") for i in range(n_players)]
    code = mgr.create_room(clients[0])
    for c in clients[1:]:
        mgr.join_room(code, c)
    return mgr, code, clients


def test_get_host_returns_room_creator():
    mgr, code, clients = _make_manager_with_room(3)
    assert mgr.get_host(code) is clients[0]

def test_get_host_unknown_room_returns_none():
    from room_manager import RoomManager
    mgr = RoomManager()
    assert mgr.get_host("9999") is None

def test_start_game_creates_game_session():
    mgr, code, clients = _make_manager_with_room(2)
    card_set = _load_all(_DATA_DIR_ROOM)
    session = mgr.start_game(clients[0], card_set, rng=_random.Random(42))
    assert session is not None
    assert mgr.get_game_session(code) is session

def test_start_game_rejects_non_host():
    mgr, code, clients = _make_manager_with_room(3)
    card_set = _load_all(_DATA_DIR_ROOM)
    with pytest.raises(ValueError):
        mgr.start_game(clients[1], card_set)

def test_start_game_rejects_if_already_in_progress():
    mgr, code, clients = _make_manager_with_room(2)
    card_set = _load_all(_DATA_DIR_ROOM)
    mgr.start_game(clients[0], card_set, rng=_random.Random(42))
    with pytest.raises(ValueError):
        mgr.start_game(clients[0], card_set, rng=_random.Random(42))

def test_start_game_rejects_if_fewer_than_2_players():
    from room_manager import RoomManager
    mgr = RoomManager()
    solo = _FakeClient("Solo")
    mgr.create_room(solo)
    card_set = _load_all(_DATA_DIR_ROOM)
    with pytest.raises(ValueError):
        mgr.start_game(solo, card_set, rng=_random.Random(42))

def test_get_game_session_by_client():
    mgr, code, clients = _make_manager_with_room(2)
    card_set = _load_all(_DATA_DIR_ROOM)
    session = mgr.start_game(clients[0], card_set, rng=_random.Random(42))
    assert mgr.get_game_session_for_client(clients[1]) is session

def test_room_cleared_on_leave_clears_session_if_last_out():
    mgr, code, clients = _make_manager_with_room(2)
    card_set = _load_all(_DATA_DIR_ROOM)
    mgr.start_game(clients[0], card_set, rng=_random.Random(42))
    mgr.leave_room(clients[0])
    mgr.leave_room(clients[1])
    assert mgr.get_game_session(code) is None  # room gone

def test_get_player_id_for_client():
    """Canonical player_id for a client is str(id(client))."""
    mgr, code, clients = _make_manager_with_room(2)
    assert mgr.get_player_id(clients[0]) == str(id(clients[0]))

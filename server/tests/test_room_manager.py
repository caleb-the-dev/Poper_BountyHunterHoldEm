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

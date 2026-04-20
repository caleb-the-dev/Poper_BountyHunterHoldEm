extends RefCounted
class_name TestHud

const Hud := preload("res://components/hud.gd")


static func run() -> int:
	print("-- test_hud --")
	var fails := 0
	fails += _test_pot_and_phase()
	fails += _test_your_turn_vs_waiting()
	fails += _test_check_vs_call_label()
	fails += _test_raise_bounds()
	fails += _test_resistance_banner_visibility()
	fails += _test_all_in_hidden_when_cant_afford_extra()
	fails += _test_bet_bar_hidden_when_folded()
	fails += _test_chat_unread_dot()
	return fails


static func _snap(overrides := {}) -> Dictionary:
	var base := {
		"room_code": "ABCD",
		"phase": "round_1",
		"players": [
			{"player_id": "me", "name": "Me", "chips": 80, "bet_this_round": 0, "folded": false, "all_in": false, "class_name": "Soldier"},
			{"player_id": "op", "name": "Opp", "chips": 90, "bet_this_round": 10, "folded": false, "all_in": false, "class_name": "Mage"},
		],
		"current_player_id": "me",
		"current_bet": 0,
		"max_raise": 20,
		"pot": 20,
		"board": {"bounty": null, "terrain": null, "mods_revealed": []},
		"resistance_dropped": false,
		"showdown": null,
	}
	for k in overrides.keys():
		base[k] = overrides[k]
	return base


static func _make() -> Node:
	var h = Hud.new()
	h._ready()
	return h


static func _test_pot_and_phase() -> int:
	var h := _make()
	h.update(_snap(), "me")
	var fails := 0
	if not TestHelpers.assert_in("Pot: 20", h.top_strip_text(), "pot displayed"): fails += 1
	if not TestHelpers.assert_in("Bounty Mod 1", h.top_strip_text(), "phase label"): fails += 1
	if not TestHelpers.assert_in("ABCD", h.top_strip_text(), "room code"): fails += 1
	h.free()
	return fails


static func _test_your_turn_vs_waiting() -> int:
	var h := _make()
	h.update(_snap(), "me")
	var fails := 0
	if not TestHelpers.assert_true(h.bet_bar_interactive(), "your turn enables bar"): fails += 1
	if not TestHelpers.assert_in("YOUR TURN", h.top_strip_text(), "turn badge"): fails += 1
	h.update(_snap({"current_player_id": "op"}), "me")
	if not TestHelpers.assert_false(h.bet_bar_interactive(), "opp turn disables bar"): fails += 1
	if not TestHelpers.assert_in("Opp", h.top_strip_text(), "waiting name"): fails += 1
	h.free()
	return fails


static func _test_check_vs_call_label() -> int:
	var h := _make()
	# No pending bet → Check
	h.update(_snap({"current_bet": 0}), "me")
	var fails := 0
	if not TestHelpers.assert_eq(h.check_call_label(), "Check", "check when bet matches"): fails += 1
	# Pending 10 bet → Call 10cp
	var players := _snap()["players"]
	h.update(_snap({"current_bet": 10, "players": players}), "me")
	if not TestHelpers.assert_eq(h.check_call_label(), "Call 10cp", "call diff"): fails += 1
	h.free()
	return fails


static func _test_raise_bounds() -> int:
	var h := _make()
	h.update(_snap({"current_bet": 5, "max_raise": 15}), "me")
	var fails := 0
	if not TestHelpers.assert_eq(h.raise_min(), 6, "raise min = current_bet+1"): fails += 1
	if not TestHelpers.assert_eq(h.raise_max(), 15, "raise max = max_raise"): fails += 1
	h.free()
	return fails


static func _test_resistance_banner_visibility() -> int:
	var h := _make()
	h.update(_snap({"resistance_dropped": false}), "me")
	var fails := 0
	if not TestHelpers.assert_false(h.resistance_banner_visible(), "banner hidden"): fails += 1
	h.update(_snap({"resistance_dropped": true}), "me")
	if not TestHelpers.assert_true(h.resistance_banner_visible(), "banner visible"): fails += 1
	h.free()
	return fails


static func _test_all_in_hidden_when_cant_afford_extra() -> int:
	var h := _make()
	# Chips = 10, current_bet = 10 → all-in just calls → hide button
	var snap := _snap({"current_bet": 10})
	snap["players"][0]["chips"] = 10
	h.update(snap, "me")
	var fails := 0
	if not TestHelpers.assert_false(h.all_in_visible(), "all-in hidden when chips == bet"): fails += 1
	h.free()
	return fails


static func _test_bet_bar_hidden_when_folded() -> int:
	var h := _make()
	var snap := _snap()
	snap["players"][0]["folded"] = true
	h.update(snap, "me")
	var fails := 0
	if not TestHelpers.assert_false(h.bet_bar_visible(), "bar hidden when folded"): fails += 1
	h.free()
	return fails


static func _test_chat_unread_dot() -> int:
	var h := _make()
	h.update(_snap(), "me")
	var fails := 0
	# Chat arrives while drawer closed → dot visible
	h.add_chat_message("Opp", "gl hf")
	if not TestHelpers.assert_true(h.chat_unread_dot_visible(), "unread dot after closed-chat"): fails += 1
	# Opening clears the dot
	h._toggle_chat()
	if not TestHelpers.assert_false(h.chat_unread_dot_visible(), "unread cleared on open"): fails += 1
	if not TestHelpers.assert_true(h.chat_drawer_open(), "drawer open after toggle"): fails += 1
	h.free()
	return fails

extends RefCounted
class_name TestSeats

const Seats3D := preload("res://components/seats_3d.gd")


static func run() -> int:
	print("-- test_seats --")
	var fails := 0
	fails += _test_opponents_placed_in_order_skipping_self()
	fails += _test_turn_seat_highlighted()
	fails += _test_local_hand_populates_seat_0()
	fails += _test_folded_opponent_shows_badge()
	return fails


static func _make() -> Node3D:
	var s = Seats3D.new()
	s._ready()
	return s


static func _players(count: int) -> Array:
	var arr := []
	for i in range(count):
		arr.append({
			"player_id": "p%d" % i,
			"name": "P%d" % i,
			"chips": 100,
			"bet_this_round": 0,
			"folded": false,
			"all_in": false,
			"class_name": "Soldier",
		})
	return arr


static func _test_opponents_placed_in_order_skipping_self() -> int:
	var s := _make()
	s.update({"players": _players(3), "current_player_id": null}, "p1")
	# Seat 0 = local (p1). Opponents: p0 at seat 1, p2 at seat 2.
	var fails := 0
	if not TestHelpers.assert_eq(s.opponent_player_id_at_seat(1), "p0", "seat 1 is p0"): fails += 1
	if not TestHelpers.assert_eq(s.opponent_player_id_at_seat(2), "p2", "seat 2 is p2"): fails += 1
	if not TestHelpers.assert_eq(s.opponent_player_id_at_seat(3), "", "seat 3 empty"): fails += 1
	s.free()
	return fails


static func _test_turn_seat_highlighted() -> int:
	var s := _make()
	s.update({"players": _players(3), "current_player_id": "p2"}, "p1")
	var fails := 0
	# p2 is at seat 2
	if not TestHelpers.assert_true(s.seat_is_turn_highlighted(2), "seat 2 highlighted"): fails += 1
	if not TestHelpers.assert_false(s.seat_is_turn_highlighted(1), "seat 1 not highlighted"): fails += 1
	s.free()
	return fails


static func _test_local_hand_populates_seat_0() -> int:
	var s := _make()
	var hand := {
		"weapon": {"name": "Longsword", "damage_types": [[3, "slashing"]]},
		"item": {"name": "Shield", "bonus_value": 1, "damage_type": "blunt"},
		"infusion": {"name": "Holy", "infusion_type": "Holy"},
		"fourth_card": {"name": "Potion", "bonus_value": 1, "damage_type": "blunt"},
	}
	var class_card := {"name": "Paladin", "damage_formulas": [["2+LV", "slashing"]]}
	s.set_local_hand(hand, class_card)
	var fails := 0
	if not TestHelpers.assert_eq(s.local_card_name(0), "Paladin", "slot 0 is class"): fails += 1
	if not TestHelpers.assert_eq(s.local_card_name(1), "Longsword", "slot 1 is weapon"): fails += 1
	if not TestHelpers.assert_eq(s.local_card_name(2), "Shield", "slot 2 is item"): fails += 1
	if not TestHelpers.assert_eq(s.local_card_name(3), "Holy", "slot 3 is infusion"): fails += 1
	if not TestHelpers.assert_eq(s.local_card_name(4), "Potion", "slot 4 is 4th"): fails += 1
	s.free()
	return fails


static func _test_folded_opponent_shows_badge() -> int:
	var s := _make()
	var ps := _players(3)
	ps[0]["folded"] = true
	s.update({"players": ps, "current_player_id": "p2"}, "p1")
	var fails := 0
	if not TestHelpers.assert_eq(s.opponent_badge_text_at_seat(1), "FOLDED", "p0 at seat 1 shows FOLDED"): fails += 1
	s.free()
	return fails

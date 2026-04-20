extends RefCounted
class_name TestBoard

const Board3D := preload("res://components/board_3d.gd")
const Card3D := preload("res://components/card_3d.gd")


static func run() -> int:
	print("-- test_board --")
	var fails := 0
	fails += _test_starts_all_face_down()
	fails += _test_mods_reveal_in_order()
	fails += _test_bounty_in_slot_1()
	fails += _test_terrain_in_slot_3()
	return fails


static func _make() -> Node3D:
	var b = Board3D.new()
	# Call _ready manually — orphan nodes work for property-only assertions.
	b._ready()
	return b


static func _test_starts_all_face_down() -> int:
	var b := _make()
	b.update({"bounty": null, "terrain": null, "mods_revealed": []}, false)
	var fails := 0
	for i in range(5):
		if not TestHelpers.assert_false(b.slot_face_up(i), "slot %d face-down initially" % i): fails += 1
	b.free()
	return fails


static func _test_mods_reveal_in_order() -> int:
	var b := _make()
	var mod_a := {"name": "ModA", "affected_type": "slashing", "modifier": 1}
	var mod_b := {"name": "ModB", "affected_type": "blunt", "modifier": -1}
	b.update({"bounty": null, "terrain": null, "mods_revealed": [mod_a, mod_b]}, false)
	var fails := 0
	if not TestHelpers.assert_true(b.slot_face_up(0), "slot 0 (mod1) face-up"): fails += 1
	if not TestHelpers.assert_eq(b.slot_card(0).get("name"), "ModA", "slot 0 holds ModA"): fails += 1
	# mod2 goes into slot 2 per round order: mod1 → bounty → mod2 → terrain → mod3
	if not TestHelpers.assert_true(b.slot_face_up(2), "slot 2 (mod2) face-up"): fails += 1
	if not TestHelpers.assert_eq(b.slot_card(2).get("name"), "ModB", "slot 2 holds ModB"): fails += 1
	b.free()
	return fails


static func _test_bounty_in_slot_1() -> int:
	var b := _make()
	var bounty := {"name": "Undead", "vulnerability": "Holy", "resistance": "Shadow"}
	b.update({"bounty": bounty, "terrain": null, "mods_revealed": [{"name": "M1", "affected_type": "slashing", "modifier": 1}]}, false)
	var fails := 0
	if not TestHelpers.assert_true(b.slot_face_up(1), "slot 1 (bounty) face-up"): fails += 1
	if not TestHelpers.assert_eq(b.slot_card(1).get("name"), "Undead", "slot 1 holds bounty"): fails += 1
	b.free()
	return fails


static func _test_terrain_in_slot_3() -> int:
	var b := _make()
	var terrain := {"name": "Graveyard", "adds_vulnerability": "Holy"}
	b.update({
		"bounty": {"name": "Undead", "vulnerability": "Holy", "resistance": "Shadow"},
		"terrain": terrain,
		"mods_revealed": [
			{"name": "M1", "affected_type": "s", "modifier": 1},
			{"name": "M2", "affected_type": "s", "modifier": 1},
		],
	}, false)
	var fails := 0
	if not TestHelpers.assert_true(b.slot_face_up(3), "slot 3 (terrain) face-up"): fails += 1
	if not TestHelpers.assert_eq(b.slot_card(3).get("name"), "Graveyard", "slot 3 holds terrain"): fails += 1
	b.free()
	return fails

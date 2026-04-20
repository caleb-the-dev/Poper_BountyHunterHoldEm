extends RefCounted
class_name TestCardFace

const CardFace := preload("res://components/card_face.gd")


static func run() -> int:
	print("-- test_card_face --")
	var fails := 0
	fails += _test_shows_name_and_stat()
	fails += _test_class_label()
	fails += _test_handles_missing_stat()
	return fails


static func _make_face() -> Node:
	return CardFace.new()


static func _test_shows_name_and_stat() -> int:
	var face := _make_face()
	face.set_card({"name": "Longsword", "damage_types": [[3, "slashing"]]}, "weapon")
	var fails := 0
	if not TestHelpers.assert_eq(face.get_name_text(), "Longsword", "weapon name"): fails += 1
	if not TestHelpers.assert_eq(face.get_type_text(), "WEAPON", "type label upper"): fails += 1
	if not TestHelpers.assert_in("3", face.get_stat_text(), "weapon stat includes damage"): fails += 1
	face.free()
	return fails


static func _test_class_label() -> int:
	var face := _make_face()
	face.set_card({"name": "Paladin", "damage_formulas": [["2+LV", "slashing"]]}, "class")
	var fails := 0
	if not TestHelpers.assert_eq(face.get_name_text(), "Paladin", "class name"): fails += 1
	if not TestHelpers.assert_eq(face.get_type_text(), "CLASS", "class type label"): fails += 1
	if not TestHelpers.assert_in("2+LV", face.get_stat_text(), "class stat shows formula"): fails += 1
	face.free()
	return fails


static func _test_handles_missing_stat() -> int:
	var face := _make_face()
	face.set_card({"name": "Mystery"}, "item")
	var fails := 0
	if not TestHelpers.assert_eq(face.get_name_text(), "Mystery", "name only"): fails += 1
	if not TestHelpers.assert_eq(face.get_stat_text(), "", "stat empty when absent"): fails += 1
	face.free()
	return fails

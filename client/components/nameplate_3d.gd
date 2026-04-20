extends Node3D


const COLOR_DEFAULT := Color(0.90, 0.90, 0.90)
const COLOR_FOLDED := Color(0.50, 0.50, 0.50)
const COLOR_ALLIN := Color(0.95, 0.35, 0.35)
const COLOR_TURN := Color(0.95, 0.82, 0.30)
const COLOR_CLASS := Color(0.85, 0.80, 0.60)

var _name_lbl: Label3D
var _class_lbl: Label3D
var _chips_lbl: Label3D
var _badge_lbl: Label3D


func _ready() -> void:
	_name_lbl = Label3D.new()
	_name_lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_name_lbl.font_size = 36
	_name_lbl.outline_size = 4
	_name_lbl.position = Vector3(0, 0.28, 0)
	add_child(_name_lbl)

	_class_lbl = Label3D.new()
	_class_lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_class_lbl.font_size = 26
	_class_lbl.outline_size = 3
	_class_lbl.position = Vector3(0, 0.17, 0)
	_class_lbl.modulate = COLOR_CLASS
	add_child(_class_lbl)

	_chips_lbl = Label3D.new()
	_chips_lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_chips_lbl.font_size = 24
	_chips_lbl.outline_size = 3
	_chips_lbl.position = Vector3(0, 0.07, 0)
	add_child(_chips_lbl)

	_badge_lbl = Label3D.new()
	_badge_lbl.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	_badge_lbl.font_size = 22
	_badge_lbl.outline_size = 3
	_badge_lbl.position = Vector3(0, -0.04, 0)
	_badge_lbl.visible = false
	add_child(_badge_lbl)


func update(entry: Dictionary, is_turn: bool) -> void:
	_name_lbl.text = str(entry.get("name", "?"))
	var cls = entry.get("class_name")
	_class_lbl.text = str(cls) if cls != null else ""
	_chips_lbl.text = "%d cp  (bet %d)" % [int(entry.get("chips", 0)), int(entry.get("bet_this_round", 0))]

	var folded := bool(entry.get("folded", false))
	var all_in := bool(entry.get("all_in", false))
	if folded:
		_name_lbl.modulate = COLOR_FOLDED
		_badge_lbl.text = "FOLDED"
		_badge_lbl.modulate = COLOR_FOLDED
		_badge_lbl.visible = true
	elif all_in:
		_name_lbl.modulate = COLOR_ALLIN
		_badge_lbl.text = "ALL-IN"
		_badge_lbl.modulate = COLOR_ALLIN
		_badge_lbl.visible = true
	else:
		_name_lbl.modulate = COLOR_TURN if is_turn else COLOR_DEFAULT
		_badge_lbl.visible = false

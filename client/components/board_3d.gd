extends Node3D


const Card3D := preload("res://components/card_3d.gd")

# Slot layout in world space — z=0 is the table center line.
const SLOT_POSITIONS := [
	Vector3(-1.2, 0.02, -0.1),
	Vector3(-0.6, 0.02, -0.1),
	Vector3( 0.0, 0.02, -0.1),
	Vector3( 0.6, 0.02, -0.1),
	Vector3( 1.2, 0.02, -0.1),
]

const SLOT_TYPES := ["mod", "bounty", "mod", "terrain", "mod"]

var _cards: Array = []  # Array of card_3d instances, length 5


func _ready() -> void:
	for i in range(5):
		var c = Card3D.new()
		c.position = SLOT_POSITIONS[i]
		c.rotation_degrees = Vector3(-90, 0, 0)  # face up from table plane
		add_child(c)
		c._ready()  # ensure inner SubViewport spins up even if not yet in a SceneTree
		_cards.append(c)


func update(board: Dictionary, resistance_dropped: bool) -> void:
	# Order of reveal matches round progression:
	#   round_1 reveals mods_revealed[0]          → slot 0
	#   round_2 reveals bounty                    → slot 1
	#   round_3 reveals mods_revealed[1]          → slot 2
	#   round_4 reveals terrain                   → slot 3
	#   round_5 reveals mods_revealed[2]          → slot 4
	var mods = board.get("mods_revealed", []) as Array
	var bounty = board.get("bounty")
	var terrain = board.get("terrain")

	_set_slot(0, mods[0] if mods.size() > 0 else null, "mod")
	_set_slot(1, bounty, "bounty")
	_set_slot(2, mods[1] if mods.size() > 1 else null, "mod")
	_set_slot(3, terrain, "terrain")
	_set_slot(4, mods[2] if mods.size() > 2 else null, "mod")


func slot_face_up(i: int) -> bool:
	return _cards[i].is_face_up()


func slot_card(i: int) -> Dictionary:
	return _cards[i].current_card()


func _set_slot(i: int, card, type_label: String) -> void:
	if card == null:
		_cards[i].set_face_down()
	else:
		_cards[i].set_card(card, type_label)

extends Node3D


const Card3D := preload("res://components/card_3d.gd")
const Nameplate3D := preload("res://components/nameplate_3d.gd")

const SEAT_COUNT := 8
const TABLE_RADIUS_X := 2.4
const TABLE_RADIUS_Z := 1.4
const LOCAL_SEAT_Z := 1.3   # closer to camera
const SEAT_HEIGHT := 0.1

# Card slot offsets within a seat: [class, weapon, item, infusion, fourth_card]
const LOCAL_CARD_OFFSETS := [
	Vector3(-1.0, 0.02, 0.0),
	Vector3(-0.5, 0.02, 0.0),
	Vector3( 0.0, 0.02, 0.0),
	Vector3( 0.5, 0.02, 0.0),
	Vector3( 1.0, 0.02, 0.0),
]

var _seats: Array = []  # seat Node3Ds
var _nameplates: Array = []  # index 1..7 populated; index 0 stays null
var _local_cards: Array = []  # 5 Card3D for seat 0
var _opponent_pids: Dictionary = {}  # seat_index → player_id ("" when empty)
var _turn_seat_index: int = -1
var _opponent_badges: Dictionary = {}  # seat_index → badge text ("" when none)


func _ready() -> void:
	_seats.resize(SEAT_COUNT)
	_nameplates.resize(SEAT_COUNT)
	for i in range(SEAT_COUNT):
		var seat := Node3D.new()
		seat.position = _seat_position(i)
		add_child(seat)
		_seats[i] = seat
		if i == 0:
			# Build 5 local card slots, start face-down
			for slot in range(5):
				var c = Card3D.new()
				c.position = LOCAL_CARD_OFFSETS[slot]
				c.rotation_degrees = Vector3(-90, 0, 0)
				seat.add_child(c)
				c._ready()
				_local_cards.append(c)
		else:
			var np = Nameplate3D.new()
			seat.add_child(np)
			np._ready()
			_nameplates[i] = np
		_opponent_pids[i] = ""
		_opponent_badges[i] = ""


func _seat_position(i: int) -> Vector3:
	if i == 0:
		return Vector3(0, SEAT_HEIGHT, LOCAL_SEAT_Z)
	# Seats 1..7 fan across the far arc (negative z).
	var count := SEAT_COUNT - 1  # 7 opponent seats
	var t := float(i - 1) / float(count - 1) if count > 1 else 0.5
	var angle := lerp(PI * 0.85, PI * 0.15, t)  # arc from left-back to right-back
	var x := cos(angle) * TABLE_RADIUS_X
	var z := -abs(sin(angle)) * TABLE_RADIUS_Z - 0.4
	return Vector3(x, SEAT_HEIGHT, z)


func update(snap: Dictionary, my_player_id: String) -> void:
	var players = snap.get("players", []) as Array
	var current_pid = snap.get("current_player_id")
	# Clear prior
	_turn_seat_index = -1
	for i in range(1, SEAT_COUNT):
		_opponent_pids[i] = ""
		_opponent_badges[i] = ""
		_nameplates[i].visible = false

	var opponents := []
	for entry in players:
		if str(entry.get("player_id", "")) != my_player_id:
			opponents.append(entry)

	for i in range(opponents.size()):
		var seat_i := i + 1
		if seat_i >= SEAT_COUNT:
			break
		var entry = opponents[i]
		var pid := str(entry.get("player_id", ""))
		_opponent_pids[seat_i] = pid
		var is_turn := current_pid != null and str(current_pid) == pid
		if is_turn:
			_turn_seat_index = seat_i
		_nameplates[seat_i].visible = true
		_nameplates[seat_i].update(entry, is_turn)
		# Track badge text for tests (we don't introspect Label3D color directly)
		if bool(entry.get("folded", false)):
			_opponent_badges[seat_i] = "FOLDED"
		elif bool(entry.get("all_in", false)):
			_opponent_badges[seat_i] = "ALL-IN"


func set_local_hand(hand: Dictionary, class_card: Dictionary) -> void:
	_local_cards[0].set_card(class_card, "class")
	_local_cards[1].set_card(hand.get("weapon", {}), "weapon")
	_local_cards[2].set_card(hand.get("item", {}), "item")
	_local_cards[3].set_card(hand.get("infusion", {}), "infusion")
	var fourth = hand.get("fourth_card", {})
	# Type inferred from shape: if it has "infusion_type" it's an infusion, else item
	var fourth_type := "infusion" if fourth.has("infusion_type") else "item"
	_local_cards[4].set_card(fourth, fourth_type)


func clear_local_hand() -> void:
	for c in _local_cards:
		c.set_face_down()


# --- Introspection for tests ---

func opponent_player_id_at_seat(i: int) -> String:
	return str(_opponent_pids.get(i, ""))


func seat_is_turn_highlighted(i: int) -> bool:
	return _turn_seat_index == i


func local_card_name(slot: int) -> String:
	return str(_local_cards[slot].current_card().get("name", ""))


func opponent_badge_text_at_seat(i: int) -> String:
	return str(_opponent_badges.get(i, ""))

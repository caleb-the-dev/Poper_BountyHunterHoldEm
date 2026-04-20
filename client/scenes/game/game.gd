extends Node3D


signal left_game

const Board3D := preload("res://components/board_3d.gd")
const Seats3D := preload("res://components/seats_3d.gd")
const Hud := preload("res://components/hud.gd")
const ClassReveal := preload("res://overlays/class_reveal.gd")
const Showdown := preload("res://overlays/showdown.gd")

var _board: Node3D
var _seats: Node3D
var _hud: CanvasLayer
var _class_reveal: Control = null
var _showdown: Control = null

var _last_snap: Dictionary = {}
var _last_private: Dictionary = {}
var _hand_reveal_shown: bool = false
var _showdown_shown: bool = false

var _message_cb: Callable


func _ready() -> void:
	_build_3d_scene()
	_build_board_and_seats()
	_build_hud()

	_message_cb = func(data): _on_message(data)
	WsClient.message_received.connect(_message_cb)


func _exit_tree() -> void:
	if WsClient.message_received.is_connected(_message_cb):
		WsClient.message_received.disconnect(_message_cb)


func _build_3d_scene() -> void:
	# Camera
	var cam := Camera3D.new()
	cam.position = Vector3(0, 2.0, 3.6)
	cam.rotation_degrees = Vector3(-22, 0, 0)
	cam.current = true
	add_child(cam)

	# Light
	var light := DirectionalLight3D.new()
	light.rotation_degrees = Vector3(-50, 30, 0)
	light.light_energy = 1.0
	add_child(light)

	# Environment
	var env := WorldEnvironment.new()
	var e := Environment.new()
	e.background_mode = Environment.BG_COLOR
	e.background_color = Color(0.06, 0.08, 0.14)
	e.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	e.ambient_light_color = Color(0.30, 0.32, 0.40)
	e.ambient_light_energy = 0.4
	env.environment = e
	add_child(env)

	# Table
	var table := MeshInstance3D.new()
	var mesh := CylinderMesh.new()
	mesh.top_radius = 3.0
	mesh.bottom_radius = 3.0
	mesh.height = 0.1
	mesh.radial_segments = 48
	table.mesh = mesh
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.16, 0.40, 0.20)
	mat.roughness = 0.9
	table.material_override = mat
	table.scale = Vector3(1.0, 1.0, 0.6)  # squash into ellipse
	table.position = Vector3(0, -0.05, 0)
	add_child(table)


func _build_board_and_seats() -> void:
	_board = Board3D.new()
	add_child(_board)
	_board._ready()
	_seats = Seats3D.new()
	add_child(_seats)
	_seats._ready()


func _build_hud() -> void:
	_hud = Hud.new()
	add_child(_hud)
	_hud._ready()
	_hud.bet_action_requested.connect(_on_bet_action_requested)


func _on_message(data) -> void:
	if typeof(data) != TYPE_DICTIONARY:
		return
	match data.get("event"):
		"game_state":
			_apply_state(data)
		"your_hand":
			_apply_private_hand(data)
		"chat":
			_hud.add_chat_message(str(data.get("from", "?")), str(data.get("text", "")))
		"error":
			# Future: toast. For now, push to log.
			push_warning("[game] server error: " + str(data.get("message", "")))


func _apply_state(snap: Dictionary) -> void:
	_last_snap = snap
	var my_pid: String = WsClient.my_player_id
	_board.update(snap.get("board", {}), bool(snap.get("resistance_dropped", false)))
	_seats.update(snap, my_pid)
	_hud.update(snap, my_pid)
	var sd = snap.get("showdown")
	if sd != null and not _showdown_shown:
		_show_showdown(snap)
		_showdown_shown = true


func _apply_private_hand(priv: Dictionary) -> void:
	_last_private = priv
	var hand: Dictionary = priv.get("hand", {})
	var class_card: Dictionary = priv.get("class_card", {})
	_seats.set_local_hand(hand, class_card)
	if not _hand_reveal_shown:
		_show_class_reveal(priv)
		_hand_reveal_shown = true


func _show_class_reveal(priv: Dictionary) -> void:
	_class_reveal = ClassReveal.new()
	# Overlays live on the HUD CanvasLayer so they render above 3D
	_hud.add_child(_class_reveal)
	_class_reveal._ready()
	_class_reveal.show_reveal(priv)
	_class_reveal.dismissed.connect(func():
		if _class_reveal and is_instance_valid(_class_reveal):
			_class_reveal.queue_free()
		_class_reveal = null
	)


func _show_showdown(snap: Dictionary) -> void:
	_showdown = Showdown.new()
	_hud.add_child(_showdown)
	_showdown._ready()
	_showdown.show_showdown(snap)
	_showdown.leave_game_requested.connect(func(): left_game.emit())


func _on_bet_action_requested(action_type: String, amount) -> void:
	var payload := {"action": "bet_action", "type": action_type}
	if amount != null:
		payload["amount"] = int(amount)
	WsClient.send_message(payload)

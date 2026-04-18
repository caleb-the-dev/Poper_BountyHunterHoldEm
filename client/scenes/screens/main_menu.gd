extends Control

signal room_created(room_code: String)
signal room_joined(room_code: String, players: Array)

var player_name: String = ""

var _url_input: LineEdit
var _code_input: LineEdit
var _status_label: Label
var _pending_action: String = ""
var _pending_code: String = ""


func _ready() -> void:
	WsClient.message_received.connect(_on_message)
	WsClient.disconnected.connect(func(): _set_status("Disconnected from server."))
	_build_ui()


func _build_ui() -> void:
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)

	var vbox := VBoxContainer.new()
	vbox.custom_minimum_size = Vector2(520, 0)
	center.add_child(vbox)

	var title := Label.new()
	title.text = "Welcome, " + player_name
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vbox.add_child(title)

	vbox.add_child(_spacer(20))

	var url_lbl := Label.new()
	url_lbl.text = "Server URL:"
	vbox.add_child(url_lbl)

	_url_input = LineEdit.new()
	_url_input.text = Config.SERVER_URL
	vbox.add_child(_url_input)

	vbox.add_child(_spacer(12))

	var create_btn := Button.new()
	create_btn.text = "Create Room"
	create_btn.pressed.connect(_on_create_pressed)
	vbox.add_child(create_btn)

	vbox.add_child(_spacer(12))

	var join_row := HBoxContainer.new()
	vbox.add_child(join_row)

	_code_input = LineEdit.new()
	_code_input.placeholder_text = "4-digit room code"
	_code_input.max_length = 4
	_code_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	join_row.add_child(_code_input)

	var join_btn := Button.new()
	join_btn.text = "Join Room"
	join_btn.pressed.connect(_on_join_pressed)
	join_row.add_child(join_btn)

	vbox.add_child(_spacer(12))

	_status_label = Label.new()
	_status_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	vbox.add_child(_status_label)


func _spacer(height: int) -> Control:
	var s := Control.new()
	s.custom_minimum_size = Vector2(0, height)
	return s


func _set_status(msg: String) -> void:
	_status_label.text = msg


func _on_create_pressed() -> void:
	_pending_action = "create"
	_pending_code = ""
	_set_status("Connecting...")
	WsClient.connected.connect(_on_ws_connected, CONNECT_ONE_SHOT)
	WsClient.connect_to_server(_url_input.text.strip_edges())


func _on_join_pressed() -> void:
	var code := _code_input.text.strip_edges()
	if code.length() != 4 or not code.is_numeric():
		_set_status("Please enter a valid 4-digit room code.")
		return
	_pending_action = "join"
	_pending_code = code
	_set_status("Connecting...")
	WsClient.connected.connect(_on_ws_connected, CONNECT_ONE_SHOT)
	WsClient.connect_to_server(_url_input.text.strip_edges())


func _on_ws_connected() -> void:
	WsClient.send_message({"action": "set_name", "name": player_name})


func _on_message(data: Dictionary) -> void:
	match data.get("event"):
		"name_set":
			if _pending_action == "create":
				WsClient.send_message({"action": "create_room"})
			elif _pending_action == "join":
				WsClient.send_message({"action": "join_room", "code": _pending_code})
		"room_created":
			_pending_action = ""
			room_created.emit(data["code"])
		"room_joined":
			_pending_action = ""
			room_joined.emit(data["code"], data.get("players", []))
		"error":
			_set_status("Error: " + data.get("message", "unknown error"))
			_pending_action = ""

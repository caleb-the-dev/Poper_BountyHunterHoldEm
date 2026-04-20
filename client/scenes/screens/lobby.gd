extends Control

signal left_room
signal game_starting

var player_name: String = ""
var room_code: String = ""
var initial_players: Array = []

var _player_list: VBoxContainer
var _chat_log: VBoxContainer
var _chat_scroll: ScrollContainer
var _chat_input: LineEdit
var _disconnected_cb: Callable
var _game_started: bool = false


func _ready() -> void:
	_disconnected_cb = func(): _add_chat("[Server]", "Connection lost.")
	WsClient.message_received.connect(_on_message)
	WsClient.disconnected.connect(_disconnected_cb)
	_build_ui()
	for p in initial_players:
		_add_player_label(p)


func _exit_tree() -> void:
	if WsClient.message_received.is_connected(_on_message):
		WsClient.message_received.disconnect(_on_message)
	if WsClient.disconnected.is_connected(_disconnected_cb):
		WsClient.disconnected.disconnect(_disconnected_cb)


func _build_ui() -> void:
	const FONT_NORMAL := 20
	const FONT_HEADER := 24

	var root := VBoxContainer.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.add_theme_constant_override("separation", 12)
	add_child(root)

	var header := HBoxContainer.new()
	header.add_theme_constant_override("separation", 16)
	root.add_child(header)

	var room_lbl := Label.new()
	room_lbl.text = "Room: " + room_code
	room_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	room_lbl.add_theme_font_size_override("font_size", FONT_HEADER)
	header.add_child(room_lbl)

	var leave_btn := Button.new()
	leave_btn.text = "Leave Room"
	leave_btn.custom_minimum_size = Vector2(0, 48)
	leave_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	leave_btn.pressed.connect(_on_leave_pressed)
	header.add_child(leave_btn)

	var start_btn := Button.new()
	start_btn.text = "Start Game"
	start_btn.custom_minimum_size = Vector2(140, 48)
	start_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	start_btn.pressed.connect(func(): WsClient.send_message({"action": "start_game"}))
	header.add_child(start_btn)

	var body := HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 16)
	root.add_child(body)

	var player_panel := VBoxContainer.new()
	player_panel.custom_minimum_size = Vector2(220, 0)
	player_panel.add_theme_constant_override("separation", 8)
	body.add_child(player_panel)

	var players_lbl := Label.new()
	players_lbl.text = "Players"
	players_lbl.add_theme_font_size_override("font_size", FONT_HEADER)
	player_panel.add_child(players_lbl)

	_player_list = VBoxContainer.new()
	_player_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_player_list.add_theme_constant_override("separation", 6)
	player_panel.add_child(_player_list)

	var chat_panel := VBoxContainer.new()
	chat_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	chat_panel.add_theme_constant_override("separation", 8)
	body.add_child(chat_panel)

	var chat_lbl := Label.new()
	chat_lbl.text = "Chat"
	chat_lbl.add_theme_font_size_override("font_size", FONT_HEADER)
	chat_panel.add_child(chat_lbl)

	_chat_scroll = ScrollContainer.new()
	_chat_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	chat_panel.add_child(_chat_scroll)

	_chat_log = VBoxContainer.new()
	_chat_log.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_chat_log.add_theme_constant_override("separation", 6)
	_chat_scroll.add_child(_chat_log)

	var input_row := HBoxContainer.new()
	input_row.add_theme_constant_override("separation", 8)
	chat_panel.add_child(input_row)

	_chat_input = LineEdit.new()
	_chat_input.placeholder_text = "Type a message..."
	_chat_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_chat_input.custom_minimum_size = Vector2(0, 48)
	_chat_input.add_theme_font_size_override("font_size", FONT_NORMAL)
	_chat_input.text_submitted.connect(func(t): _send_chat(t))
	input_row.add_child(_chat_input)

	var send_btn := Button.new()
	send_btn.text = "Send"
	send_btn.custom_minimum_size = Vector2(80, 48)
	send_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	send_btn.pressed.connect(func(): _send_chat(_chat_input.text))
	input_row.add_child(send_btn)


func _add_player_label(p_name: String) -> void:
	var lbl := Label.new()
	lbl.text = "• " + p_name
	lbl.name = "p_" + p_name
	lbl.add_theme_font_size_override("font_size", 20)
	_player_list.add_child(lbl)


func _remove_player_label(p_name: String) -> void:
	var node := _player_list.find_child("p_" + p_name, false, false)
	if node:
		node.queue_free()


func _add_chat(from: String, text: String) -> void:
	var lbl := Label.new()
	lbl.text = from + ": " + text
	lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	lbl.add_theme_font_size_override("font_size", 20)
	_chat_log.add_child(lbl)
	_scroll_to_bottom()


func _scroll_to_bottom() -> void:
	await get_tree().process_frame
	if is_instance_valid(_chat_scroll):
		_chat_scroll.scroll_vertical = int(_chat_scroll.get_v_scroll_bar().max_value)


func _send_chat(text: String) -> void:
	text = text.strip_edges()
	if text.is_empty():
		return
	WsClient.send_message({"action": "chat", "text": text})
	_add_chat(player_name, text)
	_chat_input.text = ""


func _on_leave_pressed() -> void:
	WsClient.send_message({"action": "leave_room"})
	left_room.emit()


func _on_message(data: Dictionary) -> void:
	match data.get("event"):
		"player_joined":
			_add_player_label(data["name"])
			_add_chat("[Server]", data["name"] + " joined.")
		"player_left":
			_remove_player_label(data["name"])
			_add_chat("[Server]", data["name"] + " left.")
		"chat":
			_add_chat(data.get("from", "?"), data.get("text", ""))
		"game_state":
			if not _game_started:
				_game_started = true
				game_starting.emit()

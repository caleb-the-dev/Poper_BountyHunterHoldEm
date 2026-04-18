extends Control

signal left_room

var player_name: String = ""
var room_code: String = ""
var initial_players: Array = []

var _player_list: VBoxContainer
var _chat_log: VBoxContainer
var _chat_scroll: ScrollContainer
var _chat_input: LineEdit


func _ready() -> void:
	WsClient.message_received.connect(_on_message)
	WsClient.disconnected.connect(func(): _add_chat("[Server]", "Connection lost."))
	_build_ui()
	for p in initial_players:
		_add_player_label(p)


func _build_ui() -> void:
	var root := VBoxContainer.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(root)

	var header := HBoxContainer.new()
	root.add_child(header)

	var room_lbl := Label.new()
	room_lbl.text = "Room: " + room_code
	room_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(room_lbl)

	var leave_btn := Button.new()
	leave_btn.text = "Leave Room"
	leave_btn.pressed.connect(_on_leave_pressed)
	header.add_child(leave_btn)

	var body := HBoxContainer.new()
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	root.add_child(body)

	var player_panel := VBoxContainer.new()
	player_panel.custom_minimum_size = Vector2(200, 0)
	body.add_child(player_panel)

	var players_lbl := Label.new()
	players_lbl.text = "Players"
	player_panel.add_child(players_lbl)

	_player_list = VBoxContainer.new()
	_player_list.size_flags_vertical = Control.SIZE_EXPAND_FILL
	player_panel.add_child(_player_list)

	var chat_panel := VBoxContainer.new()
	chat_panel.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_child(chat_panel)

	var chat_lbl := Label.new()
	chat_lbl.text = "Chat"
	chat_panel.add_child(chat_lbl)

	_chat_scroll = ScrollContainer.new()
	_chat_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	chat_panel.add_child(_chat_scroll)

	_chat_log = VBoxContainer.new()
	_chat_log.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_chat_scroll.add_child(_chat_log)

	var input_row := HBoxContainer.new()
	chat_panel.add_child(input_row)

	_chat_input = LineEdit.new()
	_chat_input.placeholder_text = "Type a message..."
	_chat_input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_chat_input.text_submitted.connect(func(t): _send_chat(t))
	input_row.add_child(_chat_input)

	var send_btn := Button.new()
	send_btn.text = "Send"
	send_btn.pressed.connect(func(): _send_chat(_chat_input.text))
	input_row.add_child(send_btn)


func _add_player_label(name: String) -> void:
	var lbl := Label.new()
	lbl.text = "• " + name
	lbl.name = "p_" + name
	_player_list.add_child(lbl)


func _remove_player_label(name: String) -> void:
	var node := _player_list.find_child("p_" + name, false, false)
	if node:
		node.queue_free()


func _add_chat(from: String, text: String) -> void:
	var lbl := Label.new()
	lbl.text = from + ": " + text
	lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
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

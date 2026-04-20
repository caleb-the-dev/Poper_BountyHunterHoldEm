extends Control

var _current_screen: Node = null
var _player_name: String = ""


func _ready() -> void:
	_show_name_entry()


func _show_name_entry() -> void:
	var screen: Control = load("res://scenes/screens/name_entry.gd").new()
	screen.name_confirmed.connect(_on_name_confirmed)
	_swap(screen)


func _show_main_menu() -> void:
	var screen: Control = load("res://scenes/screens/main_menu.gd").new()
	screen.player_name = _player_name
	screen.room_created.connect(_on_room_created)
	screen.room_joined.connect(_on_room_joined)
	_swap(screen)


func _show_lobby(room_code: String, players: Array) -> void:
	var screen: Control = load("res://scenes/screens/lobby.gd").new()
	screen.player_name = _player_name
	screen.room_code = room_code
	screen.initial_players = players
	screen.left_room.connect(_on_left_room)
	screen.game_starting.connect(_on_game_starting)
	_swap(screen)


func _show_game() -> void:
	var screen: Node3D = load("res://scenes/game/game.gd").new()
	screen.left_game.connect(_on_left_game)
	_swap(screen)


func _swap(new_screen: Node) -> void:
	if _current_screen != null:
		_current_screen.queue_free()
	_current_screen = new_screen
	add_child(_current_screen)
	if new_screen is Control:
		(new_screen as Control).set_anchors_preset(Control.PRESET_FULL_RECT)


func _on_name_confirmed(player_name: String) -> void:
	_player_name = player_name
	_show_main_menu()


func _on_room_created(room_code: String) -> void:
	_show_lobby(room_code, [_player_name])


func _on_room_joined(room_code: String, players: Array) -> void:
	_show_lobby(room_code, players)


func _on_left_room() -> void:
	WsClient.disconnect_from_server()
	_show_main_menu()


func _on_game_starting() -> void:
	_show_game()


func _on_left_game() -> void:
	WsClient.send_message({"action": "leave_room"})
	WsClient.disconnect_from_server()
	_show_main_menu()

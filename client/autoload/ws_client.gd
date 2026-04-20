extends Node

signal connected
signal disconnected
signal message_received(data: Dictionary)

var my_player_id: String = ""

var _socket: WebSocketPeer = null
var _is_connected: bool = false


func connect_to_server(url: String) -> void:
	_socket = WebSocketPeer.new()
	var err := _socket.connect_to_url(url)
	if err != OK:
		push_error("WsClient: failed to initiate connection to " + url)


func send_message(data: Dictionary) -> void:
	if _socket == null or not _is_connected:
		push_error("WsClient: send called while not connected")
		return
	_socket.send_text(JSON.stringify(data))


func disconnect_from_server() -> void:
	if _socket != null:
		_socket.close()
	my_player_id = ""


func _process(_delta: float) -> void:
	if _socket == null:
		return
	_socket.poll()
	match _socket.get_ready_state():
		WebSocketPeer.STATE_OPEN:
			if not _is_connected:
				_is_connected = true
				connected.emit()
			while _socket.get_available_packet_count() > 0:
				var raw := _socket.get_packet().get_string_from_utf8()
				var parsed = JSON.parse_string(raw)
				if parsed != null:
					_maybe_store_player_id(parsed)
					message_received.emit(parsed)
		WebSocketPeer.STATE_CLOSING:
			pass
		WebSocketPeer.STATE_CLOSED:
			if _is_connected:
				_is_connected = false
				disconnected.emit()
			_socket = null


func _maybe_store_player_id(data) -> void:
	if typeof(data) != TYPE_DICTIONARY:
		return
	if data.get("event") == "name_set":
		my_player_id = str(data.get("player_id", ""))

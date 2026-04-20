extends CanvasLayer


signal bet_action_requested(action_type: String, amount)  # amount may be null
signal chat_message_sent(text: String)

const FONT_NORMAL := 20
const FONT_HEADER := 24

const PHASE_LABELS := {
	"lobby": "Lobby",
	"class_selection": "Class Selection",
	"round_1": "Bounty Mod 1",
	"round_2": "Bounty",
	"round_3": "Bounty Mod 2",
	"round_4": "Terrain",
	"round_5": "Bounty Mod 3",
	"showdown": "Showdown",
	"hand_end": "Hand Over",
}

# UI
var _top_strip_lbl: Label
var _resistance_banner: Panel
var _resistance_banner_lbl: Label
var _chips_lbl: Label
var _check_call_btn: Button
var _raise_btn: Button
var _fold_btn: Button
var _all_in_btn: Button
var _raise_slider: HSlider
var _raise_commit_btn: Button
var _raise_row: HBoxContainer
var _bet_bar: HBoxContainer

# Chat
var _chat_toggle_btn: Button
var _chat_drawer: PanelContainer
var _chat_log: VBoxContainer
var _chat_scroll: ScrollContainer
var _chat_unread_dot: ColorRect
var _chat_open: bool = false
var _chat_has_unread: bool = false

# Latest-state mirror for tests
var _top_strip_text: String = ""
var _check_call_label: String = "Check"
var _raise_min: int = 1
var _raise_max: int = 1
var _all_in_visible: bool = true
var _bet_bar_interactive: bool = false
var _bet_bar_visible: bool = true
var _resistance_banner_visible: bool = false


func _ready() -> void:
	_build_ui()


func _build_ui() -> void:
	var root := Control.new()
	root.set_anchors_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)

	# Top strip
	var top := PanelContainer.new()
	top.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	top.offset_bottom = 44
	root.add_child(top)
	var top_row := HBoxContainer.new()
	top_row.add_theme_constant_override("separation", 24)
	top.add_child(top_row)
	_top_strip_lbl = Label.new()
	_top_strip_lbl.add_theme_font_size_override("font_size", FONT_NORMAL)
	top_row.add_child(_top_strip_lbl)

	# Resistance banner
	_resistance_banner = Panel.new()
	_resistance_banner.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)
	_resistance_banner.offset_top = 44
	_resistance_banner.offset_bottom = 74
	var res_sb := StyleBoxFlat.new()
	res_sb.bg_color = Color(0.60, 0.18, 0.18)
	_resistance_banner.add_theme_stylebox_override("panel", res_sb)
	_resistance_banner.visible = false
	root.add_child(_resistance_banner)
	_resistance_banner_lbl = Label.new()
	_resistance_banner_lbl.text = "⚠ 25% Resistance Dropped!"
	_resistance_banner_lbl.set_anchors_preset(Control.PRESET_FULL_RECT)
	_resistance_banner_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_resistance_banner_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_resistance_banner_lbl.add_theme_font_size_override("font_size", FONT_NORMAL)
	_resistance_banner.add_child(_resistance_banner_lbl)

	# Bottom-left chips panel
	_chips_lbl = Label.new()
	_chips_lbl.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_LEFT)
	_chips_lbl.offset_left = 16
	_chips_lbl.offset_top = -96
	_chips_lbl.offset_bottom = -16
	_chips_lbl.offset_right = 240
	_chips_lbl.add_theme_font_size_override("font_size", FONT_NORMAL)
	root.add_child(_chips_lbl)

	# Bet bar, bottom-center
	_bet_bar = HBoxContainer.new()
	_bet_bar.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	_bet_bar.offset_top = -72
	_bet_bar.offset_bottom = -16
	_bet_bar.offset_left = -240
	_bet_bar.offset_right = 240
	_bet_bar.add_theme_constant_override("separation", 12)
	root.add_child(_bet_bar)

	_check_call_btn = Button.new()
	_check_call_btn.custom_minimum_size = Vector2(120, 48)
	_check_call_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_check_call_btn.pressed.connect(func(): _emit_check_or_call())
	_bet_bar.add_child(_check_call_btn)

	_raise_btn = Button.new()
	_raise_btn.text = "Raise"
	_raise_btn.custom_minimum_size = Vector2(96, 48)
	_raise_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_raise_btn.pressed.connect(func(): _raise_row.visible = not _raise_row.visible)
	_bet_bar.add_child(_raise_btn)

	_fold_btn = Button.new()
	_fold_btn.text = "Fold"
	_fold_btn.custom_minimum_size = Vector2(96, 48)
	_fold_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_fold_btn.pressed.connect(func(): bet_action_requested.emit("fold", null))
	_bet_bar.add_child(_fold_btn)

	_all_in_btn = Button.new()
	_all_in_btn.text = "All-In"
	_all_in_btn.custom_minimum_size = Vector2(96, 48)
	_all_in_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_all_in_btn.pressed.connect(func(): bet_action_requested.emit("all_in", null))
	_bet_bar.add_child(_all_in_btn)

	# Raise slider row — hidden by default, sits above bet bar
	_raise_row = HBoxContainer.new()
	_raise_row.set_anchors_and_offsets_preset(Control.PRESET_CENTER_BOTTOM)
	_raise_row.offset_top = -132
	_raise_row.offset_bottom = -76
	_raise_row.offset_left = -240
	_raise_row.offset_right = 240
	_raise_row.add_theme_constant_override("separation", 12)
	_raise_row.visible = false
	root.add_child(_raise_row)

	_raise_slider = HSlider.new()
	_raise_slider.custom_minimum_size = Vector2(240, 48)
	_raise_slider.step = 1
	_raise_row.add_child(_raise_slider)

	_raise_commit_btn = Button.new()
	_raise_commit_btn.text = "Confirm Raise"
	_raise_commit_btn.custom_minimum_size = Vector2(140, 48)
	_raise_commit_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_raise_commit_btn.pressed.connect(func():
		bet_action_requested.emit("raise", int(_raise_slider.value))
		_raise_row.visible = false
	)
	_raise_row.add_child(_raise_commit_btn)

	# Chat toggle + drawer (bottom-right)
	_chat_toggle_btn = Button.new()
	_chat_toggle_btn.text = "Chat ▲"
	_chat_toggle_btn.custom_minimum_size = Vector2(120, 48)
	_chat_toggle_btn.add_theme_font_size_override("font_size", FONT_NORMAL)
	_chat_toggle_btn.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	_chat_toggle_btn.offset_left = -140
	_chat_toggle_btn.offset_right = -16
	_chat_toggle_btn.offset_top = -64
	_chat_toggle_btn.offset_bottom = -16
	_chat_toggle_btn.pressed.connect(_toggle_chat)
	root.add_child(_chat_toggle_btn)

	_chat_unread_dot = ColorRect.new()
	_chat_unread_dot.color = Color(0.95, 0.35, 0.35)
	_chat_unread_dot.custom_minimum_size = Vector2(12, 12)
	_chat_unread_dot.set_anchors_preset(Control.PRESET_TOP_RIGHT)
	_chat_unread_dot.position = Vector2(-14, 4)
	_chat_unread_dot.visible = false
	_chat_toggle_btn.add_child(_chat_unread_dot)

	_chat_drawer = PanelContainer.new()
	_chat_drawer.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_RIGHT)
	_chat_drawer.offset_left = -256
	_chat_drawer.offset_right = -16
	_chat_drawer.offset_top = -260
	_chat_drawer.offset_bottom = -72
	_chat_drawer.visible = false
	root.add_child(_chat_drawer)

	_chat_scroll = ScrollContainer.new()
	_chat_drawer.add_child(_chat_scroll)
	_chat_log = VBoxContainer.new()
	_chat_log.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_chat_log.add_theme_constant_override("separation", 4)
	_chat_scroll.add_child(_chat_log)


func update(snap: Dictionary, my_player_id: String) -> void:
	var me = _find_me(snap, my_player_id)
	var current_pid = snap.get("current_player_id")
	var is_my_turn := current_pid != null and str(current_pid) == my_player_id

	# Top strip
	var phase_label := str(PHASE_LABELS.get(str(snap.get("phase", "")), str(snap.get("phase", ""))))
	var turn_text := ""
	if is_my_turn:
		turn_text = "YOUR TURN"
	else:
		var waiting_name := ""
		for p in snap.get("players", []):
			if str(p.get("player_id", "")) == str(current_pid):
				waiting_name = str(p.get("name", ""))
				break
		turn_text = "Waiting for %s" % waiting_name if waiting_name != "" else ""
	_top_strip_text = "Room: %s    %s    Pot: %dcp    %s" % [
		str(snap.get("room_code", "")),
		phase_label,
		int(snap.get("pot", 0)),
		turn_text,
	]
	_top_strip_lbl.text = _top_strip_text

	# Resistance banner
	_resistance_banner_visible = bool(snap.get("resistance_dropped", false))
	_resistance_banner.visible = _resistance_banner_visible

	# Chips panel
	var chips := int(me.get("chips", 0)) if me else 0
	var my_bet := int(me.get("bet_this_round", 0)) if me else 0
	_chips_lbl.text = "Chips: %dcp\nBet: %dcp" % [chips, my_bet]

	# Bet bar visibility — hide entirely if folded or all-in
	var folded := bool(me.get("folded", false)) if me else false
	var all_in := bool(me.get("all_in", false)) if me else false
	_bet_bar_visible = not (folded or all_in)
	_bet_bar.visible = _bet_bar_visible
	_raise_row.visible = _raise_row.visible and _bet_bar_visible

	# Check/Call label
	var current_bet := int(snap.get("current_bet", 0))
	if current_bet == my_bet:
		_check_call_label = "Check"
	else:
		_check_call_label = "Call %dcp" % (current_bet - my_bet)
	_check_call_btn.text = _check_call_label

	# All-in visibility — hide if you'd only be calling
	_all_in_visible = chips > current_bet
	_all_in_btn.visible = _all_in_visible

	# Raise bounds
	_raise_min = current_bet + 1
	_raise_max = int(snap.get("max_raise", _raise_min))
	if _raise_max < _raise_min:
		_raise_max = _raise_min
	_raise_slider.min_value = _raise_min
	_raise_slider.max_value = _raise_max
	if _raise_slider.value < _raise_min:
		_raise_slider.value = _raise_min

	# Interactivity
	_bet_bar_interactive = is_my_turn and _bet_bar_visible
	_check_call_btn.disabled = not _bet_bar_interactive
	_raise_btn.disabled = not _bet_bar_interactive
	_fold_btn.disabled = not _bet_bar_interactive
	_all_in_btn.disabled = not _bet_bar_interactive
	_bet_bar.modulate = Color(1, 1, 1, 1.0 if _bet_bar_interactive else 0.3)


func _find_me(snap: Dictionary, my_player_id: String):
	for p in snap.get("players", []):
		if str(p.get("player_id", "")) == my_player_id:
			return p
	return null


func _emit_check_or_call() -> void:
	if _check_call_label == "Check":
		bet_action_requested.emit("check", null)
	else:
		bet_action_requested.emit("call", null)


func add_chat_message(from: String, text: String) -> void:
	var lbl := Label.new()
	lbl.text = "%s: %s" % [from, text]
	lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	lbl.add_theme_font_size_override("font_size", 16)
	_chat_log.add_child(lbl)
	_scroll_chat_to_bottom()
	if not _chat_open:
		_chat_has_unread = true
		_chat_unread_dot.visible = true


func _toggle_chat() -> void:
	_chat_open = not _chat_open
	_chat_drawer.visible = _chat_open
	_chat_toggle_btn.text = "Chat ▼" if _chat_open else "Chat ▲"
	if _chat_open:
		_chat_has_unread = false
		_chat_unread_dot.visible = false


func _scroll_chat_to_bottom() -> void:
	# Guard against orphan-tree tests where get_tree() is null.
	if get_tree() == null:
		return
	await get_tree().process_frame
	if is_instance_valid(_chat_scroll):
		_chat_scroll.scroll_vertical = int(_chat_scroll.get_v_scroll_bar().max_value)


# --- Test introspection ---

func top_strip_text() -> String:
	return _top_strip_text


func check_call_label() -> String:
	return _check_call_label


func raise_min() -> int:
	return _raise_min


func raise_max() -> int:
	return _raise_max


func all_in_visible() -> bool:
	return _all_in_visible


func bet_bar_interactive() -> bool:
	return _bet_bar_interactive


func bet_bar_visible() -> bool:
	return _bet_bar_visible


func resistance_banner_visible() -> bool:
	return _resistance_banner_visible


func chat_unread_dot_visible() -> bool:
	return _chat_has_unread


func chat_drawer_open() -> bool:
	return _chat_open

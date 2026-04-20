extends Control


signal leave_game_requested

const FONT_TITLE := 26
const FONT_ROW := 18
const FONT_SMALL := 14
const CardFace := preload("res://components/card_face.gd")

const COLOR_WIN_BG := Color(0.32, 0.24, 0.06, 0.65)
const COLOR_WIN_BORDER := Color(0.95, 0.82, 0.30)
const COLOR_FOLDED_FG := Color(0.60, 0.60, 0.60)


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var dim := ColorRect.new()
	dim.color = Color(0, 0, 0, 0.7)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)


func show_showdown(snap: Dictionary) -> void:
	# Clear any previous content besides the dim layer
	for c in get_children().slice(1):
		c.queue_free()

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.offset_left = -500
	panel.offset_right = 500
	panel.offset_top = -320
	panel.offset_bottom = 320
	add_child(panel)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 10)
	panel.add_child(vbox)

	# Title
	var sd: Dictionary = snap.get("showdown", {})
	var winners: Array = sd.get("winner_ids", []) as Array
	var players: Array = snap.get("players", []) as Array
	var title := Label.new()
	title.text = _title_text(winners, players)
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", FONT_TITLE)
	vbox.add_child(title)

	# Board reference strip
	vbox.add_child(_build_board_row(snap))

	# Rows per player
	for p in players:
		vbox.add_child(_build_row(p, sd))

	var leave_btn := Button.new()
	leave_btn.text = "Leave Game"
	leave_btn.custom_minimum_size = Vector2(0, 48)
	leave_btn.add_theme_font_size_override("font_size", FONT_ROW)
	leave_btn.pressed.connect(func(): leave_game_requested.emit())
	vbox.add_child(leave_btn)


func _title_text(winners: Array, players: Array) -> String:
	if winners.is_empty():
		return "Showdown"
	var names := []
	for p in players:
		if str(p.get("player_id", "")) in winners:
			names.append(str(p.get("name", "?")))
	if names.size() == 1:
		return "%s wins the hand" % names[0]
	return "%s split the pot" % ", ".join(names)


func _build_board_row(snap: Dictionary) -> Control:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 8)
	var lbl := Label.new()
	lbl.text = "Board: "
	lbl.add_theme_font_size_override("font_size", FONT_SMALL)
	row.add_child(lbl)
	var board: Dictionary = snap.get("board", {})
	for m in board.get("mods_revealed", []):
		var mlbl := Label.new()
		mlbl.text = "Mod %+d %s" % [int(m.get("modifier", 0)), str(m.get("affected_type", ""))]
		mlbl.add_theme_font_size_override("font_size", FONT_SMALL)
		row.add_child(mlbl)
	if board.get("bounty"):
		var blbl := Label.new()
		blbl.text = "Bounty: %s" % str(board["bounty"].get("name", ""))
		blbl.add_theme_font_size_override("font_size", FONT_SMALL)
		row.add_child(blbl)
	if board.get("terrain"):
		var tlbl := Label.new()
		tlbl.text = "Terrain: %s" % str(board["terrain"].get("name", ""))
		tlbl.add_theme_font_size_override("font_size", FONT_SMALL)
		row.add_child(tlbl)
	if bool(snap.get("resistance_dropped", false)):
		var rlbl := Label.new()
		rlbl.text = "  (25% resistance dropped)"
		rlbl.add_theme_font_size_override("font_size", FONT_SMALL)
		rlbl.modulate = Color(1.0, 0.5, 0.3)
		row.add_child(rlbl)
	return row


func _build_row(player: Dictionary, sd: Dictionary) -> Control:
	var pid := str(player.get("player_id", ""))
	var is_winner := pid in (sd.get("winner_ids", []) as Array)
	var is_folded := bool(player.get("folded", false))

	var pc := PanelContainer.new()
	if is_winner:
		var sb := StyleBoxFlat.new()
		sb.bg_color = COLOR_WIN_BG
		sb.border_color = COLOR_WIN_BORDER
		sb.border_width_left = 4
		pc.add_theme_stylebox_override("panel", sb)

	var hbox := HBoxContainer.new()
	hbox.add_theme_constant_override("separation", 12)
	pc.add_child(hbox)

	# Name + class column
	var name_box := VBoxContainer.new()
	name_box.custom_minimum_size = Vector2(140, 0)
	var name_lbl := Label.new()
	name_lbl.text = str(player.get("name", "?"))
	name_lbl.add_theme_font_size_override("font_size", FONT_ROW)
	name_box.add_child(name_lbl)
	var class_lbl := Label.new()
	var cls_name := str(player.get("class_name", "") if player.get("class_name") != null else "")
	class_lbl.text = "%s%s" % [cls_name, "  (folded)" if is_folded else ""]
	class_lbl.add_theme_font_size_override("font_size", FONT_SMALL)
	name_box.add_child(class_lbl)
	hbox.add_child(name_box)

	# 5 cards
	var cards_row := HBoxContainer.new()
	cards_row.add_theme_constant_override("separation", 4)
	hbox.add_child(cards_row)
	if is_folded:
		for i in range(5):
			_append_folded_placeholder(cards_row)
	else:
		var revealed: Dictionary = (sd.get("revealed_hands", {}) as Dictionary).get(pid, {})
		_append_face(cards_row, revealed.get("class_card", {}), "class")
		_append_face(cards_row, revealed.get("weapon", {}), "weapon")
		_append_face(cards_row, revealed.get("item", {}), "item")
		_append_face(cards_row, revealed.get("infusion", {}), "infusion")
		var fourth = revealed.get("fourth_card", {})
		var fourth_type := "infusion" if fourth.has("infusion_type") else "item"
		_append_face(cards_row, fourth, fourth_type)

	# Damage + math helper
	var dmg_box := VBoxContainer.new()
	dmg_box.custom_minimum_size = Vector2(140, 0)
	var dmg_lbl := Label.new()
	var damages: Dictionary = sd.get("damages", {}) as Dictionary
	if is_folded or not damages.has(pid):
		dmg_lbl.text = "—"
	else:
		dmg_lbl.text = "%d dmg" % int(damages[pid])
	dmg_lbl.add_theme_font_size_override("font_size", FONT_ROW)
	dmg_box.add_child(dmg_lbl)

	var math_lbl := Label.new()
	math_lbl.text = _format_math_helper(pid, sd)
	math_lbl.add_theme_font_size_override("font_size", FONT_SMALL)
	math_lbl.modulate = Color(0.75, 0.75, 0.75)
	dmg_box.add_child(math_lbl)
	hbox.add_child(dmg_box)

	# Chips change
	var chips_lbl := Label.new()
	chips_lbl.custom_minimum_size = Vector2(100, 0)
	var won := int((sd.get("pot_distribution", {}) as Dictionary).get(pid, 0))
	chips_lbl.text = ("+%d cp" % won) if won > 0 else "—"
	chips_lbl.add_theme_font_size_override("font_size", FONT_ROW)
	hbox.add_child(chips_lbl)

	if is_folded:
		pc.modulate = Color(1, 1, 1, 0.5)

	return pc


func _append_face(parent: Container, card: Dictionary, type_label: String) -> void:
	var face := CardFace.new()
	face.custom_minimum_size = Vector2(80, 112)
	face.set_card(card, type_label)
	parent.add_child(face)


func _append_folded_placeholder(parent: Container) -> void:
	var rect := ColorRect.new()
	rect.color = Color(0.18, 0.18, 0.18)
	rect.custom_minimum_size = Vector2(80, 112)
	parent.add_child(rect)


func _format_math_helper(pid: String, sd: Dictionary) -> String:
	var bd: Dictionary = (sd.get("damage_breakdown", {}) as Dictionary).get(pid, {})
	if bd.is_empty():
		return ""
	var parts := []
	parts.append(str(int(bd.get("weapon", 0))))
	parts.append(str(int(bd.get("class", 0))))
	for v in bd.get("items", []):
		parts.append(str(int(v)))
	var mods := int(bd.get("mods_sum", 0))
	if mods != 0:
		parts.append("%+d" % mods)
	var base_str := " + ".join(parts)
	var mult = bd.get("infusion_mult", 1.0)
	var total := int(bd.get("total", 0))
	return "%s → %d × %s" % [base_str, total, str(mult)]

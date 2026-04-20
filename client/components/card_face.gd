extends Control


const FACE_SIZE := Vector2(256, 358)
const COLOR_BG := Color(0.12, 0.14, 0.20, 1.0)
const COLOR_BORDER := Color(0.55, 0.60, 0.75, 1.0)
const COLOR_NAME := Color(1.0, 1.0, 1.0, 1.0)
const COLOR_TYPE := Color(0.90, 0.75, 0.25, 1.0)
const COLOR_STAT := Color(0.90, 0.90, 0.90, 1.0)

var _name_lbl: Label
var _type_lbl: Label
var _stat_lbl: Label


func _init() -> void:
	custom_minimum_size = FACE_SIZE
	size = FACE_SIZE
	var bg := ColorRect.new()
	bg.color = COLOR_BG
	bg.size = FACE_SIZE
	add_child(bg)

	var border := Panel.new()
	border.size = FACE_SIZE
	var sb := StyleBoxFlat.new()
	sb.bg_color = Color(0, 0, 0, 0)
	sb.border_color = COLOR_BORDER
	sb.border_width_left = 4
	sb.border_width_right = 4
	sb.border_width_top = 4
	sb.border_width_bottom = 4
	sb.corner_radius_top_left = 10
	sb.corner_radius_top_right = 10
	sb.corner_radius_bottom_left = 10
	sb.corner_radius_bottom_right = 10
	border.add_theme_stylebox_override("panel", sb)
	add_child(border)

	_type_lbl = Label.new()
	_type_lbl.position = Vector2(16, 14)
	_type_lbl.size = Vector2(FACE_SIZE.x - 32, 24)
	_type_lbl.add_theme_color_override("font_color", COLOR_TYPE)
	_type_lbl.add_theme_font_size_override("font_size", 18)
	add_child(_type_lbl)

	_name_lbl = Label.new()
	_name_lbl.position = Vector2(16, 52)
	_name_lbl.size = Vector2(FACE_SIZE.x - 32, 40)
	_name_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_name_lbl.add_theme_color_override("font_color", COLOR_NAME)
	_name_lbl.add_theme_font_size_override("font_size", 26)
	add_child(_name_lbl)

	_stat_lbl = Label.new()
	_stat_lbl.position = Vector2(16, FACE_SIZE.y - 60)
	_stat_lbl.size = Vector2(FACE_SIZE.x - 32, 44)
	_stat_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_stat_lbl.add_theme_color_override("font_color", COLOR_STAT)
	_stat_lbl.add_theme_font_size_override("font_size", 20)
	add_child(_stat_lbl)


func set_card(card: Dictionary, type_label: String) -> void:
	_type_lbl.text = type_label.to_upper()
	_name_lbl.text = str(card.get("name", ""))
	_stat_lbl.text = _format_stat(card, type_label)


func get_name_text() -> String:
	return _name_lbl.text


func get_type_text() -> String:
	return _type_lbl.text


func get_stat_text() -> String:
	return _stat_lbl.text


func _format_stat(card: Dictionary, type_label: String) -> String:
	match type_label:
		"weapon":
			return _format_damage_types(card.get("damage_types", []))
		"class":
			return _format_formulas(card.get("damage_formulas", []))
		"item":
			var bonus = card.get("bonus_value", null)
			var dtype := str(card.get("damage_type", ""))
			if bonus == null:
				return ""
			return "+%s %s" % [str(bonus), dtype]
		"infusion":
			var itype := str(card.get("infusion_type", ""))
			if itype == "":
				return ""
			return itype.to_upper()
		_:
			return ""


func _format_damage_types(pairs) -> String:
	if pairs == null or pairs.size() == 0:
		return ""
	var parts := []
	for pair in pairs:
		parts.append("%s %s" % [str(pair[0]), str(pair[1])])
	return ", ".join(parts)


func _format_formulas(pairs) -> String:
	if pairs == null or pairs.size() == 0:
		return ""
	var parts := []
	for pair in pairs:
		parts.append("%s (%s)" % [str(pair[0]), str(pair[1])])
	return ", ".join(parts)

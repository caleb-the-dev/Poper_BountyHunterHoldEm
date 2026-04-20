extends Control


signal dismissed

const FONT_TITLE := 28
const FONT_BUTTON := 22
const CardFace := preload("res://components/card_face.gd")


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP


func _ready() -> void:
	set_anchors_preset(Control.PRESET_FULL_RECT)
	var dim := ColorRect.new()
	dim.name = "_dim_bg"
	dim.color = Color(0, 0, 0, 0.6)
	dim.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(dim)


func show_reveal(priv: Dictionary) -> void:
	# Clear any previous content besides the dim layer
	for c in get_children():
		if c.name != "_dim_bg":
			c.queue_free()

	var panel := PanelContainer.new()
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.offset_left = -360
	panel.offset_right = 360
	panel.offset_top = -260
	panel.offset_bottom = 260
	add_child(panel)

	var vbox := VBoxContainer.new()
	vbox.add_theme_constant_override("separation", 16)
	panel.add_child(vbox)

	var title := Label.new()
	title.text = "YOUR HAND"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", FONT_TITLE)
	vbox.add_child(title)

	# Single row: class + 4 hand cards
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	row.alignment = BoxContainer.ALIGNMENT_CENTER
	vbox.add_child(row)

	var class_card: Dictionary = priv.get("class_card", {})
	var hand: Dictionary = priv.get("hand", {})
	_append_card(row, class_card, "class")
	_append_card(row, hand.get("weapon", {}), "weapon")
	_append_card(row, hand.get("item", {}), "item")
	_append_card(row, hand.get("infusion", {}), "infusion")
	var fourth: Dictionary = hand.get("fourth_card", {})
	var fourth_type := "infusion" if fourth.has("infusion_type") else "item"
	_append_card(row, fourth, fourth_type)

	var begin_btn := Button.new()
	begin_btn.text = "Begin Round 1 ▸"
	begin_btn.custom_minimum_size = Vector2(0, 56)
	begin_btn.add_theme_font_size_override("font_size", FONT_BUTTON)
	begin_btn.pressed.connect(func():
		dismissed.emit()
		queue_free()
	)
	vbox.add_child(begin_btn)


func _append_card(parent: Container, card: Dictionary, type_label: String) -> void:
	var face := CardFace.new()
	# Half render size — reveal shows all 5 cards side-by-side, space is tight.
	face.custom_minimum_size = Vector2(128, 179)
	face.set_card(card, type_label)
	parent.add_child(face)

extends Control

signal name_confirmed(player_name: String)

var _name_input: LineEdit
var _continue_btn: Button


func _ready() -> void:
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	add_child(center)

	var vbox := VBoxContainer.new()
	vbox.custom_minimum_size = Vector2(400, 0)
	center.add_child(vbox)

	var title := Label.new()
	title.text = "Poper: Bounty Hunter Hold'em"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	vbox.add_child(title)

	vbox.add_child(_spacer(24))

	var lbl := Label.new()
	lbl.text = "Enter your name:"
	vbox.add_child(lbl)

	_name_input = LineEdit.new()
	_name_input.placeholder_text = "Your name"
	_name_input.max_length = 32
	_name_input.text_changed.connect(_on_text_changed)
	_name_input.text_submitted.connect(func(_t): _submit())
	vbox.add_child(_name_input)

	vbox.add_child(_spacer(8))

	_continue_btn = Button.new()
	_continue_btn.text = "Continue"
	_continue_btn.disabled = true
	_continue_btn.pressed.connect(_submit)
	vbox.add_child(_continue_btn)


func _spacer(height: int) -> Control:
	var s := Control.new()
	s.custom_minimum_size = Vector2(0, height)
	return s


func _on_text_changed(text: String) -> void:
	_continue_btn.disabled = text.strip_edges().is_empty()


func _submit() -> void:
	var name := _name_input.text.strip_edges()
	if not name.is_empty():
		name_confirmed.emit(name)

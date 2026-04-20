extends MeshInstance3D


const CARD_WIDTH := 0.5
const CARD_HEIGHT := 0.7
const FACE_SIZE := Vector2i(256, 358)

const COLOR_BACK := Color(0.18, 0.12, 0.28)
const CardFace := preload("res://components/card_face.gd")

var _viewport: SubViewport
var _face: Control
var _face_material: StandardMaterial3D
var _back_material: StandardMaterial3D
var _current: Dictionary = {}
var _current_type: String = ""
var _face_up: bool = false


func _ready() -> void:
	var quad := QuadMesh.new()
	quad.size = Vector2(CARD_WIDTH, CARD_HEIGHT)
	mesh = quad

	_viewport = SubViewport.new()
	_viewport.size = FACE_SIZE
	_viewport.disable_3d = true
	_viewport.transparent_bg = false
	_viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_viewport)

	_face = CardFace.new()
	_viewport.add_child(_face)

	_face_material = StandardMaterial3D.new()
	_face_material.albedo_texture = _viewport.get_texture()
	_face_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED

	_back_material = StandardMaterial3D.new()
	_back_material.albedo_color = COLOR_BACK
	_back_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED

	set_face_down()


func set_card(card: Dictionary, type_label: String) -> void:
	_current = card
	_current_type = type_label
	_face.set_card(card, type_label)
	material_override = _face_material
	_face_up = true


func set_face_down() -> void:
	material_override = _back_material
	_face_up = false


func is_face_up() -> bool:
	return _face_up


func current_card() -> Dictionary:
	return _current


func current_type() -> String:
	return _current_type

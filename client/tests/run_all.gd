extends SceneTree


func _initialize() -> void:
	print("Running Godot UI tests...")
	var fails := 0
	# Each suite class_name is added here as tasks land. class_name makes the
	# class globally referenceable; static run() returns the failure count.
	fails += TestCardFace.run()
	fails += TestBoard.run()
	fails += TestSeats.run()
	fails += TestHud.run()
	if fails == 0:
		print("ALL TESTS PASSED")
		quit(0)
	else:
		print("TESTS FAILED: ", fails)
		quit(1)

extends RefCounted
class_name TestHelpers


static func assert_eq(actual, expected, label: String) -> bool:
	if actual == expected:
		print("  PASS  ", label)
		return true
	print("  FAIL  ", label, " — expected ", expected, " got ", actual)
	return false


static func assert_true(cond: bool, label: String) -> bool:
	if cond:
		print("  PASS  ", label)
		return true
	print("  FAIL  ", label, " — expected true")
	return false


static func assert_false(cond: bool, label: String) -> bool:
	if not cond:
		print("  PASS  ", label)
		return true
	print("  FAIL  ", label, " — expected false")
	return false


static func assert_in(needle, haystack, label: String) -> bool:
	if needle in haystack:
		print("  PASS  ", label)
		return true
	print("  FAIL  ", label, " — ", needle, " not in ", haystack)
	return false

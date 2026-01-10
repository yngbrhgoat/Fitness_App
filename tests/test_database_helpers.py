import exercise_database


def test_normalize_weight_unit_recognizes_kg() -> None:
    """Ensure weight unit normalization returns kg for supported labels."""
    assert exercise_database.normalize_weight_unit("kg") == "kg"
    assert exercise_database.normalize_weight_unit(" KGS ") == "kg"
    assert exercise_database.normalize_weight_unit("kilograms") == "kg"
    assert exercise_database.normalize_weight_unit("lb") is None


def test_normalize_equipment_list_maps_aliases_and_dedupes() -> None:
    """Ensure equipment normalization maps aliases and removes duplicates."""
    items = exercise_database.normalize_equipment_list(
        "Barbell, plates; dumbbells & body weight, mat optional"
    )
    assert items == ["Barbell", "Dumbbell", "Bodyweight", "Mat"]


def test_normalize_equipment_list_handles_iterables_and_nones() -> None:
    """Ensure equipment normalization accepts iterable input with None entries."""
    items = exercise_database.normalize_equipment_list(["barbell", None, "bands"])
    assert items == ["Barbell", "Bands"]


def test_normalize_muscle_group_list_maps_aliases_and_dedupes() -> None:
    """Ensure muscle group normalization expands aliases and de-duplicates."""
    items = exercise_database.normalize_muscle_group_list("glutes and calves")
    assert items == ["Glutes", "Legs", "Posterior Chain", "Calves"]


def test_infer_supports_weight_detects_weight_equipment() -> None:
    """Ensure weight-support inference flags equipment with external loads."""
    assert exercise_database.infer_supports_weight("Bodyweight") is False
    assert exercise_database.infer_supports_weight("Dumbbell, Bodyweight") is True


def test_format_tag_list_skips_empty_items() -> None:
    """Ensure tag formatting ignores empty values."""
    assert exercise_database.format_tag_list(["Chest", "", "Back"]) == "Chest, Back"

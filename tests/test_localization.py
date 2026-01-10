import localization


def test_translate_english_passthrough() -> None:
    """Ensure English translations return formatted source text."""
    result = localization.translate("Current user: {value}", "en", value="Alex")
    assert result == "Current user: Alex"


def test_translate_uses_translation_and_handles_missing_placeholder() -> None:
    """Ensure translations apply and tolerate missing format args."""
    translated = localization.translate("Current user: {value}", "de", value="Alex")
    assert translated == "Aktueller Benutzer: Alex"
    missing = localization.translate("Current user: {value}", "de")
    assert missing == "Aktueller Benutzer: {value}"


def test_translate_unknown_key_returns_input() -> None:
    """Ensure missing translation keys return the input string."""
    assert localization.translate("Unknown text", "de") == "Unknown text"


def test_translate_goal_and_fallback() -> None:
    """Ensure goal labels are translated or fall back to title-case."""
    assert localization.translate_goal("muscle_building", "de") == "Muskelaufbau"
    assert localization.translate_goal("custom_goal", "de") == "Custom Goal"


def test_goal_code_from_label_resolves_codes() -> None:
    """Ensure goal codes resolve from labels and codes."""
    assert localization.goal_code_from_label("muscle_building") == "muscle_building"
    assert localization.goal_code_from_label("Muscle Building") == "muscle_building"
    assert localization.goal_code_from_label("muskelaufbau") == "muscle_building"
    assert localization.goal_code_from_label("Unknown") is None


def test_translate_equipment_and_muscle_labels() -> None:
    """Ensure equipment and muscle labels translate with fallbacks."""
    assert localization.translate_equipment("Machine", "de") == "Maschine"
    assert localization.translate_equipment("Unknown", "de") == "Unknown"
    assert localization.translate_muscle("Chest", "de") == "Brust"
    assert localization.translate_muscle("Unknown", "de") == "Unknown"


def test_translate_exercise_translations_and_fallbacks() -> None:
    """Ensure exercise translation helpers use entries when available."""
    assert localization.translate_exercise_name("Bicycle Crunch", "en") == "Bicycle Crunch"
    assert localization.translate_exercise_name("Unknown", "de") == "Unknown"
    assert localization.translate_exercise_name("Bicycle Crunch", "de") != "Bicycle Crunch"
    assert localization.translate_exercise_description("Bicycle Crunch", "Original", "de") != "Original"
    assert localization.translate_exercise_instructions("Bicycle Crunch", "Original", "de") != "Original"


def test_weekday_labels_and_format_month_year() -> None:
    """Ensure weekday labels and month-year formatting are localized."""
    assert localization.weekday_labels("en") == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert localization.format_month_year(2024, 1, "en") == "January 2024"
    assert localization.format_month_year(2024, 13, "en") == "13 2024"

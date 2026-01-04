import os
import tempfile
import unittest
from pathlib import Path
from types import MethodType, SimpleNamespace

# Keep Kivy quiet and headless during logic tests before importing Kivy modules.
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ.setdefault("KIVY_WINDOW", "mock")
os.environ.setdefault("KIVY_NO_FILELOG", "1")

import exercise_database
import localization
from main import RootWidget


class RecommendationLogicTests(unittest.TestCase):
    """Tests for recommendation scoring and time estimation."""
    def test_score_recommendation_recency_bonus(self) -> None:
        """Validate recency bonus values for recommendation scoring."""
        # Use a lightweight dummy to call the helper as a bound method.
        dummy = object()
        cases = [
            (None, 7.0),
            (20, 6.0),
            (10, 5.5),
            (2, 4.0),
            (5, 5.0),
        ]
        for recency, expected in cases:
            score = RootWidget._score_recommendation(dummy, {"rating": 5}, recency)  # type: ignore[arg-type]
            self.assertEqual(score, expected)

    def test_estimate_minutes_prefers_time_then_volume(self) -> None:
        """Ensure estimate logic prefers time then volume fallbacks."""
        # Cover time-based, rep-based, and fallback estimations.
        dummy = object()
        time_first = RootWidget._estimate_minutes(dummy, {"time_seconds": 125, "sets": 2, "reps": 10})
        volume_based = RootWidget._estimate_minutes(dummy, {"sets": 3, "reps": 10})
        sets_only = RootWidget._estimate_minutes(dummy, {"sets": 3})
        fallback = RootWidget._estimate_minutes(dummy, {})

        self.assertEqual(time_first, 5)  # 2 * 125s + rest
        self.assertEqual(volume_based, 3)  # includes rest between sets
        self.assertEqual(sets_only, 3)  # includes rest between sets
        self.assertEqual(fallback, 5)

    def test_completion_percentage_clamped_and_rounded(self) -> None:
        """Confirm completion percentage clamps to [0, 100]."""
        # Verify rounding and upper bound behavior.
        dummy = object()
        self.assertEqual(RootWidget._compute_completion_percentage(dummy, 0, 4), 0.0)
        self.assertEqual(RootWidget._compute_completion_percentage(dummy, 3, 4), 75.0)
        self.assertEqual(RootWidget._compute_completion_percentage(dummy, 6, 4), 100.0)  # capped at 100%

    def test_tempo_hint_for_reps_rest_and_hold(self) -> None:
        """Check tempo hints for reps, rest, and holds."""
        # Build a minimal stub to exercise _update_tempo_hint branches.
        # Build a lightweight stub that satisfies _update_tempo_hint requirements.
        class TempoStub:
            """Simple stub container for tempo hint tests."""
            def _t(self, text: str, **kwargs) -> str:
                """Return English translations for tempo hint tests."""
                return localization.translate(text, "en", **kwargs)

        stub = TempoStub()
        stub.live_exercises = [{"name": "Push-Up", "reps": 10}]
        stub._live_current_index = 0
        stub._live_set_target_seconds = 40
        stub._live_set_elapsed = 12
        stub._live_phase = "set"
        stub.live_tempo_hint = ""

        def current_exercise():
            """Return the current exercise from the stub list."""
            # Mirror RootWidget._current_live_exercise behavior.
            if 0 <= stub._live_current_index < len(stub.live_exercises):
                return stub.live_exercises[stub._live_current_index]
            return None

        stub._current_live_exercise = current_exercise
        RootWidget._update_tempo_hint(stub)
        self.assertIn("repetition 4", stub.live_tempo_hint)

        # Rest phase
        stub._live_phase = "rest"
        RootWidget._update_tempo_hint(stub)
        self.assertIn("Rest and breathe", stub.live_tempo_hint)

        # Time-based hold
        stub.live_exercises = [{"name": "Plank", "time_seconds": 30}]
        stub._live_phase = "set"
        stub._live_set_target_seconds = 30
        stub._live_set_elapsed = 10
        RootWidget._update_tempo_hint(stub)
        self.assertIn("10s of 30s", stub.live_tempo_hint)


class HistoryAndStatsTests(unittest.TestCase):
    """Tests for workout history filtering and stats aggregation."""
    def test_history_filtering_by_date(self) -> None:
        """Validate filtering history by start/end date."""
        # Write sample data and verify date boundaries.
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            exercise_database.initialize_database(db_path)
            user_id = exercise_database.add_user("alice", db_path=db_path)
            exercise_database.log_workout(
                user_id=user_id,
                performed_at="2024-01-01",
                duration_minutes=30,
                exercises=["Push-Up"],
                db_path=db_path,
            )
            exercise_database.log_workout(
                user_id=user_id,
                performed_at="2024-02-15",
                duration_minutes=40,
                exercises=["Squat"],
                db_path=db_path,
            )

            jan_entries = exercise_database.fetch_workout_history(
                user_id,
                end_date="2024-01-31",
                db_path=db_path,
            )
            feb_entries = exercise_database.fetch_workout_history(
                user_id,
                start_date="2024-02-01",
                db_path=db_path,
            )

            self.assertEqual(len(jan_entries), 1)
            self.assertEqual(jan_entries[0]["performed_at"], "2024-01-01")
            self.assertEqual(len(feb_entries), 1)
            self.assertEqual(feb_entries[0]["performed_at"], "2024-02-15")

    def test_stats_aggregate_and_top_exercise(self) -> None:
        """Validate stats aggregation and top exercise selection."""
        # Insert workouts and verify totals and top exercise counts.
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            exercise_database.initialize_database(db_path)
            user_id = exercise_database.add_user("bob", db_path=db_path)
            exercise_database.log_workout(
                user_id=user_id,
                performed_at="2024-03-01",
                duration_minutes=20,
                exercises=["Jump Rope", "Push-Up"],
                db_path=db_path,
            )
            exercise_database.log_workout(
                user_id=user_id,
                performed_at="2024-03-02",
                duration_minutes=25,
                exercises=["Jump Rope"],
                db_path=db_path,
            )

            stats = exercise_database.fetch_workout_stats(user_id, db_path=db_path)
            self.assertEqual(stats["total_workouts"], 2)
            self.assertEqual(stats["total_minutes"], 45)
            self.assertEqual(stats["top_exercise"], "Jump Rope")
            self.assertEqual(stats["top_exercise_count"], 2)


class ParsingHelperTests(unittest.TestCase):
    """Tests for parsing and normalization helpers."""
    def test_split_exercises_normalizes_commas_and_newlines(self) -> None:
        """Ensure exercise splitting handles commas and newlines."""
        # Confirm trailing separators and blank lines are ignored.
        result = RootWidget._split_exercises(object(), "Push-Up, Squat\n\nPlank, ")
        self.assertEqual(result, ["Push-Up", "Squat", "Plank"])

    def test_parse_date_value_handles_empty_and_invalid(self) -> None:
        """Ensure date parsing handles empty and invalid inputs."""
        # Validate empty and malformed input behavior.
        dummy = object()
        self.assertIsNone(RootWidget._parse_date_value(dummy, "  ", allow_empty=True))
        with self.assertRaises(ValueError):
            RootWidget._parse_date_value(dummy, "  ", allow_empty=False)
        with self.assertRaises(ValueError):
            RootWidget._parse_date_value(dummy, "2024/01/01")

    def test_parse_optional_int_accepts_positive_only(self) -> None:
        """Ensure optional integer parsing enforces positivity."""
        # Cover valid input and multiple invalid cases.
        dummy = object()
        self.assertEqual(RootWidget._parse_optional_int(dummy, "7"), 7)
        with self.assertRaises(ValueError):
            RootWidget._parse_optional_int(dummy, "0")
        with self.assertRaises(ValueError):
            RootWidget._parse_optional_int(dummy, "-3")
        with self.assertRaises(ValueError):
            RootWidget._parse_optional_int(dummy, "abc")

    def test_normalize_equipment_includes_barbell(self) -> None:
        """Ensure equipment normalization maps Barbell aliases."""
        # Use a known alias to confirm normalization.
        items = exercise_database.normalize_equipment_list("Barbell, plates")
        self.assertIn("Barbell", items)

    def test_normalize_muscle_groups_expands_posterior_chain(self) -> None:
        """Ensure muscle normalization expands posterior chain."""
        # Verify alias expansion into multiple groups.
        items = exercise_database.normalize_muscle_group_list("Posterior chain")
        self.assertIn("Back", items)
        self.assertIn("Legs", items)
        self.assertIn("Posterior Chain", items)


class RegressionGuardTests(unittest.TestCase):
    """Regression tests for edge cases in helpers."""
    def test_validate_history_exercises_blocks_unknown(self) -> None:
        """Ensure unknown exercises are flagged in history validation."""
        # Stub the known exercise list to test validation output.
        dummy = SimpleNamespace()
        dummy._known_exercise_names = lambda: {"push-up", "plank"}

        error = RootWidget._validate_history_exercises(dummy, ["Push-Up", "Row"])
        self.assertIn("Unknown exercises", error)
        self.assertIsNone(RootWidget._validate_history_exercises(dummy, ["Plank"]))

    def test_resolve_equipment_choice_prefers_available_option(self) -> None:
        """Ensure equipment choice prefers valid options and fallback."""
        # Validate Bodyweight preference when present.
        dummy = SimpleNamespace(equipment_choice_options=["Barbell", "Bands"])
        first_choice = RootWidget._resolve_equipment_choice(dummy, "")
        self.assertEqual(first_choice, "Barbell")

        dummy.equipment_choice_options.append("Bodyweight")
        prefer_bodyweight = RootWidget._resolve_equipment_choice(dummy, "")
        self.assertEqual(prefer_bodyweight, "Bodyweight")

        fallback = RootWidget._resolve_equipment_choice(SimpleNamespace(equipment_choice_options=[]), "")
        self.assertEqual(fallback, "Bodyweight")

    def test_toggle_recommendation_details_uses_boolean(self) -> None:
        """Ensure detail toggling flips boolean state per item."""
        # Use stubs to avoid Kivy dependencies.
        rec_list = SimpleNamespace(data=[], refresh_from_data=lambda: None)
        rec_screen = SimpleNamespace(ids=SimpleNamespace(rec_list=rec_list))
        dummy = SimpleNamespace(
            rec_recommendations=[
                {"name": "A", "show_details": False},
                {"name": "B", "show_details": False},
            ]
        )
        dummy._find_recommendation = lambda name: next((r for r in dummy.rec_recommendations if r["name"] == name), None)
        dummy._recommend_screen = lambda: rec_screen
        dummy._set_rec_status = lambda *args, **kwargs: None

        RootWidget.toggle_recommendation_details(dummy, "A")
        self.assertTrue(dummy.rec_recommendations[0]["show_details"])
        self.assertFalse(dummy.rec_recommendations[1]["show_details"])

        RootWidget.toggle_recommendation_details(dummy, "A")
        self.assertFalse(dummy.rec_recommendations[0]["show_details"])

    def test_plan_goal_label_handles_mixed_goals(self) -> None:
        """Ensure plan goal labeling handles mixed goals."""
        # Verify mixed goals report as "Multiple goals".
        multi = SimpleNamespace(rec_plan=[{"goal_label": "Muscle Building"}, {"goal_label": "Weight Loss"}])
        self.assertEqual(RootWidget._plan_goal_label(multi), "Multiple goals")

        single = SimpleNamespace(rec_plan=[{"goal_label": "Endurance"}])
        self.assertEqual(RootWidget._plan_goal_label(single), "Endurance")

    def test_generate_recommendations_keeps_existing_plan(self) -> None:
        """Ensure recommendation generation does not clear a valid plan."""
        # Use a stub with a pre-existing plan entry.
        rec_list = SimpleNamespace(data=[], refresh_from_data=lambda: None)
        rec_ids = SimpleNamespace(rec_max_time=SimpleNamespace(text="30"), rec_list=rec_list)
        rec_screen = SimpleNamespace(ids=rec_ids)
        stub = SimpleNamespace(
            rec_plan=[
                {"name": "Push-Up", "estimated_minutes": "5", "goal": "muscle_building", "goal_label": "Muscle Building", "display": "Push-Up (5 min) - Muscle Building"}
            ],
            rec_recommendations=[],
            rec_goal_spinner_text="Muscle Building",
            rec_max_minutes_text="30",
            records=[
                {
                    "name": "Push-Up",
                    "goal": "muscle_building",
                    "description": "desc",
                    "muscle_group": "Chest",
                    "equipment": "Bodyweight",
                    "suitability_display": "8/10",
                    "sets": 3,
                    "reps": 10,
                    "time_seconds": None,
                    "recommendation": "Do it",
                    "goal_label": "Muscle Building",
                    "rating": 8,
                },
                {
                    "name": "Row",
                    "goal": "muscle_building",
                    "description": "desc",
                    "muscle_group": "Back",
                    "equipment": "Cable",
                    "suitability_display": "7/10",
                    "sets": 3,
                    "reps": 12,
                    "time_seconds": None,
                    "recommendation": "Rows",
                    "goal_label": "Muscle Building",
                    "rating": 7,
                },
            ],
            _goal_label_map={"Muscle Building": "muscle_building"},
        )
        stub._require_user = lambda: True
        stub._recency_days_map = lambda: {}
        stub._recommend_screen = lambda: rec_screen
        stub._set_rec_status = lambda *args, **kwargs: None
        stub._estimate_minutes = MethodType(RootWidget._estimate_minutes, stub)
        stub._estimate_exercise_seconds = MethodType(RootWidget._estimate_exercise_seconds, stub)
        stub._minutes_from_seconds = MethodType(RootWidget._minutes_from_seconds, stub)
        stub._score_recommendation = MethodType(RootWidget._score_recommendation, stub)
        stub._plan_goal_label = MethodType(RootWidget._plan_goal_label, stub)

        RootWidget.handle_generate_recommendations(stub)
        self.assertEqual(len(stub.rec_plan), 1)
        self.assertEqual(stub.rec_plan[0]["name"], "Push-Up")
        self.assertTrue(all("goal_label" in rec for rec in stub.rec_recommendations))


if __name__ == "__main__":
    unittest.main()

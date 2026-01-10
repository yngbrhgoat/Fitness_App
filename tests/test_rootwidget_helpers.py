from main import RootWidget


class DummyRootContext:
    """Minimal context for exercising RootWidget helper methods."""

    _rest_seconds_for_plan = RootWidget._rest_seconds_for_plan
    _estimate_exercise_seconds = RootWidget._estimate_exercise_seconds
    _compute_set_target_seconds = RootWidget._compute_set_target_seconds

    def __init__(self) -> None:
        """Initialize the dummy context with default state."""
        self.live_rest_seconds = 30
        self.rec_plan = []
        self._live_current_index = 0
        self.live_exercises = []
        self.live_active = False
        self.live_started = False
        self._live_phase = "set"
        self._live_rest_remaining = 0.0
        self._live_set_target_seconds = 0.0
        self._live_set_elapsed = 0.0
        self._live_attempt_log = []
        self._live_skipped = []

    def _current_live_exercise(self) -> dict[str, object] | None:
        """Return the current exercise from the dummy live list."""
        if 0 <= self._live_current_index < len(self.live_exercises):
            return self.live_exercises[self._live_current_index]
        return None

    def _t(self, text: str, **kwargs: object) -> str:
        """Return formatted text without localization."""
        return text.format(**kwargs)


def test_format_time_zero_pads_and_clamps() -> None:
    """Ensure time formatting clamps negatives and zero-pads output."""
    ctx = DummyRootContext()
    assert RootWidget._format_time(ctx, -5) == "00:00"
    assert RootWidget._format_time(ctx, 61.2) == "01:01"


def test_compute_set_target_seconds_prefers_time_then_reps() -> None:
    """Ensure set targets prefer explicit time and then reps."""
    ctx = DummyRootContext()
    assert RootWidget._compute_set_target_seconds(ctx, {"time_seconds": 5}) == 10.0
    assert RootWidget._compute_set_target_seconds(ctx, {"reps": 3}) == 20.0
    assert RootWidget._compute_set_target_seconds(ctx, None) == 30.0


def test_exercise_expected_duration_seconds_includes_rest_and_estimate() -> None:
    """Ensure expected duration includes rest and honors estimate floor."""
    ctx = DummyRootContext()
    ctx.live_rest_seconds = 30
    exercise = {"sets": 3, "reps": 10}
    assert RootWidget._exercise_expected_duration_seconds(ctx, exercise) == 180.0
    exercise["estimated_minutes"] = 4
    assert RootWidget._exercise_expected_duration_seconds(ctx, exercise) == 240.0


def test_compute_live_progress_ratio_handles_rest_and_set() -> None:
    """Ensure live progress ratio accounts for phase and remaining time."""
    ctx = DummyRootContext()
    ctx.live_exercises = [{"name": "Push-Up"}]
    ctx.live_active = True
    ctx.live_started = True
    ctx._live_phase = "rest"
    ctx.live_rest_seconds = 20
    ctx._live_rest_remaining = 5
    assert RootWidget._compute_live_progress_ratio(ctx) == -0.75
    ctx._live_phase = "set"
    ctx._live_set_target_seconds = 40
    ctx._live_set_elapsed = 10
    assert RootWidget._compute_live_progress_ratio(ctx) == -0.75


def test_collect_attempts_marks_unattempted_skipped() -> None:
    """Ensure unattempted exercises are marked skipped when needed."""
    ctx = DummyRootContext()
    ctx.live_exercises = [{"name": "Push-Up"}, {"name": "Squat"}]
    ctx._live_attempt_log = [{"name": "Push-Up", "status": "completed"}]
    attempts = RootWidget._collect_attempts(ctx, mark_unattempted_skipped=True)
    statuses = {att["name"]: att["status"] for att in attempts}
    assert statuses == {"Push-Up": "completed", "Squat": "skipped"}
    assert ctx._live_skipped == ["Squat"]


def test_collect_attempts_marks_all_skipped_when_empty() -> None:
    """Ensure empty attempt logs default to skipped exercises."""
    ctx = DummyRootContext()
    ctx.live_exercises = [{"name": "Push-Up"}, {"name": "Squat"}]
    attempts = RootWidget._collect_attempts(ctx, mark_unattempted_skipped=False)
    statuses = {att["name"]: att["status"] for att in attempts}
    assert statuses == {"Push-Up": "skipped", "Squat": "skipped"}


def test_plan_goal_label_handles_empty_and_multiple() -> None:
    """Ensure plan goal label summarizes single or mixed goals."""
    ctx = DummyRootContext()
    assert RootWidget._plan_goal_label(ctx) == ""
    ctx.rec_plan = [{"goal_label": "Strength"}]
    assert RootWidget._plan_goal_label(ctx) == "Strength"
    ctx.rec_plan = [{"goal_label": "Strength"}, {"goal_label": "Endurance"}]
    assert RootWidget._plan_goal_label(ctx) == "Multiple goals"


def test_rest_seconds_for_plan_handles_invalid() -> None:
    """Ensure rest seconds fall back when input is invalid."""
    ctx = DummyRootContext()
    ctx.live_rest_seconds = "bad"
    assert RootWidget._rest_seconds_for_plan(ctx) == 30
    ctx.live_rest_seconds = "45"
    assert RootWidget._rest_seconds_for_plan(ctx) == 45


def test_minutes_from_seconds_rounds_up() -> None:
    """Ensure minute conversion rounds up partial minutes."""
    ctx = DummyRootContext()
    assert RootWidget._minutes_from_seconds(ctx, 0) == 0
    assert RootWidget._minutes_from_seconds(ctx, 61) == 2


def test_estimate_plan_seconds_includes_rest_between_items() -> None:
    """Ensure plan estimates include rest between exercises."""
    ctx = DummyRootContext()
    ctx.live_rest_seconds = 20
    plan_items = [
        {"time_seconds": 30, "sets": 2},
        {"reps": 5, "sets": 1},
    ]
    total = RootWidget._estimate_plan_seconds(ctx, plan_items)
    assert total == 120

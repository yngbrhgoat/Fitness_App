from main import RootWidget


class DummyTempoContext:
    """Minimal context object for exercising live tempo hint logic."""

    def __init__(
        self,
        exercise,
        *,
        phase="set",
        set_target_seconds=None,
        set_elapsed=0.0,
    ) -> None:
        """Initialize the dummy tempo context.

        Args:
            exercise (dict[str, object]): Exercise data with reps or time.
            phase (str): Live phase label to simulate.
            set_target_seconds (float | None): Optional per-set target time.
            set_elapsed (float): Elapsed set time to simulate.

        Returns:
            None: Initializes the dummy state used by tests.
        """
        self._exercise = exercise
        self._live_phase = phase
        self._live_set_target_seconds = set_target_seconds
        self._live_set_elapsed = set_elapsed
        self.live_tempo_hint = ""

    def _current_live_exercise(self):
        return self._exercise

    def _t(self, text: str, **kwargs):
        return text.format(**kwargs)


def test_tempo_hint_for_repetition_exercises() -> None:
    """Verify tempo hints for repetition-based exercises.

    Args:
        None.

    Returns:
        None: Assertions validate hint formatting.
    """
    ctx = DummyTempoContext({"reps": 10}, set_target_seconds=40, set_elapsed=9)
    RootWidget._update_tempo_hint(ctx)
    assert ctx.live_tempo_hint == "You should be at repetition 3 now."


def test_tempo_hint_for_time_based_holds() -> None:
    """Verify tempo hints for time-based holds.

    Args:
        None.

    Returns:
        None: Assertions validate hint formatting.
    """
    ctx = DummyTempoContext({"time_seconds": 30}, set_elapsed=12.7)
    RootWidget._update_tempo_hint(ctx)
    assert ctx.live_tempo_hint == "Hold steady: 12s of 30s"


def test_tempo_hint_for_rest_phase() -> None:
    """Verify tempo hints during rest phases.

    Args:
        None.

    Returns:
        None: Assertions validate rest messaging.
    """
    ctx = DummyTempoContext({"reps": 8}, phase="rest")
    RootWidget._update_tempo_hint(ctx)
    assert ctx.live_tempo_hint == "Rest and breathe. Next set starts soon."


def test_tempo_hint_for_between_exercises_phase() -> None:
    """Verify tempo hints between exercises.

    Args:
        None.

    Returns:
        None: Assertions validate between-exercise messaging.
    """
    ctx = DummyTempoContext({"reps": 8}, phase="between_exercises")
    RootWidget._update_tempo_hint(ctx)
    assert ctx.live_tempo_hint.startswith("Rest up")
    assert "break" in ctx.live_tempo_hint


def test_completion_percentage_clamps_bounds() -> None:
    """Verify completion percentage clamps to 0-100 bounds.

    Args:
        None.

    Returns:
        None: Assertions validate clamping behavior.
    """
    assert RootWidget._compute_completion_percentage(object(), 12, 10) == 100.0
    assert RootWidget._compute_completion_percentage(object(), -1, 5) == 0.0


def test_completion_percentage_calculates_ratio() -> None:
    """Verify completion percentage calculations for normal ratios.

    Args:
        None.

    Returns:
        None: Assertions validate percentage calculation.
    """
    assert RootWidget._compute_completion_percentage(object(), 3, 4) == 75.0

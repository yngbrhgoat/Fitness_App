from types import SimpleNamespace

import pytest

from main import RootWidget


def test_score_recommendation_combines_rating_and_novelty_bonus() -> None:
    """Verify score combines rating with novelty bonus when recency is None.

    Args:
        None.

    Returns:
        None: Assertions validate score composition.
    """
    score = RootWidget._score_recommendation(object(), {"rating": 6.5}, None)
    assert score == 8.5


@pytest.mark.parametrize(
    ("recency_days", "expected_bonus"),
    [
        (15, 1.0),
        (10, 0.5),
        (3, -1.0),
        (5, 0.0),
    ],
)
def test_score_recommendation_recency_bonus(recency_days: int, expected_bonus: float) -> None:
    """Verify recency bonus values across tested day ranges.

    Args:
        recency_days (int): Days since last exercise.
        expected_bonus (float): Expected recency bonus for that range.

    Returns:
        None: Assertions validate computed bonus.
    """
    score = RootWidget._score_recommendation(object(), {"rating": 6.0}, recency_days)
    assert score == round(6.0 + expected_bonus, 2)


def test_estimate_exercise_seconds_time_based() -> None:
    """Verify estimate uses time-based recommendations with rest.

    Args:
        None.

    Returns:
        None: Assertions validate time-based estimate.
    """
    dummy = SimpleNamespace(live_rest_seconds=30)
    record = {"time_seconds": 45, "sets": 3}
    assert RootWidget._estimate_exercise_seconds(dummy, record) == 195


def test_estimate_exercise_seconds_volume_based() -> None:
    """Verify estimate uses rep-based recommendations with rest.

    Args:
        None.

    Returns:
        None: Assertions validate rep-based estimate.
    """
    dummy = SimpleNamespace(live_rest_seconds=30)
    record = {"reps": 8, "sets": 4}
    assert RootWidget._estimate_exercise_seconds(dummy, record) == 218


def test_estimate_exercise_seconds_fallback_when_missing_data() -> None:
    """Verify estimate falls back to default when volume data is missing.

    Args:
        None.

    Returns:
        None: Assertions validate fallback estimate.
    """
    dummy = SimpleNamespace(live_rest_seconds=30)
    assert RootWidget._estimate_exercise_seconds(dummy, {}) == 300

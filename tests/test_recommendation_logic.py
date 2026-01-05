from types import SimpleNamespace

import pytest

from main import RootWidget


def test_score_recommendation_combines_rating_and_novelty_bonus() -> None:
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
    score = RootWidget._score_recommendation(object(), {"rating": 6.0}, recency_days)
    assert score == round(6.0 + expected_bonus, 2)


def test_estimate_exercise_seconds_time_based() -> None:
    dummy = SimpleNamespace(live_rest_seconds=30)
    record = {"time_seconds": 45, "sets": 3}
    assert RootWidget._estimate_exercise_seconds(dummy, record) == 195


def test_estimate_exercise_seconds_volume_based() -> None:
    dummy = SimpleNamespace(live_rest_seconds=30)
    record = {"reps": 8, "sets": 4}
    assert RootWidget._estimate_exercise_seconds(dummy, record) == 218


def test_estimate_exercise_seconds_fallback_when_missing_data() -> None:
    dummy = SimpleNamespace(live_rest_seconds=30)
    assert RootWidget._estimate_exercise_seconds(dummy, {}) == 300

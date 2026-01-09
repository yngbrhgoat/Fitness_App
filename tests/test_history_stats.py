import exercise_database


def _seed_history(db_path):
    """Seed workout history records for history/stat tests.

    Args:
        db_path (Path): Temporary database path fixture.

    Returns:
        int: User id associated with the seeded history.
    """
    user_id = exercise_database.add_user("history-user", db_path=db_path)
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-01-05",
        duration_minutes=20,
        exercises=["Push-Up", "Squat"],
        goal="Strength",
        db_path=db_path,
    )
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-02-10",
        duration_minutes=30,
        exercises=["Push-Up"],
        goal="Strength",
        db_path=db_path,
    )
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-03-15",
        duration_minutes=25,
        exercises=["Deadlift"],
        goal="Strength",
        db_path=db_path,
    )
    return user_id


def test_fetch_workout_history_filters_by_start_date(db_path) -> None:
    """Ensure history filters out workouts before the start date.

    Args:
        db_path (Path): Temporary database path fixture.

    Returns:
        None: Assertions validate filtering behavior.
    """
    user_id = _seed_history(db_path)
    history = exercise_database.fetch_workout_history(
        user_id,
        start_date="2024-02-01",
        db_path=db_path,
    )
    dates = {entry["performed_at"] for entry in history}
    assert dates == {"2024-02-10", "2024-03-15"}
    assert "2024-01-05" not in dates


def test_fetch_workout_history_filters_by_end_date(db_path) -> None:
    """Ensure history filters out workouts after the end date.

    Args:
        db_path (Path): Temporary database path fixture.

    Returns:
        None: Assertions validate filtering behavior.
    """
    user_id = _seed_history(db_path)
    history = exercise_database.fetch_workout_history(
        user_id,
        end_date="2024-02-28",
        db_path=db_path,
    )
    dates = {entry["performed_at"] for entry in history}
    assert dates == {"2024-01-05", "2024-02-10"}
    assert "2024-03-15" not in dates


def test_fetch_workout_stats_totals_and_top_exercise(db_path) -> None:
    """Ensure stats totals and top exercise are computed correctly.

    Args:
        db_path (Path): Temporary database path fixture.

    Returns:
        None: Assertions validate aggregation behavior.
    """
    user_id = exercise_database.add_user("stats-user", db_path=db_path)
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-01-05",
        duration_minutes=20,
        exercises=["Push-Up", "Squat"],
        goal="Strength",
        db_path=db_path,
    )
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-01-10",
        duration_minutes=15,
        exercises=["Push-Up"],
        goal="Strength",
        db_path=db_path,
    )
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-01-20",
        duration_minutes=25,
        exercises=["Lunge"],
        goal="Strength",
        db_path=db_path,
    )
    stats = exercise_database.fetch_workout_stats(user_id, db_path=db_path)
    assert stats["total_workouts"] == 3
    assert stats["total_minutes"] == 60
    assert stats["top_exercise"] == "Push-Up"
    assert stats["top_exercise_count"] == 2

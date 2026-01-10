from datetime import date, timedelta

import pytest

import exercise_database


def test_add_user_and_fetch_users_sorted(db_path) -> None:
    """Ensure users are added and returned sorted by username."""
    exercise_database.add_user("beta", db_path=db_path)
    exercise_database.add_user("alpha", db_path=db_path)
    with exercise_database.get_connection(db_path) as conn:
        rows = exercise_database.fetch_users(conn)
    assert [row[1] for row in rows] == ["alpha", "beta"]
    assert rows[0][2] == "alpha"


def test_update_user_profile_updates_fields(db_path) -> None:
    """Ensure profile updates persist new display name and goal."""
    user_id = exercise_database.add_user("profile-user", db_path=db_path)
    exercise_database.update_user_profile(
        user_id=user_id,
        display_name="Profile User",
        preferred_goal="muscle_building",
        db_path=db_path,
    )
    with exercise_database.get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT display_name, preferred_goal FROM users WHERE id = ?;",
            (user_id,),
        ).fetchone()
    assert row == ("Profile User", "muscle_building")


def test_delete_user_cascades_workouts(db_path) -> None:
    """Ensure deleting a user removes their workouts and returns status."""
    user_id = exercise_database.add_user("delete-user", db_path=db_path)
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-01-01",
        duration_minutes=10,
        exercises=["Push-Up"],
        db_path=db_path,
    )
    assert exercise_database.delete_user(user_id=user_id, db_path=db_path) is True
    assert exercise_database.delete_user(user_id=user_id, db_path=db_path) is False
    with exercise_database.get_connection(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM workouts WHERE user_id = ?;",
            (user_id,),
        ).fetchone()[0]
    assert count == 0


def test_add_exercise_infers_supports_weight_and_defaults_unit(db_path) -> None:
    """Ensure exercise insertion infers weight support and default unit."""
    exercise_id = exercise_database.add_exercise(
        name="Weighted Squat",
        short_description="Basic weighted squat.",
        execution_instructions="Do the movement with control.",
        required_equipment="Barbell, plates",
        target_muscle_group="Legs",
        goal="strength_increase",
        suitability_rating=7,
        recommended_sets=3,
        recommended_reps_per_set=5,
        default_weight_value=60,
        default_weight_unit=None,
        db_path=db_path,
    )
    with exercise_database.get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT required_equipment, supports_weight, default_weight_value, default_weight_unit
            FROM exercises
            WHERE id = ?;
            """,
            (exercise_id,),
        ).fetchone()
    assert row == ("Barbell", 1, 60.0, "kg")


def test_add_exercise_clears_weight_defaults_when_not_supported(db_path) -> None:
    """Ensure default weight values are cleared when weight support is false."""
    exercise_id = exercise_database.add_exercise(
        name="Air Squat",
        short_description="Bodyweight squat.",
        execution_instructions="Move slowly.",
        required_equipment="Bodyweight",
        target_muscle_group="Legs",
        goal="weight_loss",
        suitability_rating=6,
        supports_weight=False,
        default_weight_value=20,
        default_weight_unit="kg",
        db_path=db_path,
    )
    with exercise_database.get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT supports_weight, default_weight_value, default_weight_unit
            FROM exercises
            WHERE id = ?;
            """,
            (exercise_id,),
        ).fetchone()
    assert row == (0, None, None)


def test_add_exercise_creates_goal_recommendations(db_path) -> None:
    """Ensure per-goal recommendations are created for new exercises."""
    exercise_id = exercise_database.add_exercise(
        name="Row",
        short_description="Basic row.",
        execution_instructions="Pull with control.",
        required_equipment="Dumbbell",
        target_muscle_group="Back",
        goal="muscle_building",
        suitability_rating=6,
        goal_ratings={"weight_loss": 4},
        recommended_sets=4,
        recommended_reps_per_set=10,
        db_path=db_path,
    )
    with exercise_database.get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT goal, suitability_rating, recommended_sets, recommended_reps_per_set
            FROM goal_recommendations
            WHERE exercise_id = ?
            ORDER BY goal;
            """,
            (exercise_id,),
        ).fetchall()
    assert len(rows) == len(exercise_database.GOALS)
    goal_map = {row[0]: row[1:] for row in rows}
    assert goal_map["muscle_building"] == (6, 4, 10)
    assert goal_map["weight_loss"][0] == 4
    assert goal_map["weight_loss"][1:] == (None, None)


def test_parse_performed_date_accepts_date_and_datetime() -> None:
    """Ensure date parsing accepts ISO date and datetime values."""
    parsed_date = exercise_database._parse_performed_date("2024-01-05")
    parsed_datetime = exercise_database._parse_performed_date("2024-01-05T12:30:00")
    assert parsed_date.isoformat() == "2024-01-05"
    assert parsed_datetime.isoformat() == "2024-01-05"


def test_parse_performed_date_rejects_missing_or_invalid() -> None:
    """Ensure date parsing rejects missing or malformed inputs."""
    with pytest.raises(ValueError, match="Date is required"):
        exercise_database._parse_performed_date("")
    with pytest.raises(ValueError, match="Use YYYY-MM-DD format"):
        exercise_database._parse_performed_date("01-05-2024")


def test_log_workout_rejects_invalid_duration_and_exercises(db_path) -> None:
    """Ensure workout logging validates duration and exercise list."""
    user_id = exercise_database.add_user("validation-user", db_path=db_path)
    with pytest.raises(ValueError, match="Duration must be positive"):
        exercise_database.log_workout(
            user_id=user_id,
            performed_at="2024-01-01",
            duration_minutes=0,
            exercises=["Push-Up"],
            db_path=db_path,
        )
    with pytest.raises(ValueError, match="At least one exercise is required"):
        exercise_database.log_workout(
            user_id=user_id,
            performed_at="2024-01-01",
            duration_minutes=10,
            exercises=[" ", ""],
            db_path=db_path,
        )


def test_log_workout_rejects_future_date(db_path) -> None:
    """Ensure workout logging rejects future dates."""
    user_id = exercise_database.add_user("future-user", db_path=db_path)
    future_date = (date.today() + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="Workout date cannot be in the future"):
        exercise_database.log_workout(
            user_id=user_id,
            performed_at=future_date,
            duration_minutes=10,
            exercises=["Push-Up"],
            db_path=db_path,
        )


def test_log_workout_rejects_negative_sets(db_path) -> None:
    """Ensure workout logging rejects negative total sets."""
    user_id = exercise_database.add_user("sets-user", db_path=db_path)
    with pytest.raises(ValueError, match="Total sets completed cannot be negative"):
        exercise_database.log_workout(
            user_id=user_id,
            performed_at="2024-01-01",
            duration_minutes=10,
            exercises=["Push-Up"],
            total_sets_completed=-1,
            db_path=db_path,
        )


def test_log_workout_rejects_invalid_statuses(db_path) -> None:
    """Ensure workout logging validates exercise statuses."""
    user_id = exercise_database.add_user("status-user", db_path=db_path)
    with pytest.raises(ValueError, match="Exercise status must be"):
        exercise_database.log_workout(
            user_id=user_id,
            performed_at="2024-01-01",
            duration_minutes=10,
            exercises=["Push-Up"],
            exercise_statuses=[("Push-Up", "done")],
            db_path=db_path,
        )


@pytest.mark.parametrize(
    ("value", "unit", "match"),
    [
        ("bad", "kg", "must be numeric"),
        (-5, "kg", "must be positive"),
        (10, "lb", "units must be kg"),
    ],
)
def test_log_workout_rejects_invalid_weights(db_path, value, unit, match) -> None:
    """Ensure workout logging validates exercise weight values and units."""
    user_id = exercise_database.add_user("weight-user", db_path=db_path)
    with pytest.raises(ValueError, match=match):
        exercise_database.log_workout(
            user_id=user_id,
            performed_at="2024-01-01",
            duration_minutes=10,
            exercises=["Push-Up"],
            exercise_weights=[("Push-Up", value, unit)],
            db_path=db_path,
        )


def test_log_workout_assigns_weights_by_name(db_path) -> None:
    """Ensure workout logging maps weights by name when lengths differ."""
    user_id = exercise_database.add_user("weight-map-user", db_path=db_path)
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-01-01",
        duration_minutes=10,
        exercises=["Push-Up", "Squat"],
        exercise_statuses=[("Push-Up", "completed"), ("Squat", "completed")],
        exercise_weights=[("Squat", 40, "kg")],
        db_path=db_path,
    )
    with exercise_database.get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT exercise_name, weight_value, weight_unit
            FROM workout_exercises
            ORDER BY exercise_name;
            """
        ).fetchall()
    weight_map = {row[0]: row[1:] for row in rows}
    assert weight_map["Push-Up"] == (None, None)
    assert weight_map["Squat"] == (40.0, "kg")


def test_log_workout_updates_exercise_defaults_from_weights(db_path) -> None:
    """Ensure logged weights update exercise defaults when missing."""
    exercise_database.add_exercise(
        name="Weighted Plank",
        short_description="Weighted plank.",
        execution_instructions="Hold steady.",
        required_equipment="Bodyweight",
        target_muscle_group="Core",
        goal="endurance_increase",
        suitability_rating=5,
        supports_weight=False,
        db_path=db_path,
    )
    user_id = exercise_database.add_user("weight-default-user", db_path=db_path)
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-01-05",
        duration_minutes=10,
        exercises=["Weighted Plank"],
        exercise_weights=[("Weighted Plank", 12.5, "kg")],
        db_path=db_path,
    )
    with exercise_database.get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT supports_weight, default_weight_value, default_weight_unit
            FROM exercises
            WHERE lower(name) = lower(?);
            """,
            ("Weighted Plank",),
        ).fetchone()
    assert row == (1, 12.5, "kg")


def test_fetch_workout_history_includes_attempts_and_weights(db_path) -> None:
    """Ensure workout history aggregates attempts with statuses and weights."""
    user_id = exercise_database.add_user("history-detail-user", db_path=db_path)
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-01-10",
        duration_minutes=15,
        exercises=["Push-Up", "Squat"],
        exercise_statuses=[("Push-Up", "completed"), ("Squat", "skipped")],
        exercise_weights=[("Push-Up", 20, "kg")],
        db_path=db_path,
    )
    history = exercise_database.fetch_workout_history(user_id, db_path=db_path)
    assert len(history) == 1
    attempts = {att["name"]: att for att in history[0]["exercise_attempts"]}
    assert attempts["Push-Up"]["status"] == "completed"
    assert attempts["Push-Up"]["weight_value"] == 20.0
    assert attempts["Push-Up"]["weight_unit"] == "kg"
    assert attempts["Squat"]["status"] == "skipped"


def test_fetch_workout_stats_counts_weights_and_filters(db_path) -> None:
    """Ensure workout stats include weight totals and date filters."""
    with exercise_database.get_connection(db_path) as conn:
        user_id = conn.execute(
            "INSERT INTO users (username, display_name) VALUES (?, ?);",
            ("stats-weight-user", "stats-weight-user"),
        ).lastrowid
        workout_one = conn.execute(
            """
            INSERT INTO workouts (user_id, performed_at, duration_minutes, goal)
            VALUES (?, ?, ?, ?);
            """,
            (user_id, "2024-01-01", 20, "Strength"),
        ).lastrowid
        workout_two = conn.execute(
            """
            INSERT INTO workouts (user_id, performed_at, duration_minutes, goal)
            VALUES (?, ?, ?, ?);
            """,
            (user_id, "2024-02-01", 30, "Strength"),
        ).lastrowid
        conn.executemany(
            """
            INSERT INTO workout_exercises (workout_id, exercise_name, status, weight_value, weight_unit)
            VALUES (?, ?, ?, ?, ?);
            """,
            [
                (workout_one, "Press", "completed", 20, "kg"),
                (workout_one, "Press", "skipped", 10, "kg"),
                (workout_two, "Row", "completed", 30, "lb"),
            ],
        )
        conn.commit()
    stats_all = exercise_database.fetch_workout_stats(user_id, db_path=db_path)
    assert stats_all["total_workouts"] == 2
    assert stats_all["total_minutes"] == 50
    assert stats_all["total_weight_kg"] == 20
    assert stats_all["total_weight_lb"] == 30
    assert stats_all["top_exercise"] == "Press"
    stats_filtered = exercise_database.fetch_workout_stats(
        user_id,
        start_date="2024-02-01",
        db_path=db_path,
    )
    assert stats_filtered["total_workouts"] == 1
    assert stats_filtered["total_weight_lb"] == 30
    assert stats_filtered["total_weight_kg"] == 0


def test_fetch_recent_exercise_usage_applies_limit_and_filters(db_path) -> None:
    """Ensure recent exercise usage respects limit and date filters."""
    user_id = exercise_database.add_user("recent-limit-user", db_path=db_path)
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-01-01",
        duration_minutes=10,
        exercises=["Push-Up"],
        db_path=db_path,
    )
    exercise_database.log_workout(
        user_id=user_id,
        performed_at="2024-01-02",
        duration_minutes=10,
        exercises=["Squat"],
        db_path=db_path,
    )
    rows = exercise_database.fetch_recent_exercise_usage(
        user_id,
        limit=1,
        db_path=db_path,
    )
    assert rows == [("Squat", "2024-01-02")]
    filtered = exercise_database.fetch_recent_exercise_usage(
        user_id,
        start_date="2024-01-02",
        db_path=db_path,
    )
    assert filtered == [("Squat", "2024-01-02")]


def test_seed_example_user_creates_default_profile(db_path) -> None:
    """Ensure the example user and workouts are inserted once."""
    with exercise_database.get_connection(db_path) as conn:
        exercise_database.seed_example_user(conn)
        exercise_database.seed_example_user(conn)
        user = conn.execute(
            "SELECT id, display_name, preferred_goal FROM users WHERE username = ?;",
            (exercise_database.EXAMPLE_USERNAME,),
        ).fetchone()
        workouts = conn.execute(
            "SELECT COUNT(*) FROM workouts WHERE user_id = ?;",
            (user[0],),
        ).fetchone()[0]
    assert user[1] == exercise_database.EXAMPLE_DISPLAY_NAME
    assert user[2] == exercise_database.EXAMPLE_PREFERRED_GOAL
    assert workouts == 3


def test_initialize_database_creates_file_and_data(db_path) -> None:
    """Ensure database initialization creates file and seeded data."""
    path = exercise_database.initialize_database(db_path)
    assert path.exists()
    with exercise_database.get_connection(path) as conn:
        exercise_count = conn.execute("SELECT COUNT(*) FROM exercises;").fetchone()[0]
        user = conn.execute(
            "SELECT 1 FROM users WHERE username = ?;",
            (exercise_database.EXAMPLE_USERNAME,),
        ).fetchone()
    assert exercise_count > 0
    assert user is not None

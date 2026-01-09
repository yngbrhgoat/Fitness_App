from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple


DB_PATH = Path(__file__).with_name("exercises.db")

GOALS = (
    "muscle_building",
    "weight_loss",
    "strength_increase",
    "endurance_increase",
)
DEFAULT_GOAL_RATING = 5
EXAMPLE_USERNAME = "exaple-user"
EXAMPLE_DISPLAY_NAME = "Example User"
EXAMPLE_PREFERRED_GOAL = "muscle_building"

_TAG_DESCRIPTOR_WORDS = {
    "focus",
    "emphasis",
    "target",
    "targeting",
    "optional",
    "mainly",
    "primary",
    "secondary",
}
_EQUIPMENT_ALIASES = {
    "barbell": ["Barbell"],
    "plates": ["Barbell"],
    "dumbbell": ["Dumbbell"],
    "dumbbells": ["Dumbbell"],
    "bodyweight": ["Bodyweight"],
    "body weight": ["Bodyweight"],
    "machine": ["Machine"],
    "cable machine": ["Machine"],
    "cable": ["Machine"],
    "resistance bands": ["Bands"],
    "bands": ["Bands"],
    "band": ["Bands"],
    "kettlebell": ["Kettlebell"],
    "medicine ball": ["Medicine Ball"],
    "jump rope": ["Jump Rope"],
    "pull up bar": ["Bodyweight", "Pull-up Bar"],
    "pull-up bar": ["Bodyweight", "Pull-up Bar"],
    "mat": ["Bodyweight", "Mat"],
}
_MUSCLE_ALIASES = {
    "chest": ["Chest"],
    "back": ["Back"],
    "legs": ["Legs"],
    "shoulders": ["Shoulders"],
    "core": ["Core"],
    "biceps": ["Biceps"],
    "triceps": ["Triceps"],
    "posterior chain": ["Back", "Legs", "Posterior Chain"],
    "glutes": ["Glutes", "Legs", "Posterior Chain"],
    "calves": ["Calves", "Legs"],
    "full body": ["Full Body"],
}
_WEIGHT_EQUIPMENT = {
    "Barbell",
    "Dumbbell",
    "Machine",
    "Kettlebell",
    "Bands",
    "Medicine Ball",
}


def _normalize_tag_key(value: str) -> str:
    """Normalize a tag string into a lookup key."""
    # Strip punctuation and collapse whitespace.
    cleaned = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return " ".join(cleaned.split())


def _strip_descriptor_words(token: str) -> str:
    """Remove trailing descriptor words from a tag token."""
    # Drop words like "focus" or "target" to improve matching.
    parts = token.split()
    while parts and parts[-1].lower() in _TAG_DESCRIPTOR_WORDS:
        parts.pop()
    return " ".join(parts)


def _split_tag_string(value: str) -> list[str]:
    """Split a tag string into cleaned tokens."""
    # Normalize separators and trim descriptors for each token.
    text = re.sub(r"\([^)]*\)", "", value or "")
    text = text.replace("&", " and ").replace("/", ",")
    parts = re.split(r",|;|\band\b|\bwith\b|\+|\|", text, flags=re.IGNORECASE)
    tokens: list[str] = []
    for part in parts:
        cleaned = _strip_descriptor_words(part.strip())
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _flatten_tag_input(value: Iterable[str] | str | None) -> list[str]:
    """Flatten tag input from strings or iterables into tokens."""
    # Accept strings or iterables and normalize them uniformly.
    if value is None:
        return []
    if isinstance(value, str):
        return _split_tag_string(value)
    tokens: list[str] = []
    for item in value:
        if item is None:
            continue
        tokens.extend(_split_tag_string(str(item)))
    return tokens


def _normalize_weight_unit(value: Optional[str]) -> Optional[str]:
    """Normalize weight unit strings to kg."""
    if not value:
        return None
    cleaned = value.strip().lower()
    if cleaned in {"kg", "kgs", "kilogram", "kilograms"}:
        return "kg"
    return None


def normalize_weight_unit(value: Optional[str]) -> Optional[str]:
    """Normalize a weight unit to the canonical ``kg`` label.

    Args:
        value (str | None): Raw weight unit string to normalize.

    Returns:
        str | None: ``"kg"`` when recognized, otherwise ``None``.
    """
    return _normalize_weight_unit(value)


def infer_supports_weight(required_equipment: Iterable[str] | str | None) -> bool:
    """Determine whether equipment implies external load support.

    Args:
        required_equipment (Iterable[str] | str | None): Equipment tags to
            inspect.

    Returns:
        bool: ``True`` when equipment suggests external weights are used.
    """
    equipment_items = normalize_equipment_list(required_equipment or "")
    return bool(set(equipment_items) & _WEIGHT_EQUIPMENT)


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    """Return items with duplicates removed while preserving order."""
    # Use a set to keep the first occurrence of each item.
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def format_tag_list(items: Sequence[str]) -> str:
    """Join non-empty tags into a comma-separated string.

    Args:
        items (Sequence[str]): Tags to format.

    Returns:
        str: Comma-separated list with empty items removed.
    """
    # Filter out falsy items for clean display.
    return ", ".join([item for item in items if item])


def normalize_equipment_list(value: Iterable[str] | str) -> list[str]:
    """Normalize equipment labels into canonical display values.

    Args:
        value (Iterable[str] | str): Raw equipment labels or tags.

    Returns:
        list[str]: Canonicalized, de-duplicated equipment labels.
    """
    # Map known aliases and title-case unknown entries.
    items: list[str] = []
    for token in _flatten_tag_input(value):
        key = _normalize_tag_key(token)
        if not key:
            continue
        mapped = _EQUIPMENT_ALIASES.get(key)
        if mapped:
            items.extend(mapped)
        else:
            items.append(token.strip().title())
    return _dedupe_preserve_order(items)


def normalize_muscle_group_list(value: Iterable[str] | str) -> list[str]:
    """Normalize muscle group labels into canonical display values.

    Args:
        value (Iterable[str] | str): Raw muscle group labels or tags.

    Returns:
        list[str]: Canonicalized, de-duplicated muscle group labels.
    """
    # Map known aliases and title-case unknown entries.
    items: list[str] = []
    for token in _flatten_tag_input(value):
        key = _normalize_tag_key(token)
        if not key:
            continue
        mapped = _MUSCLE_ALIASES.get(key)
        if mapped:
            items.extend(mapped)
        else:
            items.append(token.strip().title())
    return _dedupe_preserve_order(items)


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Create a SQLite connection with foreign keys enabled.

    Args:
        db_path (Path): Location of the SQLite database file.

    Returns:
        sqlite3.Connection: Connection configured with foreign key support.
    """
    # Enable foreign keys on each new connection.
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Create tables to store exercises and per-goal recommendations.

    Args:
        conn (sqlite3.Connection): Open connection to the database.

    Returns:
        None: Schema changes are applied in place.
    """
    # Create tables if they do not already exist.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT,
            preferred_goal TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            performed_at TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),
            duration_seconds INTEGER,
            goal TEXT,
            total_sets_completed INTEGER DEFAULT 0 CHECK (total_sets_completed >= 0),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS workout_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workout_id INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'completed' CHECK (status IN ('completed','skipped')),
            weight_value REAL,
            weight_unit TEXT,
            FOREIGN KEY (workout_id) REFERENCES workouts (id) ON DELETE CASCADE
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            icon TEXT,
            short_description TEXT NOT NULL,
            execution_instructions TEXT,
            required_equipment TEXT NOT NULL,
            target_muscle_group TEXT NOT NULL,
            supports_weight INTEGER NOT NULL DEFAULT 0,
            default_weight_value REAL,
            default_weight_unit TEXT
        );
        """
    )
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS goal_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id INTEGER NOT NULL,
            goal TEXT NOT NULL CHECK (goal IN {GOALS}),
            suitability_rating INTEGER NOT NULL CHECK (suitability_rating BETWEEN 1 AND 10),
            recommended_sets INTEGER,
            recommended_reps_per_set INTEGER,
            recommended_time_seconds INTEGER,
            UNIQUE (exercise_id, goal),
            FOREIGN KEY (exercise_id) REFERENCES exercises (id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()


def _add_column_if_missing(
    conn: sqlite3.Connection,
    table: str,
    column: str,
    definition: str,
) -> None:
    """Add a column only when it is absent to support simple migrations."""
    # Inspect table columns and append missing fields.
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table});")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition};")


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Apply lightweight schema upgrades for existing databases.

    Args:
        conn (sqlite3.Connection): Open connection to migrate in place.

    Returns:
        None: Updates the database schema and commits changes.
    """
    # Apply lightweight schema upgrades for existing databases.
    _add_column_if_missing(conn, "users", "display_name", "display_name TEXT")
    _add_column_if_missing(conn, "users", "preferred_goal", "preferred_goal TEXT")
    _add_column_if_missing(conn, "workouts", "duration_seconds", "duration_seconds INTEGER")
    _add_column_if_missing(conn, "workouts", "goal", "goal TEXT")
    _add_column_if_missing(conn, "workouts", "total_sets_completed", "total_sets_completed INTEGER DEFAULT 0")
    _add_column_if_missing(
        conn,
        "workout_exercises",
        "status",
        "status TEXT NOT NULL DEFAULT 'completed'",
    )
    _add_column_if_missing(conn, "workout_exercises", "weight_value", "weight_value REAL")
    _add_column_if_missing(conn, "workout_exercises", "weight_unit", "weight_unit TEXT")
    _add_column_if_missing(conn, "exercises", "execution_instructions", "execution_instructions TEXT")
    _add_column_if_missing(conn, "exercises", "supports_weight", "supports_weight INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "exercises", "default_weight_value", "default_weight_value REAL")
    _add_column_if_missing(conn, "exercises", "default_weight_unit", "default_weight_unit TEXT")
    _backfill_supports_weight(conn)
    _convert_weights_to_kg(conn)
    conn.commit()


def _backfill_supports_weight(conn: sqlite3.Connection) -> None:
    """Update supports_weight when equipment or logged weights indicate external load."""
    rows = conn.execute(
        "SELECT id, required_equipment, supports_weight, name FROM exercises;"
    ).fetchall()
    weighted_names = {
        row[0].strip().lower()
        for row in conn.execute(
            "SELECT DISTINCT exercise_name FROM workout_exercises WHERE weight_value IS NOT NULL;"
        ).fetchall()
        if row and row[0]
    }
    updates = []
    for exercise_id, required_equipment, supports_weight, name in rows:
        if supports_weight:
            continue
        name_key = (name or "").strip().lower()
        if name_key and name_key in weighted_names:
            updates.append((exercise_id,))
            continue
        if infer_supports_weight(required_equipment or ""):
            updates.append((exercise_id,))
    if updates:
        conn.executemany("UPDATE exercises SET supports_weight = 1 WHERE id = ?;", updates)


def _convert_weights_to_kg(conn: sqlite3.Connection) -> None:
    """Convert any stored lb weights into kg."""
    conn.execute(
        """
        UPDATE workout_exercises
        SET weight_value = weight_value * 0.453592,
            weight_unit = 'kg'
        WHERE lower(weight_unit) IN ('lb', 'lbs', 'pound', 'pounds');
        """
    )
    conn.execute(
        """
        UPDATE exercises
        SET default_weight_value = default_weight_value * 0.453592,
            default_weight_unit = 'kg'
        WHERE lower(default_weight_unit) IN ('lb', 'lbs', 'pound', 'pounds');
        """
    )


def seed_sample_data(conn: sqlite3.Connection) -> None:
    """Seed baseline exercises and per-goal recommendations.

    Existing entries are updated with newer descriptions and instructions, and
    defaults are filled when missing.

    Args:
        conn (sqlite3.Connection): Open connection for inserting seed data.

    Returns:
        None: Inserts or updates seed exercise rows.
    """
    # Preload a curated set of exercises for first-time users.
    existing_names = {row[0].strip().lower() for row in conn.execute("SELECT name FROM exercises;")}

    exercises = [
        {
            "name": "Push-Up",
            "icon": "push_up",
            "short_description": "Classic bodyweight press for chest, shoulders, and triceps.",
            "execution_instructions": (
                "Set up in a high plank with hands slightly wider than shoulders, wrists stacked, and a "
                "straight line from head to heels.\n"
                "Brace your core and glutes, lower your chest to just above the floor with elbows about "
                "45 degrees from your torso.\n"
                "Press back up while exhaling, keeping your neck neutral and hips level."
            ),
            "required_equipment": "Bodyweight (mat optional)",
            "target_muscle_group": "Chest",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 8,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 8,
                    "recommended_sets": 5,
                    "recommended_reps_per_set": 6,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Barbell Deadlift",
            "icon": "barbell_deadlift",
            "short_description": "Full-body hip hinge that builds the posterior chain and grip.",
            "execution_instructions": (
                "Stand with mid-foot under the bar and feet hip-width.\n"
                "Hinge at the hips, grip the bar just outside your legs, flatten your back, and brace.\n"
                "Push the floor away to stand tall, keep the bar close to your shins and thighs, then "
                "hinge back and lower with control."
            ),
            "required_equipment": "Barbell, plates",
            "target_muscle_group": "Posterior chain",
            "default_weight_value": 60,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 9,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 8,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 10,
                    "recommended_sets": 5,
                    "recommended_reps_per_set": 5,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 5,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Plank",
            "icon": "plank",
            "short_description": "Static core hold for trunk stability.",
            "execution_instructions": (
                "Place forearms under shoulders with elbows at 90 degrees and legs extended.\n"
                "Brace your abs and glutes so your head, shoulders, hips, and heels stay in one line.\n"
                "Breathe steadily and stop if your lower back starts to sag or arch."
            ),
            "required_equipment": "Mat (optional)",
            "target_muscle_group": "Core",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": None,
                    "recommended_time_seconds": 45,
                },
                "weight_loss": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": None,
                    "recommended_time_seconds": 60,
                },
                "strength_increase": {
                    "suitability_rating": 5,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": None,
                    "recommended_time_seconds": 30,
                },
                "endurance_increase": {
                    "suitability_rating": 9,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": None,
                    "recommended_time_seconds": 90,
                },
            },
        },
        {
            "name": "Jump Rope",
            "icon": "jump_rope",
            "short_description": "Cardio drill that boosts coordination and calf endurance.",
            "execution_instructions": (
                "Hold handles at hip height with elbows tucked and the rope behind your heels.\n"
                "Turn the rope with small wrist circles and jump low on the balls of your feet with "
                "soft knees.\n"
                "Land quietly, keep your torso tall, and maintain a steady rhythm."
            ),
            "required_equipment": "Jump rope",
            "target_muscle_group": "Full body with calves focus",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 5,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": None,
                    "recommended_time_seconds": 60,
                },
                "weight_loss": {
                    "suitability_rating": 9,
                    "recommended_sets": 5,
                    "recommended_reps_per_set": None,
                    "recommended_time_seconds": 90,
                },
                "strength_increase": {
                    "suitability_rating": 4,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": None,
                    "recommended_time_seconds": 60,
                },
                "endurance_increase": {
                    "suitability_rating": 10,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": None,
                    "recommended_time_seconds": 120,
                },
            },
        },
        {
            "name": "Bench Press",
            "icon": "bench_press",
            "short_description": "Barbell press for chest, shoulder, and triceps strength.",
            "execution_instructions": (
                "Lie on the bench with eyes under the bar, feet planted, and shoulder blades squeezed "
                "back.\n"
                "Unrack the bar, lower it to mid-chest with elbows about 45 to 70 degrees, and keep "
                "wrists stacked.\n"
                "Press straight up while exhaling, keeping your glutes on the bench."
            ),
            "required_equipment": "Barbell",
            "target_muscle_group": "Chest",
            "default_weight_value": 40,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 9,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 8,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 10,
                    "recommended_sets": 5,
                    "recommended_reps_per_set": 5,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 5,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Dumbbell Chest Fly",
            "icon": "dumbbell_chest_fly",
            "short_description": "Dumbbell fly to open the chest with control.",
            "execution_instructions": (
                "Lie on a bench with dumbbells above your chest, palms facing, and a slight bend in the "
                "elbows.\n"
                "Open your arms in a wide arc until you feel a chest stretch, keeping the elbow angle "
                "fixed.\n"
                "Squeeze your chest to bring the dumbbells back together over your chest without "
                "clanking."
            ),
            "required_equipment": "Dumbbells",
            "target_muscle_group": "Chest",
            "default_weight_value": 8,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 8,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 7,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 8,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 5,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Dumbbell Bicep Curl",
            "icon": "dumbbell_bicep_curl",
            "short_description": "Dumbbell curl to build biceps strength.",
            "execution_instructions": (
                "Stand tall with dumbbells at your sides and palms facing forward.\n"
                "Curl the weights up without swinging or moving your elbows, then pause and squeeze.\n"
                "Lower slowly to full elbow extension."
            ),
            "required_equipment": "Dumbbells",
            "target_muscle_group": "Biceps",
            "default_weight_value": 8,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 8,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 7,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 8,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 5,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Overhead Tricep Extension",
            "icon": "overhead_tricep_extension",
            "short_description": "Overhead extension that targets the triceps long head.",
            "execution_instructions": (
                "Hold a dumbbell overhead with both hands and keep your elbows close to your ears.\n"
                "Lower the weight behind your head by bending only the elbows while keeping your upper "
                "arms still.\n"
                "Extend the elbows to return overhead and avoid flaring the ribs."
            ),
            "required_equipment": "Dumbbells",
            "target_muscle_group": "Triceps",
            "default_weight_value": 10,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 7,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 8,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Tricep Dip",
            "icon": "tricep_dip",
            "short_description": "Bench dip focused on triceps and chest.",
            "execution_instructions": (
                "Place hands on a bench with fingers forward and legs extended, hips just off the edge.\n"
                "Lower your body by bending the elbows to about 90 degrees while keeping shoulders "
                "down.\n"
                "Press through your palms to straighten the arms and keep your torso close to the bench."
            ),
            "required_equipment": "Bodyweight",
            "target_muscle_group": "Triceps",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 8,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 7,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 6,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Dumbbell Shoulder Press",
            "icon": "dumbbell_shoulder_press",
            "short_description": "Overhead press for shoulder strength and stability.",
            "execution_instructions": (
                "Sit or stand tall with dumbbells at shoulder height and palms facing forward.\n"
                "Brace your core and press the weights overhead until your biceps are near your ears.\n"
                "Lower with control to shoulder height without arching your back."
            ),
            "required_equipment": "Dumbbells",
            "target_muscle_group": "Shoulders",
            "default_weight_value": 10,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 8,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 8,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 6,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Goblet Squat",
            "icon": "goblet_squat",
            "short_description": "Front-loaded squat that trains legs and core.",
            "execution_instructions": (
                "Hold a dumbbell or kettlebell at your chest with elbows down.\n"
                "Set your feet slightly wider than hips with toes turned out, then sit hips down and "
                "back while keeping your chest up.\n"
                "Drive through your heels to stand and keep the weight close to your body."
            ),
            "required_equipment": "Kettlebell",
            "target_muscle_group": "Legs",
            "default_weight_value": 16,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 8,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 8,
                    "recommended_sets": 5,
                    "recommended_reps_per_set": 6,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Walking Lunge",
            "icon": "walking_lunge",
            "short_description": "Alternating lunge for legs, glutes, and balance.",
            "execution_instructions": (
                "Stand tall and take a long step forward so both knees can bend to about 90 degrees.\n"
                "Lower straight down with the front knee over the ankle and the back knee hovering above "
                "the floor.\n"
                "Push through the front heel to stand and step into the next lunge."
            ),
            "required_equipment": "Bodyweight",
            "target_muscle_group": "Legs",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 8,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 16,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 6,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 8,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Pull-Up",
            "icon": "pull_up",
            "short_description": "Bodyweight vertical pull for back and biceps.",
            "execution_instructions": (
                "Grip the bar slightly wider than shoulders with palms away and start from a dead hang.\n"
                "Engage your lats and pull your chest toward the bar by driving elbows down and back.\n"
                "Lower under control to a full hang without swinging."
            ),
            "required_equipment": "Pull-up Bar",
            "target_muscle_group": "Back",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 9,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 6,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 8,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 9,
                    "recommended_sets": 5,
                    "recommended_reps_per_set": 5,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Lat Pulldown",
            "icon": "lat_pulldown",
            "short_description": "Machine pulldown for lats and upper back.",
            "execution_instructions": (
                "Sit tall with thighs secured and grip the bar wider than shoulders.\n"
                "Pull the bar to your upper chest by driving elbows down and squeezing the shoulder "
                "blades.\n"
                "Return slowly to a full stretch without leaning back or using momentum."
            ),
            "required_equipment": "Cable Machine",
            "target_muscle_group": "Back",
            "default_weight_value": 30,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 8,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 8,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 6,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Seated Cable Row",
            "icon": "seated_cable_row",
            "short_description": "Seated row for mid-back strength.",
            "execution_instructions": (
                "Sit tall with knees slightly bent and arms extended to the handle.\n"
                "Row to the lower ribs with elbows close and shoulders down.\n"
                "Pause, then return with control while keeping your torso upright."
            ),
            "required_equipment": "Cable Machine",
            "target_muscle_group": "Back",
            "default_weight_value": 30,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 8,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 8,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 6,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Kettlebell Swing",
            "icon": "kettlebell_swing",
            "short_description": "Explosive hip hinge for full-body power and conditioning.",
            "execution_instructions": (
                "Stand hip-width with the kettlebell in front, hinge at the hips, and hike it back "
                "between your legs.\n"
                "Drive the hips forward explosively so the bell floats to chest height while arms stay "
                "relaxed.\n"
                "Let it fall, hinge again, and keep your back neutral throughout."
            ),
            "required_equipment": "Kettlebell",
            "target_muscle_group": "Full Body",
            "default_weight_value": 16,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 7,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 9,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 7,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 9,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 25,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Russian Twist",
            "icon": "russian_twist",
            "short_description": "Rotational core move for obliques.",
            "execution_instructions": (
                "Sit with knees bent, lean back with a flat back, and brace your core.\n"
                "Rotate your torso side to side, moving the ribs and shoulders together rather than just "
                "the arms.\n"
                "Keep feet grounded or slightly lifted and maintain a steady pace."
            ),
            "required_equipment": "Medicine Ball",
            "target_muscle_group": "Core",
            "default_weight_value": 6,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 8,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 30,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 5,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 8,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 40,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Glute Bridge",
            "icon": "glute_bridge",
            "short_description": "Hip bridge to activate glutes and hamstrings.",
            "execution_instructions": (
                "Lie on your back with knees bent and feet hip-width, heels close to your glutes.\n"
                "Brace your core and drive through the heels to lift your hips until shoulders, hips, "
                "and knees align.\n"
                "Squeeze the glutes, pause, then lower slowly."
            ),
            "required_equipment": "Bodyweight",
            "target_muscle_group": "Glutes",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 7,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 7,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 8,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Calf Raise",
            "icon": "calf_raise",
            "short_description": "Standing calf raise for lower-leg strength.",
            "execution_instructions": (
                "Stand tall with feet hip-width and hold a support if needed.\n"
                "Rise onto the balls of your feet and pause at the top.\n"
                "Lower slowly below neutral for a full stretch."
            ),
            "required_equipment": "Bodyweight",
            "target_muscle_group": "Calves",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 7,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 25,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Band Pull-Apart",
            "icon": "band_pull_apart",
            "short_description": "Band pull-apart for rear shoulders and upper back.",
            "execution_instructions": (
                "Hold the band at shoulder height with arms straight and hands shoulder-width.\n"
                "Pull the band apart by moving the arms out and squeezing the shoulder blades.\n"
                "Return with control and keep the ribs down."
            ),
            "required_equipment": "Resistance Bands",
            "target_muscle_group": "Shoulders",
            "default_weight_value": 6,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 5,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 25,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Leg Press",
            "icon": "leg_press",
            "short_description": "Machine leg press for quads and glutes.",
            "execution_instructions": (
                "Sit with your back and head against the pad and feet shoulder-width on the platform.\n"
                "Unrack, lower the platform until knees are about 90 degrees while keeping heels down.\n"
                "Press through mid-foot and heels to extend without locking the knees."
            ),
            "required_equipment": "Machine",
            "target_muscle_group": "Legs",
            "default_weight_value": 80,
            "default_weight_unit": "kg",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 8,
                    "recommended_sets": 4,
                    "recommended_reps_per_set": 10,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 12,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 9,
                    "recommended_sets": 5,
                    "recommended_reps_per_set": 6,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
            },
        },
        {
            "name": "Bicycle Crunch",
            "icon": "bicycle_crunch",
            "short_description": "Alternating crunch for core endurance.",
            "execution_instructions": (
                "Lie on your back with hands lightly behind your head and lower back pressed into the "
                "floor.\n"
                "Extend one leg while rotating the opposite elbow toward the knee.\n"
                "Alternate smoothly and avoid pulling on your neck."
            ),
            "required_equipment": "Bodyweight",
            "target_muscle_group": "Core",
            "recommendations": {
                "muscle_building": {
                    "suitability_rating": 6,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 20,
                    "recommended_time_seconds": None,
                },
                "weight_loss": {
                    "suitability_rating": 8,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 30,
                    "recommended_time_seconds": None,
                },
                "strength_increase": {
                    "suitability_rating": 5,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 15,
                    "recommended_time_seconds": None,
                },
                "endurance_increase": {
                    "suitability_rating": 7,
                    "recommended_sets": 3,
                    "recommended_reps_per_set": 40,
                    "recommended_time_seconds": None,
                },
            },
        },
    ]

    exercise_stmt = """
        INSERT INTO exercises (
            name,
            icon,
            short_description,
            execution_instructions,
            required_equipment,
            target_muscle_group,
            supports_weight,
            default_weight_value,
            default_weight_unit
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
    """
    recommendation_stmt = """
        INSERT INTO goal_recommendations (
            exercise_id,
            goal,
            suitability_rating,
            recommended_sets,
            recommended_reps_per_set,
            recommended_time_seconds
        )
        VALUES (?, ?, ?, ?, ?, ?);
    """

    for exercise in exercises:
        name_key = exercise["name"].strip().lower()
        instructions = exercise.get("execution_instructions", "")
        equipment_value = format_tag_list(normalize_equipment_list(exercise["required_equipment"]))
        muscle_value = format_tag_list(normalize_muscle_group_list(exercise["target_muscle_group"]))
        supports_weight = exercise.get("supports_weight")
        if supports_weight is None:
            supports_weight = infer_supports_weight(equipment_value or exercise["required_equipment"])
        default_weight_value = exercise.get("default_weight_value")
        default_weight_unit = _normalize_weight_unit(exercise.get("default_weight_unit"))
        if supports_weight and default_weight_value is not None and not default_weight_unit:
            default_weight_unit = "kg"
        if not supports_weight:
            default_weight_value = None
            default_weight_unit = None
        if name_key in existing_names:
            conn.execute(
                """
                UPDATE exercises
                SET short_description = ?,
                    execution_instructions = ?
                WHERE lower(name) = ?;
                """,
                (exercise["short_description"], instructions, name_key),
            )
            if default_weight_value is not None:
                conn.execute(
                    """
                    UPDATE exercises
                    SET supports_weight = 1,
                        default_weight_value = COALESCE(default_weight_value, ?),
                        default_weight_unit = COALESCE(default_weight_unit, ?)
                    WHERE lower(name) = ?;
                    """,
                    (default_weight_value, default_weight_unit, name_key),
                )
            continue
        cursor = conn.execute(
            exercise_stmt,
            (
                exercise["name"],
                exercise["icon"],
                exercise["short_description"],
                instructions,
                equipment_value or exercise["required_equipment"],
                muscle_value or exercise["target_muscle_group"],
                1 if supports_weight else 0,
                default_weight_value,
                default_weight_unit,
            ),
        )
        exercise_id = cursor.lastrowid

        for goal, recommendation in exercise["recommendations"].items():
            conn.execute(
                recommendation_stmt,
                (
                    exercise_id,
                    goal,
                    recommendation["suitability_rating"],
                    recommendation.get("recommended_sets"),
                    recommendation.get("recommended_reps_per_set"),
                    recommendation.get("recommended_time_seconds"),
                ),
            )
        existing_names.add(name_key)

    conn.commit()


def seed_example_user(conn: sqlite3.Connection) -> None:
    """Ensure a sample user exists with example workouts for previews.

    Args:
        conn (sqlite3.Connection): Open connection for seeding sample data.

    Returns:
        None: Inserts or updates the sample user and workouts.
    """
    # Create or update a sample profile with starter workouts.
    row = conn.execute(
        "SELECT id, display_name, preferred_goal FROM users WHERE username = ?;",
        (EXAMPLE_USERNAME,),
    ).fetchone()
    if row:
        user_id, display_name, preferred_goal = row
        if display_name is None or preferred_goal is None:
            conn.execute(
                """
                UPDATE users
                SET display_name = COALESCE(display_name, ?),
                    preferred_goal = COALESCE(preferred_goal, ?)
                WHERE id = ?;
                """,
                (EXAMPLE_DISPLAY_NAME, EXAMPLE_PREFERRED_GOAL, user_id),
            )
            conn.commit()
    else:
        cursor = conn.execute(
            "INSERT INTO users (username, display_name, preferred_goal) VALUES (?, ?, ?);",
            (EXAMPLE_USERNAME, EXAMPLE_DISPLAY_NAME, EXAMPLE_PREFERRED_GOAL),
        )
        user_id = cursor.lastrowid
        conn.commit()

    has_workouts = conn.execute(
        "SELECT 1 FROM workouts WHERE user_id = ? LIMIT 1;",
        (user_id,),
    ).fetchone()
    if has_workouts:
        return

    def goal_label(goal: str) -> str:
        """Convert a goal code into a title-cased label."""
        # Keep sample workout labels aligned with UI formatting.
        return goal.replace("_", " ").title()

    sample_workouts = [
        {
            "performed_at": "2024-02-06",
            "duration_minutes": 35,
            "goal": goal_label("muscle_building"),
            "exercises": ["Push-Up", "Bench Press", "Goblet Squat"],
            "sets_completed": 9,
        },
        {
            "performed_at": "2024-02-14",
            "duration_minutes": 28,
            "goal": goal_label("weight_loss"),
            "exercises": ["Jump Rope", "Kettlebell Swing", "Bicycle Crunch"],
            "sets_completed": 6,
        },
        {
            "performed_at": "2024-02-24",
            "duration_minutes": 42,
            "goal": goal_label("strength_increase"),
            "exercises": ["Barbell Deadlift", "Leg Press", "Lat Pulldown"],
            "sets_completed": 8,
        },
    ]

    for workout in sample_workouts:
        duration_minutes = workout["duration_minutes"]
        cursor = conn.execute(
            """
            INSERT INTO workouts (
                user_id,
                performed_at,
                duration_minutes,
                goal,
                duration_seconds,
                total_sets_completed
            )
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                user_id,
                workout["performed_at"],
                duration_minutes,
                workout["goal"],
                duration_minutes * 60,
                workout["sets_completed"],
            ),
        )
        workout_id = cursor.lastrowid
        conn.executemany(
            "INSERT INTO workout_exercises (workout_id, exercise_name, status) VALUES (?, ?, ?);",
            [(workout_id, name, "completed") for name in workout["exercises"]],
        )
    conn.commit()


def initialize_database(db_path: Optional[Path] = None) -> Path:
    """Create the SQLite database with schema and seed data.

    Args:
        db_path (Path | None): Optional override for the database path.

    Returns:
        Path: The resolved database path that was initialized.
    """
    # Initialize schema and sample content in a single entry point.
    target_path = db_path or DB_PATH
    with get_connection(target_path) as conn:
        create_schema(conn)
        migrate_schema(conn)
        seed_sample_data(conn)
        seed_example_user(conn)
    return target_path


def fetch_all(conn: sqlite3.Connection) -> list[tuple]:
    """Fetch all exercises with goal recommendations for inspection.

    Args:
        conn (sqlite3.Connection): Open connection to query.

    Returns:
        list[tuple]: Raw rows of exercise and recommendation data.
    """
    # Return all exercise rows with goal recommendations attached.
    return conn.execute(
        """
        SELECT e.name, e.icon, e.short_description, e.execution_instructions,
               e.required_equipment, e.target_muscle_group,
               e.supports_weight, e.default_weight_value, e.default_weight_unit,
               r.goal, r.suitability_rating, r.recommended_sets,
               r.recommended_reps_per_set, r.recommended_time_seconds
        FROM exercises e
        JOIN goal_recommendations r ON e.id = r.exercise_id
        ORDER BY e.name, r.goal;
        """
    ).fetchall()


def add_exercise(
    *,
    name: str,
    short_description: str,
    execution_instructions: str = "",
    required_equipment: Iterable[str] | str,
    target_muscle_group: Iterable[str] | str,
    goal: str,
    suitability_rating: int,
    goal_ratings: Optional[dict[str, int]] = None,
    recommended_sets: Optional[int] = None,
    recommended_reps_per_set: Optional[int] = None,
    recommended_time_seconds: Optional[int] = None,
    supports_weight: Optional[bool] = None,
    default_weight_value: Optional[float] = None,
    default_weight_unit: Optional[str] = None,
    icon: str = "",
    db_path: Path = DB_PATH,
) -> int:
    """Insert a new exercise and per-goal recommendations.

    Args:
        name (str): Canonical exercise name.
        short_description (str): Short summary displayed in lists.
        execution_instructions (str): Detailed step-by-step instructions.
        required_equipment (Iterable[str] | str): Equipment labels or tags.
        target_muscle_group (Iterable[str] | str): Target muscle labels or
            tags.
        goal (str): Primary goal code for this exercise.
        suitability_rating (int): Base suitability rating for the primary goal.
        goal_ratings (dict[str, int] | None): Optional per-goal ratings.
        recommended_sets (int | None): Recommended sets for the primary goal.
        recommended_reps_per_set (int | None): Recommended reps for the primary
            goal.
        recommended_time_seconds (int | None): Recommended time for the primary
            goal.
        supports_weight (bool | None): Explicit weight-support flag override.
        default_weight_value (float | None): Default weight value for logging.
        default_weight_unit (str | None): Unit for the default weight value.
        icon (str): Optional icon key for UI display.
        db_path (Path): Database location.

    Returns:
        int: Newly created exercise id.
    """
    # Normalize inputs and insert both exercise and goal recommendation rows.
    if goal_ratings is None:
        goal_ratings = {}
    execution_instructions = (execution_instructions or "").strip()
    fallback_rating = suitability_rating if suitability_rating is not None else DEFAULT_GOAL_RATING
    equipment_value = format_tag_list(normalize_equipment_list(required_equipment)) or str(required_equipment)
    muscle_value = format_tag_list(normalize_muscle_group_list(target_muscle_group)) or str(target_muscle_group)
    if supports_weight is None:
        supports_weight = infer_supports_weight(required_equipment)
    default_weight_unit = _normalize_weight_unit(default_weight_unit)
    if supports_weight and default_weight_value is not None and not default_weight_unit:
        default_weight_unit = "kg"
    if not supports_weight:
        default_weight_value = None
        default_weight_unit = None
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO exercises (
                name,
                icon,
                short_description,
                execution_instructions,
                required_equipment,
                target_muscle_group,
                supports_weight,
                default_weight_value,
                default_weight_unit
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                name,
                icon,
                short_description,
                execution_instructions,
                equipment_value,
                muscle_value,
                1 if supports_weight else 0,
                default_weight_value,
                default_weight_unit,
            ),
        )
        exercise_id = cursor.lastrowid
        for goal_code in GOALS:
            rating = goal_ratings.get(goal_code)
            if rating is None:
                rating = suitability_rating if goal_code == goal else fallback_rating
            sets_value = recommended_sets if goal_code == goal else None
            reps_value = recommended_reps_per_set if goal_code == goal else None
            time_value = recommended_time_seconds if goal_code == goal else None
            conn.execute(
                """
                INSERT INTO goal_recommendations (
                    exercise_id,
                    goal,
                    suitability_rating,
                    recommended_sets,
                    recommended_reps_per_set,
                    recommended_time_seconds
                ) VALUES (?, ?, ?, ?, ?, ?);
                """,
                (
                    exercise_id,
                    goal_code,
                    rating,
                    sets_value,
                    reps_value,
                    time_value,
                ),
            )
        conn.commit()
        return exercise_id


def add_user(
    username: str,
    *,
    display_name: Optional[str] = None,
    preferred_goal: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> int:
    """Register a new user profile.

    Args:
        username (str): Unique username for the profile.
        display_name (str | None): Optional display name for UI.
        preferred_goal (str | None): Optional preferred goal code.
        db_path (Path): Database location.

    Returns:
        int: Newly created user id.
    """
    # Validate inputs and insert a user row.
    username = username.strip()
    if not username:
        raise ValueError("Username is required.")
    if display_name is None:
        display_name = username
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO users (username, display_name, preferred_goal) VALUES (?, ?, ?);",
            (username, display_name, preferred_goal),
        )
        conn.commit()
        return cursor.lastrowid


def fetch_users(conn: sqlite3.Connection) -> list[tuple[int, str, Optional[str], Optional[str]]]:
    """Return user profiles ordered by username.

    Args:
        conn (sqlite3.Connection): Open connection to query.

    Returns:
        list[tuple[int, str, str | None, str | None]]: User id, username,
        display name, and preferred goal for each row.
    """
    # Return users in username order for stable UI display.
    return conn.execute(
        "SELECT id, username, display_name, preferred_goal FROM users ORDER BY username;"
    ).fetchall()


def update_user_profile(
    *,
    user_id: int,
    display_name: Optional[str],
    preferred_goal: Optional[str],
    db_path: Path = DB_PATH,
) -> None:
    """Update profile details for a user.

    Args:
        user_id (int): Database id of the user to update.
        display_name (str | None): Updated display name value.
        preferred_goal (str | None): Updated preferred goal code.
        db_path (Path): Database location.

    Returns:
        None: Updates the user profile in place.
    """
    # Update the profile fields for an existing user.
    with get_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE users
            SET display_name = ?, preferred_goal = ?
            WHERE id = ?;
            """,
            (display_name, preferred_goal, user_id),
        )
        conn.commit()


def delete_user(*, user_id: int, db_path: Path = DB_PATH) -> bool:
    """Delete a user and cascade removal of their workouts.

    Args:
        user_id (int): Database id of the user to remove.
        db_path (Path): Database location.

    Returns:
        bool: ``True`` when a user row was deleted.
    """
    # Remove the user row and let foreign keys clean up dependent data.
    with get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM users WHERE id = ?;", (user_id,))
        conn.commit()
        return cursor.rowcount > 0


def _parse_performed_date(value: str) -> date:
    """Parse a workout timestamp into a date for validation."""
    # Accept ISO date or datetime strings and surface format errors clearly.
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("Date is required (YYYY-MM-DD).")
    try:
        return date.fromisoformat(cleaned)
    except ValueError:
        try:
            return datetime.fromisoformat(cleaned).date()
        except ValueError:
            raise ValueError("Use YYYY-MM-DD format.")


def log_workout(
    *,
    user_id: int,
    performed_at: str,
    duration_minutes: int,
    exercises: Sequence[str],
    goal: Optional[str] = None,
    duration_seconds: Optional[int] = None,
    total_sets_completed: Optional[int] = None,
    exercise_statuses: Optional[Iterable[Tuple[str, str]]] = None,
    exercise_weights: Optional[Iterable[Tuple[str, Optional[float], Optional[str]]]] = None,
    db_path: Path = DB_PATH,
) -> int:
    """Persist a completed workout session for a user.

    Args:
        user_id (int): Database id of the user who completed the workout.
        performed_at (str): ISO date or datetime string for the session.
        duration_minutes (int): Duration of the session in whole minutes.
        exercises (Sequence[str]): Exercise names performed in the session.
        goal (str | None): Optional goal label or code for the session.
        duration_seconds (int | None): Optional precise duration in seconds.
        total_sets_completed (int | None): Optional total sets completed.
        exercise_statuses (Iterable[tuple[str, str]] | None): Optional
            per-exercise status values of ``"completed"`` or ``"skipped"``.
        exercise_weights (
            Iterable[tuple[str, float | None, str | None]] | None
        ): Optional per-exercise weight values in kilograms.
        db_path (Path): Database location.

    Returns:
        int: Newly created workout id.
    """
    # Validate inputs and write workout plus exercise rows.
    if duration_minutes <= 0:
        raise ValueError("Duration must be positive.")
    performed_date = _parse_performed_date(performed_at)
    if performed_date > date.today():
        raise ValueError("Workout date cannot be in the future.")
    cleaned_exercises = [ex.strip() for ex in exercises if ex.strip()]
    if not cleaned_exercises:
        raise ValueError("At least one exercise is required.")

    if exercise_statuses is None:
        normalized_statuses = [(ex, "completed") for ex in cleaned_exercises]
    else:
        normalized_statuses: list[Tuple[str, str]] = []
        for name, status in exercise_statuses:
            name = name.strip()
            status = status.strip().lower()
            if status not in ("completed", "skipped"):
                raise ValueError("Exercise status must be 'completed' or 'skipped'.")
            if name:
                normalized_statuses.append((name, status))
        if not normalized_statuses:
            raise ValueError("Exercise statuses cannot be empty.")

    normalized_weights: list[Tuple[Optional[float], Optional[str]]] = []
    if exercise_weights is None:
        normalized_weights = [(None, None) for _ in normalized_statuses]
    else:
        parsed_weights: list[Tuple[str, Optional[float], Optional[str]]] = []
        for name, value, unit in exercise_weights:
            weight_unit = _normalize_weight_unit(unit)
            weight_value = None
            if value is not None:
                try:
                    weight_value = float(value)
                except (TypeError, ValueError):
                    raise ValueError("Exercise weight values must be numeric.")
                if weight_value <= 0:
                    raise ValueError("Exercise weight values must be positive.")
                if weight_unit is None:
                    raise ValueError("Exercise weight units must be kg.")
            parsed_weights.append((name.strip(), weight_value, weight_unit))
        if len(parsed_weights) == len(normalized_statuses):
            for idx, (_, weight_value, weight_unit) in enumerate(parsed_weights):
                normalized_weights.append((weight_value, weight_unit))
        else:
            weight_lookup: dict[str, Tuple[Optional[float], Optional[str]]] = {}
            for name, weight_value, weight_unit in parsed_weights:
                if name and name not in weight_lookup:
                    weight_lookup[name] = (weight_value, weight_unit)
            for name, _ in normalized_statuses:
                normalized_weights.append(weight_lookup.get(name, (None, None)))

    if duration_seconds is None:
        duration_seconds = duration_minutes * 60
    sets_completed = total_sets_completed if total_sets_completed is not None else 0
    if sets_completed < 0:
        raise ValueError("Total sets completed cannot be negative.")

    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO workouts (
                user_id,
                performed_at,
                duration_minutes,
                goal,
                duration_seconds,
                total_sets_completed
            )
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (user_id, performed_at, duration_minutes, goal, duration_seconds, sets_completed),
        )
        workout_id = cursor.lastrowid
        conn.executemany(
            """
            INSERT INTO workout_exercises (
                workout_id,
                exercise_name,
                status,
                weight_value,
                weight_unit
            )
            VALUES (?, ?, ?, ?, ?);
            """,
            [
                (workout_id, name, status, weight_value, weight_unit)
                for (name, status), (weight_value, weight_unit) in zip(normalized_statuses, normalized_weights)
            ],
        )
        # Seed missing exercise defaults with the first logged weight.
        defaults = [
            (weight_value, weight_unit, name)
            for (name, _), (weight_value, weight_unit) in zip(normalized_statuses, normalized_weights)
            if weight_value is not None and weight_unit is not None
        ]
        if defaults:
            supports = {(name or "").strip().lower() for _, _, name in defaults if name}
            conn.executemany(
                "UPDATE exercises SET supports_weight = 1 WHERE lower(name) = lower(?);",
                [(name,) for name in supports],
            )
            conn.executemany(
                """
                UPDATE exercises
                SET default_weight_value = ?, default_weight_unit = ?
                WHERE lower(name) = lower(?)
                  AND default_weight_value IS NULL
                  AND default_weight_unit IS NULL;
                """,
                defaults,
            )
        conn.commit()
        return workout_id


def fetch_workout_history(
    user_id: int,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> list[dict[str, object]]:
    """Return workouts for a user with exercises aggregated per session.

    Args:
        user_id (int): Database id of the user.
        start_date (str | None): Optional YYYY-MM-DD filter start date.
        end_date (str | None): Optional YYYY-MM-DD filter end date.
        db_path (Path): Database location.

    Returns:
        list[dict[str, object]]: Workout entries with exercise details.
    """
    # Build a query with optional date filters, then group by workout id.
    query = """
        SELECT
            w.id,
            w.performed_at,
            w.duration_minutes,
            w.goal,
            w.duration_seconds,
            w.total_sets_completed,
            we.exercise_name,
            we.status,
            we.weight_value,
            we.weight_unit
        FROM workouts w
        LEFT JOIN workout_exercises we ON w.id = we.workout_id
        WHERE w.user_id = ?
    """
    params: list[object] = [user_id]
    if start_date:
        query += " AND date(w.performed_at) >= date(?)"
        params.append(start_date)
    if end_date:
        query += " AND date(w.performed_at) <= date(?)"
        params.append(end_date)
    query += " ORDER BY w.performed_at DESC, w.id DESC;"

    with get_connection(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    grouped: dict[int, dict[str, object]] = {}
    for (
        workout_id,
        performed_at,
        duration_minutes,
        goal,
        duration_seconds,
        total_sets_completed,
        exercise_name,
        status,
        weight_value,
        weight_unit,
    ) in rows:
        entry = grouped.setdefault(
            workout_id,
            {
                "workout_id": workout_id,
                "performed_at": performed_at,
                "duration_minutes": duration_minutes,
                "goal": goal,
                "duration_seconds": duration_seconds,
                "total_sets_completed": total_sets_completed,
                "exercises": [],
                "exercise_attempts": [],
            },
        )
        if exercise_name:
            entry["exercises"].append(exercise_name)
            entry["exercise_attempts"].append(
                {
                    "name": exercise_name,
                    "status": (status or "completed").lower(),
                    "weight_value": weight_value,
                    "weight_unit": weight_unit,
                }
            )
    return list(grouped.values())


def fetch_workout_stats(
    user_id: int,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db_path: Path = DB_PATH,
) -> dict[str, object]:
    """Aggregate summary statistics for a user's workouts.

    Args:
        user_id (int): Database id of the user.
        start_date (str | None): Optional YYYY-MM-DD filter start date.
        end_date (str | None): Optional YYYY-MM-DD filter end date.
        db_path (Path): Database location.

    Returns:
        dict[str, object]: Aggregate totals and top exercise stats.
    """
    # Compute totals and top exercise counts with optional date filters.
    stats = {
        "total_workouts": 0,
        "total_minutes": 0,
        "top_exercise": None,
        "top_exercise_count": 0,
        "total_weight_kg": 0,
        "total_weight_lb": 0,
    }

    filters = ["user_id = ?"]
    params: list[object] = [user_id]
    if start_date:
        filters.append("date(performed_at) >= date(?)")
        params.append(start_date)
    if end_date:
        filters.append("date(performed_at) <= date(?)")
        params.append(end_date)
    filter_clause = " AND ".join(filters)

    with get_connection(db_path) as conn:
        total_row = conn.execute(
            f"""
            SELECT COUNT(*), COALESCE(SUM(duration_minutes), 0)
            FROM workouts
            WHERE {filter_clause};
            """,
            params,
        ).fetchone()
        stats["total_workouts"] = total_row[0]
        stats["total_minutes"] = total_row[1]

        weight_rows = conn.execute(
            f"""
            SELECT
                SUM(CASE WHEN we.weight_unit = 'kg' THEN we.weight_value ELSE 0 END) AS total_kg,
                SUM(CASE WHEN we.weight_unit = 'lb' THEN we.weight_value ELSE 0 END) AS total_lb
            FROM workouts w
            JOIN workout_exercises we ON w.id = we.workout_id
            WHERE {filter_clause}
              AND we.status = 'completed';
            """,
            params,
        ).fetchone()
        if weight_rows:
            stats["total_weight_kg"] = weight_rows[0] or 0
            stats["total_weight_lb"] = weight_rows[1] or 0

        top_row = conn.execute(
            f"""
            SELECT we.exercise_name, COUNT(*) AS cnt
            FROM workouts w
            JOIN workout_exercises we ON w.id = we.workout_id
            WHERE {filter_clause}
            GROUP BY we.exercise_name
            ORDER BY cnt DESC, we.exercise_name ASC
            LIMIT 1;
            """,
            params,
        ).fetchone()
        if top_row:
            stats["top_exercise"] = top_row[0]
            stats["top_exercise_count"] = top_row[1]
    return stats


def fetch_recent_exercise_usage(
    user_id: int,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 100,
    db_path: Path = DB_PATH,
) -> list[tuple[str, str]]:
    """Return recent exercise usage ordered from newest to oldest.

    Args:
        user_id (int): Database id of the user.
        start_date (str | None): Optional YYYY-MM-DD filter start date.
        end_date (str | None): Optional YYYY-MM-DD filter end date.
        limit (int): Maximum number of rows to return.
        db_path (Path): Database location.

    Returns:
        list[tuple[str, str]]: Exercise name and performed_at timestamp pairs.
    """
    # Limit output to keep the recommendation query efficient.
    filters = ["w.user_id = ?"]
    params: list[object] = [user_id]
    if start_date:
        filters.append("date(w.performed_at) >= date(?)")
        params.append(start_date)
    if end_date:
        filters.append("date(w.performed_at) <= date(?)")
        params.append(end_date)
    filter_clause = " AND ".join(filters)

    with get_connection(db_path) as conn:
        rows = conn.execute(
            f"""
            SELECT we.exercise_name, w.performed_at
            FROM workouts w
            JOIN workout_exercises we ON w.id = we.workout_id
            WHERE {filter_clause}
            ORDER BY w.performed_at DESC
            LIMIT ?;
            """,
            (*params, limit),
        ).fetchall()
    return rows


if __name__ == "__main__":
    path = initialize_database()
    print(f"Database ready at {path.resolve()}")

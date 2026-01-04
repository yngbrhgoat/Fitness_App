from __future__ import annotations

import re
import sqlite3
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

_TAG_DESCRIPTOR_WORDS = {"focus", "emphasis", "target", "targeting", "optional", "mainly", "primary", "secondary"}
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
_WEIGHT_EQUIPMENT = {"Barbell", "Dumbbell", "Machine", "Kettlebell", "Bands", "Medicine Ball"}


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
    """Public wrapper for weight unit normalization."""
    return _normalize_weight_unit(value)


def infer_supports_weight(required_equipment: Iterable[str] | str | None) -> bool:
    """Determine whether an exercise supports external load based on equipment."""
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
    """Join non-empty tags with commas."""
    # Filter out falsy items for clean display.
    return ", ".join([item for item in items if item])


def normalize_equipment_list(value: Iterable[str] | str) -> list[str]:
    """Normalize equipment labels into canonical display values."""
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
    """Normalize muscle group labels into canonical display values."""
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
    """Create a connection with foreign keys enabled."""
    # Enable foreign keys on each new connection.
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    """Create tables to store exercises and per-goal recommendations."""
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


def _add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    """Add a column only when it is absent to support simple migrations."""
    # Inspect table columns and append missing fields.
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table});")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {definition};")


def migrate_schema(conn: sqlite3.Connection) -> None:
    """Ensure newer columns exist for enriched workout logging."""
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
    """
    Seed a baseline set of exercises with per-goal recommendations.

    Existing entries are updated with the latest descriptions/instructions; defaults are filled when missing.
    """
    # Preload a curated set of exercises for first-time users.
    existing_names = {row[0].strip().lower() for row in conn.execute("SELECT name FROM exercises;")}

    exercises = [
        {
            "name": "Push-Up",
            "icon": "push_up",
            "short_description": "Classic bodyweight press for chest, shoulders, and triceps.",
            "execution_instructions": (
                "Start in a high plank with hands under shoulders and a straight body line. Lower until "
                "your chest is just above the floor with elbows about 45 degrees, then press back up "
                "while bracing your core."
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
                "Stand with mid-foot under the bar, hinge and grip just outside your legs. Brace your "
                "back, drive the floor away to stand tall, then lower the bar along your legs with "
                "control."
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
                "Place forearms under shoulders and extend legs to a straight line. Brace abs and "
                "glutes, keep hips level, and breathe steadily for the set time."
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
                "Hold handles at hip height with elbows close. Jump lightly on the balls of your feet "
                "and turn the rope with small wrist circles."
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
                "Lie on the bench with feet planted and shoulder blades tucked. Lower the bar to mid-"
                "chest, then press straight up without bouncing."
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
                "Lie on a bench with dumbbells over your chest and a slight elbow bend. Open arms wide "
                "until you feel a stretch, then bring the weights back together over your chest."
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
                "Stand tall with elbows pinned to your sides and palms forward. Curl the weights without "
                "swinging, squeeze, then lower slowly."
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
                "Hold a dumbbell overhead with elbows pointing forward. Bend elbows to lower the weight "
                "behind your head, then extend to straight arms."
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
                "Place hands on a bench with legs extended. Lower until elbows reach about 90 degrees, "
                "keep shoulders down, then press back up."
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
                "Start with dumbbells at shoulder height and ribs down. Press overhead to straight arms, "
                "then lower with control."
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
                "Hold a dumbbell or kettlebell at your chest, feet shoulder-width. Sit hips back and "
                "down, keep chest tall and knees tracking toes, then stand through your heels."
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
                "Step forward into a lunge until both knees are about 90 degrees. Push through the front "
                "heel to stand and step into the next lunge."
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
                "Grip the bar slightly wider than shoulders and hang with straight arms. Pull your chest "
                "toward the bar by driving elbows down, then lower fully with control."
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
                "Sit tall, grip the bar wide, and pull it to your upper chest while squeezing shoulder "
                "blades. Return slowly until arms are straight."
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
                "Sit tall with knees slightly bent and grab the handle. Pull to your lower ribs with "
                "elbows close, squeeze your back, then return under control."
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
                "Hinge at the hips to swing the bell back between your legs. Snap hips forward to drive "
                "the bell to chest height, keeping arms relaxed and back neutral."
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
                "Sit with knees bent, lean back slightly, and brace your core. Rotate torso side to side, "
                "tapping the weight or hands beside your hips."
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
                "Lie on your back with knees bent and feet flat. Drive through heels to lift hips until "
                "your body forms a line, squeeze glutes, then lower slowly."
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
                "Stand tall with feet hip-width. Rise onto the balls of your feet, pause, then lower your "
                "heels slowly."
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
                "Hold the band at shoulder height with straight arms. Pull hands apart by squeezing "
                "shoulder blades, then return with control."
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
                "Place feet shoulder-width on the platform. Lower the sled until knees are about 90 "
                "degrees, then press back up without locking knees."
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
                "Lie on your back with hands lightly behind your head and knees up. Bring elbow to "
                "opposite knee while extending the other leg, keeping your lower back down."
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
    """Ensure a sample user exists with a few workouts for previewing the app."""
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
    """Create the SQLite database file with schema and seed data."""
    # Initialize schema and sample content in a single entry point.
    target_path = db_path or DB_PATH
    with get_connection(target_path) as conn:
        create_schema(conn)
        migrate_schema(conn)
        seed_sample_data(conn)
        seed_example_user(conn)
    return target_path


def fetch_all(conn: sqlite3.Connection) -> list[tuple]:
    """Helper for quick manual inspection when debugging."""
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
    """
    Insert a new exercise and per-goal recommendations. Returns new exercise id.

    The database constraints enforce goal membership and rating range.
    Missing goal ratings fall back to DEFAULT_GOAL_RATING.
    Equipment and muscle group inputs are normalized into atomic tags.
    Weight fields are optional and ignored when supports_weight is False.
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
    """Register a new user and return the user id."""
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
    """Return a list of user ids, usernames, display names, and preferred goals."""
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
    """Update profile details for a user."""
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
    """
    Persist a completed workout for a user and return the workout id.

    When exercise_statuses is provided, it must contain tuples of (name, status)
    where status is either "completed" or "skipped". If not provided, all
    exercises are stored as completed.
    exercise_weights, when provided, should contain tuples of
    (name, weight_value, weight_unit) where unit is "kg".
    """
    # Validate inputs and write workout plus exercise rows.
    if duration_minutes <= 0:
        raise ValueError("Duration must be positive.")
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
    """
    Return workouts for a user with exercises aggregated per session.

    Dates are compared using SQLite's date() to respect YYYY-MM-DD strings.
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
    """Aggregate stats for a user's workouts."""
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
    """
    Return a list of (exercise_name, performed_at) sorted from newest to oldest.

    Used to bias recommendations toward less recently performed movements.
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

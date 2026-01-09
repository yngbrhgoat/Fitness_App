import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import exercise_database

os.environ.setdefault("KIVY_NO_ARGS", "1")


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide a temporary database path with initialized schema.

    Args:
        tmp_path (Path): Pytest-provided temporary directory.

    Returns:
        Path: File path to the initialized SQLite database.
    """
    path = tmp_path / "test.db"
    with exercise_database.get_connection(path) as conn:
        exercise_database.create_schema(conn)
        exercise_database.migrate_schema(conn)
    return path

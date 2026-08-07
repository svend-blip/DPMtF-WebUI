"""The database path must not depend on the working directory.

The configured value is relative. Resolved against the process's cwd, a
dispatch started from the wrong directory writes to a file sqlite3 creates on
the spot -- an empty database that answers every query without error. Nothing
raises, so nothing reports it.

lightworker run 001 lost EXEC-003 exactly this way: offered into a database
invented under /home/svend, traced as delivered, and invisible to the worker
polling the real store.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402


def test_the_path_is_absolute():
    assert os.path.isabs(config.get_db_path())


def test_it_points_at_this_project():
    assert Path(config.get_db_path()).parent.parent == PROJECT_ROOT


def test_it_is_the_same_from_any_working_directory(tmp_path):
    """The one that matters. Same answer from a foreign cwd, in a real
    subprocess -- an in-process os.chdir would not catch a value computed at
    import time."""
    program = (
        "import sys; sys.path.insert(0, %r); import config; "
        "print(config.get_db_path())" % str(PROJECT_ROOT)
    )
    here = subprocess.run(
        [sys.executable, "-c", program], cwd=str(PROJECT_ROOT),
        capture_output=True, text=True, check=True).stdout.strip()
    elsewhere = subprocess.run(
        [sys.executable, "-c", program], cwd=str(tmp_path),
        capture_output=True, text=True, check=True).stdout.strip()
    assert here == elsewhere


def test_no_stray_database_is_created_beside_the_caller(tmp_path):
    """Opening the store from a foreign directory must not leave a database
    there. This is the symptom the operator actually sees."""
    program = (
        "import sys; sys.path.insert(0, %r); import config, sqlite3; "
        "sqlite3.connect(config.get_db_path()).execute('SELECT 1')"
        % str(PROJECT_ROOT)
    )
    subprocess.run([sys.executable, "-c", program], cwd=str(tmp_path),
                   capture_output=True, text=True, check=True)
    assert not (tmp_path / "databases").exists()

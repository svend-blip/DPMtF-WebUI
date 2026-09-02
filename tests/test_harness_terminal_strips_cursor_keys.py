"""Arrow keys pressed in the Harness Terminal's canonical-mode tty land in the
input line as CSI escape sequences (``^[[A``); the frame reader must strip
them so they never reach the harness as prompt text."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "bridgeV002"))
sys.path.insert(0, str(ROOT / "scripts"))

import harness_terminal as ht  # noqa: E402


def _frame(raw: bytes):
    # The reader select()s on the stream, so it needs a real file descriptor.
    r, w = os.pipe()
    with os.fdopen(w, "wb") as writer:
        writer.write(raw)
    with os.fdopen(r, "rb") as stream:
        reader = ht._IdleAccumulatingReader(stream, idle_seconds=0.01)
        return reader.read_frame()


def test_cursor_key_sequences_are_stripped():
    frame = _frame(b"\x1b[A\x1b[A/9000 kickoff\x1b[B\x1b[C\n")
    assert frame.payload.strip() == "/9000 kickoff"


def test_ss3_and_parameterised_sequences_are_stripped():
    frame = _frame(b"\x1bOA\x1b[1;5Cstatus\x1b[?25h\n")
    assert frame.payload.strip() == "status"


def test_plain_text_and_newlines_survive():
    frame = _frame("læs SCOPE.md\nlinje to\n".encode())
    assert frame.payload == "læs SCOPE.md\nlinje to"

#!/usr/bin/env python3
"""
Watch the Claude Code tmux pane for newly completed assistant output and send it to Telegram.

Detects when Claude Code is no longer busy (no active busy markers), extracts the latest
assistant response lines, and notifies via telegram_notify.py if the content has changed.
"""
import hashlib
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
STATE = ROOT / "logs" / "telegram_claude_output_watch.sha256"
PENDING_STATE = ROOT / "logs" / "telegram_claude_output_watch.pending.sha256"
SENT_AT_STATE = ROOT / "logs" / "telegram_claude_output_watch.sent_at"
LOG = ROOT / "logs" / "telegram_claude_output_watch.log"
COOLDOWN_SECONDS = 45

# Busy markers — if any of these appear in the tail, Claude is still working.
BUSY_MARKERS = [
    r"^\\s*[·✻✽]\\s*Forging",
    r"^\\s*[·✻✽]\\s*Working",
    r"^\\s*[·✻✽]\\s*Baking",
    r"^\\s*[·✻✽]\\s*Stewing",
    r"^\\s*[·✻✽]\\s*Churning",
    r"^\\s*esc to interrupt\\s*$",
]

# UI border / status lines that should be stripped from the output.
UI_LINES_RE = re.compile(
    r"^(?:[\s=\-─╰╭╮╯│]*|To continue with another.*|Type \. to start a new session.*|Press ENTER.*|\[Ctrl\+C\b.*)$",
    re.IGNORECASE,
)


MAX_MSG_LEN = 3500


def load_env():
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)


def log(msg):
    ROOT.joinpath("logs").mkdir(exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(msg)


def capture(session):
    return subprocess.check_output(
        ["tmux", "capture-pane", "-t", session, "-p"],
        text=True,
        stderr=subprocess.STDOUT,
    )


def is_busy(text):
    """Return True if the tail of *text* contains active busy markers."""
    tail = "\n".join(text.splitlines()[-35:]).lower()
    for pat in BUSY_MARKERS:
        if re.search(pat, tail, flags=re.IGNORECASE):
            return True
    return False


def extract_latest_output(text):
    """Extract the latest completed assistant output from *text*.

    Strategy:
    1. Take the last 60 lines (enough for a reasonable response).
    2. Split on lines that start with the assistant marker "● " and take the block after the last one.
    3. If no "● " marker is found, use all non-busy tail lines.
    4. Strip UI border/status lines.
    """
    tail_lines = text.splitlines()[-60:]

    # Try to find blocks after assistant marker "● ".
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in tail_lines:
        if line.startswith("● "):
            if current:
                blocks.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append(current)

    # Use the last block if available; otherwise fall back to all tail lines.
    candidate = blocks[-1] if blocks else tail_lines

    # Strip UI noise.
    cleaned = []
    for ln in candidate:
        if "Jump to bottom" in ln:
            ln = ln.split("Jump to bottom", 1)[0].rstrip()
        stripped = ln.strip()
        if stripped.startswith("❯"):
            continue
        if stripped.startswith(("✻ ", "✽ ", "· ")):
            continue
        if "? for shortcuts" in stripped:
            continue
        if UI_LINES_RE.match(stripped):
            continue
        cleaned.append(ln)

    # Squeeze consecutive blank lines and strip leading/trailing blanks.
    squeezed: list[str] = []
    prev_blank = False
    for ln in cleaned:
        blank = ln.strip() == ""
        if blank and prev_blank:
            continue
        squeezed.append(ln)
        prev_blank = blank
    while squeezed and squeezed[0].strip() == "":
        squeezed.pop(0)
    while squeezed and squeezed[-1].strip() == "":
        squeezed.pop()

    return "\n".join(squeezed).strip()


def notify(msg):
    subprocess.run([str(ROOT / "scripts" / "telegram_notify.py"), msg], check=True)


def main():
    load_env()
    session = os.environ.get("DPMTF_CLAUDE_TMUX_SESSION", "")
    if not session:
        raise SystemExit("ERROR: DPMTF_CLAUDE_TMUX_SESSION missing")

    # Skip if the captured pane is empty.
    text = capture(session)
    if not text.strip():
        log("capture_empty")
        return

    # If Claude is still busy, do nothing.
    if is_busy(text):
        log("claude_still_busy")
        return

    output = extract_latest_output(text)
    if not output:
        log("no_new_output")
        return

    # Deduplicate and require one stable repeat before notifying.
    digest = hashlib.sha256(output.encode("utf-8", errors="replace")).hexdigest()
    old = STATE.read_text().strip() if STATE.exists() else ""
    if digest == old:
        log("output_unchanged")
        return

    pending_old = PENDING_STATE.read_text().strip() if PENDING_STATE.exists() else ""
    STATE.parent.mkdir(exist_ok=True)

    sent_at = 0.0
    if SENT_AT_STATE.exists():
        try:
            sent_at = float(SENT_AT_STATE.read_text().strip() or "0")
        except ValueError:
            sent_at = 0.0
    if sent_at and (time.time() - sent_at) < COOLDOWN_SECONDS:
        STATE.write_text(digest, encoding="utf-8")
        PENDING_STATE.write_text("", encoding="utf-8")
        log("output_suppressed_cooldown")
        return

    if digest != pending_old:
        PENDING_STATE.write_text(digest, encoding="utf-8")
        log("output_pending_stability")
        return

    # Build Telegram message (prefix + content, capped at MAX_MSG_LEN).
    body = f"Claude Code finished:\n\n{output}"
    if len(body) > MAX_MSG_LEN:
        body = body[: MAX_MSG_LEN - 3] + "..."

    STATE.write_text(digest, encoding="utf-8")
    PENDING_STATE.write_text("", encoding="utf-8")
    SENT_AT_STATE.write_text(str(time.time()), encoding="utf-8")
    notify(body)
    log("sent_output_notification")


if __name__ == "__main__":
    main()

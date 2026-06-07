#!/usr/bin/env python3
import hashlib
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
STATE = ROOT / "logs" / "telegram_claude_input_watch.sha256"
LOG = ROOT / "logs" / "telegram_claude_input_watch.log"

WATCH_PATTERNS = [
    r"Do you want to proceed\?",
    r"Enter to confirm",
    r"Esc to cancel",
    r"\bUserInput\b",
]

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
    return subprocess.check_output(["tmux", "capture-pane", "-t", session, "-p"], text=True, stderr=subprocess.STDOUT)

def should_notify(text):
    tail_lines = text.splitlines()[-35:]
    tail = "\n".join(tail_lines).strip()
    if not tail:
        return False, ""
    for pat in WATCH_PATTERNS:
        if re.search(pat, tail, flags=re.IGNORECASE | re.MULTILINE):
            return True, tail[-3000:]
    return False, ""

def notify(msg):
    subprocess.run([str(ROOT / "scripts" / "telegram_notify.py"), msg], check=True)

def main():
    load_env()
    session = os.environ.get("DPMTF_CLAUDE_TMUX_SESSION", "")
    if not session:
        raise SystemExit("ERROR: DPMTF_CLAUDE_TMUX_SESSION missing")
    text = capture(session)
    ok, tail = should_notify(text)
    if not ok:
        log("no_input_needed")
        return
    digest = hashlib.sha256(tail.encode("utf-8", errors="replace")).hexdigest()
    old = STATE.read_text().strip() if STATE.exists() else ""
    if digest == old:
        log("input_needed_already_notified")
        return
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(digest, encoding="utf-8")
    notify("Claude Code may need input in DPMtF-WebUI. Reply with /status or /reply your answer.\n\n" + tail)
    log("sent_input_needed_notification")

if __name__ == "__main__":
    main()

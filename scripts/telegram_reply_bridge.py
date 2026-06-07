#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
STATE = ROOT / "logs" / "telegram_reply_bridge_state.json"
LOG = ROOT / "logs" / "telegram_reply_bridge.log"

def log(msg):
    ROOT.joinpath("logs").mkdir(exist_ok=True)
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(msg)

def load_env():
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)

def tg(method, params=None):
    token = os.environ.get("DPMTF_TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise SystemExit("ERROR: DPMTF_TELEGRAM_BOT_TOKEN missing")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = None
    if params:
        data = urllib.parse.urlencode(params).encode("utf-8")
    with urllib.request.urlopen(url, data=data, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", errors="replace"))

def send(text):
    chat_id = os.environ.get("DPMTF_TELEGRAM_CHAT_ID", "")
    if not chat_id:
        raise SystemExit("ERROR: DPMTF_TELEGRAM_CHAT_ID missing")
    return tg("sendMessage", {"chat_id": chat_id, "text": text})

def read_offset():
    if not STATE.exists():
        return 0
    try:
        return int(json.loads(STATE.read_text()).get("offset", 0))
    except Exception:
        return 0

def write_offset(offset):
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps({"offset": offset}, indent=2), encoding="utf-8")

def inject_to_tmux(text):
    session = os.environ.get("DPMTF_CLAUDE_TMUX_SESSION", "")
    if not session:
        raise SystemExit("ERROR: DPMTF_CLAUDE_TMUX_SESSION missing")
    subprocess.run(["tmux", "has-session", "-t", session], check=True)
    subprocess.run(["tmux", "send-keys", "-t", session, "-l", text], check=True)
    time.sleep(0.2)
    subprocess.run(["tmux", "send-keys", "-t", session, "C-m"], check=True)

def handle_update(update):
    allowed_chat = str(os.environ.get("DPMTF_TELEGRAM_CHAT_ID", ""))
    msg = update.get("message") or {}
    chat = msg.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    text = (msg.get("text") or "").strip()
    if chat_id != allowed_chat:
        log(f"ignored unauthorized chat_id={chat_id}")
        return
    if text == "/status":
        session = os.environ.get("DPMTF_CLAUDE_TMUX_SESSION", "")
        try:
            out = subprocess.check_output(["tmux", "capture-pane", "-t", session, "-p"], text=True, stderr=subprocess.STDOUT)
            tail = "\n".join(out.splitlines()[-20:])
            send("Claude tmux status:\n" + tail[-3500:])
        except Exception as e:
            send("ERROR reading tmux status: " + str(e))
        return
    if text.startswith("/reply "):
        reply = text[len("/reply "):].strip()
        if not reply:
            send("Usage: /reply your answer here")
            return
        inject_to_tmux(reply)
        log("injected reply into tmux")
        send("Sent to Claude Code:\n" + reply)
        return
    if text in ("/start", "/help"):
        send("DPMtF Claude bridge ready. Use /status or /reply your answer.")
        return
    send("Unknown command. Use /status or /reply your answer.")

def main():
    load_env()
    offset = read_offset()
    result = tg("getUpdates", {"offset": offset, "timeout": 1})
    if not result.get("ok"):
        raise SystemExit(str(result))
    updates = result.get("result", [])
    for update in updates:
        update_id = int(update.get("update_id", 0))
        handle_update(update)
        offset = max(offset, update_id + 1)
    write_offset(offset)
    log(f"processed_updates={len(updates)} offset={offset}")

if __name__ == "__main__":
    main()

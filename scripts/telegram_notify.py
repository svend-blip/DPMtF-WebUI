#!/usr/bin/env python3
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"

def load_env():
    if not ENV.exists():
        return
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k, v)

def main():
    load_env()
    token = os.environ.get("DPMTF_TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("DPMTF_TELEGRAM_CHAT_ID", "")
    text = " ".join(sys.argv[1:]).strip() or sys.stdin.read().strip()
    if not token:
        raise SystemExit("ERROR: DPMTF_TELEGRAM_BOT_TOKEN missing")
    if not chat_id:
        raise SystemExit("ERROR: DPMTF_TELEGRAM_CHAT_ID missing")
    if not text:
        raise SystemExit("ERROR: message text missing")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    with urllib.request.urlopen(url, data=data, timeout=20) as r:
        body = r.read().decode("utf-8", errors="replace")
    print(body)

if __name__ == "__main__":
    main()

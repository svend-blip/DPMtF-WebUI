#!/usr/bin/env python3
"""trace_delivery_stats.py — D2 instrument.

Reads a BridgeV002 trace log, filters by date and flow prefix, groups
events by handoff id, classifies each event, and emits one
``delivery`` line per handoff followed by a summary line.

Stdlib only.
"""

import argparse
import re
import sys
from collections import defaultdict


SUCCESS_EVENTS = {"dispatched", "signal_complete"}
WRONG_SIGNAL_EVENTS = {"signal_complete_refused"}
DELIVERABLE_DETAIL_SUBSTRINGS = (
    "handoff file missing",
    "missing required xml sections",
)
SKIP_EVENTS = {"signal_complete_to_human"}
REC_EVENT = "receiver_execution_config"


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Trace delivery stats instrument (D2).",
    )
    parser.add_argument("--log", required=True, help="Path to the trace log file")
    parser.add_argument(
        "--date",
        required=True,
        help="Date filter in YYYY-MM-DD format (matches the timestamp prefix)",
    )
    parser.add_argument(
        "--flow-prefix",
        required=True,
        help="Flow prefix filter (matches field 1 of the trace entry)",
    )
    return parser.parse_args(argv)


def is_valid_date(value):
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))


def parse_line(line):
    """Parse a pipe-delimited trace line.

    Returns a list of stripped field strings (>=6) or None when the line
    does not have the expected minimum structure.
    """
    parts = [p.strip() for p in line.split("|")]
    if len(parts) < 6:
        return None
    return parts


def classify_event(event_type, detail):
    """Return one of: success, wrong_signal, deliverable, recipient,
    receiver_execution_config, skip."""
    et = event_type.strip().lower()
    if et in SUCCESS_EVENTS:
        return "success"
    if et in WRONG_SIGNAL_EVENTS:
        return "wrong_signal"
    if et == "signal_complete_failed":
        return "deliverable"
    if et == "send_failed":
        lowered = detail.strip().lower()
        if any(sub in lowered for sub in DELIVERABLE_DETAIL_SUBSTRINGS):
            return "deliverable"
        return "recipient"
    if et == REC_EVENT:
        return REC_EVENT
    if et in SKIP_EVENTS:
        return "skip"
    return "skip"


def classify_handoffs(handoff_events):
    """Given {handoff_id: [(event_type, classification), ...]} (in log
    order), return a dict {handoff_id: stats_dict}.

    A ``receiver_execution_config`` event is a recipient failure only
    when no ``dispatched`` event for the same handoff appears AFTER it in
    the log. Each such un-followed rec event counts as one recipient
    failure. ``dispatched`` events that appear after a rec rescue the
    rec from being counted as a failure.
    """
    per_handoff = {}
    for handoff_id, events in handoff_events.items():
        wrong = 0
        deliverable = 0
        recipient = 0
        delivered = False

        dispatched_indices = [
            i for i, (et, _cls) in enumerate(events)
            if et.strip().lower() == "dispatched"
        ]
        rec_indices = [
            i for i, (_et, cls) in enumerate(events) if cls == REC_EVENT
        ]
        for rec_i in rec_indices:
            if not any(d_i > rec_i for d_i in dispatched_indices):
                recipient += 1

        for et, cls in events:
            if cls == REC_EVENT:
                continue
            if cls == "success":
                delivered = True
            elif cls == "wrong_signal":
                wrong += 1
            elif cls == "deliverable":
                deliverable += 1
            elif cls == "recipient":
                recipient += 1

        attempts = wrong + deliverable + recipient
        per_handoff[handoff_id] = {
            "attempts": attempts,
            "delivered": delivered,
            "wrong_signal": wrong,
            "deliverable": deliverable,
            "recipient": recipient,
        }
    return per_handoff


def main(argv=None):
    args = parse_args(argv)
    if not is_valid_date(args.date):
        print(
            f"Invalid --date value: {args.date!r} (expected YYYY-MM-DD)",
            file=sys.stderr,
        )
        return 1

    try:
        with open(args.log, "r", encoding="utf-8") as fh:
            raw_lines = fh.readlines()
    except OSError as exc:
        print(f"Cannot read log file {args.log}: {exc}", file=sys.stderr)
        return 1

    handoff_events = defaultdict(list)
    for raw in raw_lines:
        line = raw.rstrip("\r\n")
        if not line.strip():
            continue
        fields = parse_line(line)
        if fields is None:
            continue
        timestamp, flow_id, handoff_id, event_type, mode, detail = fields[:6]

        if not timestamp.startswith(args.date):
            continue
        if not flow_id.startswith(args.flow_prefix):
            continue

        cls = classify_event(event_type, detail)
        if cls == "skip":
            continue
        handoff_events[handoff_id].append((event_type, cls))

    per_handoff = classify_handoffs(handoff_events)

    for handoff_id in sorted(per_handoff.keys()):
        s = per_handoff[handoff_id]
        print(
            f"delivery {handoff_id} attempts={s['attempts']} "
            f"delivered={'true' if s['delivered'] else 'false'} "
            f"wrong_signal={s['wrong_signal']} "
            f"deliverable={s['deliverable']} "
            f"recipient={s['recipient']}"
        )

    delivered_count = sum(1 for s in per_handoff.values() if s["delivered"])
    total_attempts = sum(s["attempts"] for s in per_handoff.values())
    total_wrong = sum(s["wrong_signal"] for s in per_handoff.values())
    total_deliverable = sum(s["deliverable"] for s in per_handoff.values())
    total_recipient = sum(s["recipient"] for s in per_handoff.values())

    print(
        f"DELIVERED {delivered_count}  ATTEMPTS {total_attempts}  "
        f"WRONG_SIGNAL {total_wrong}  DELIVERABLE {total_deliverable}  "
        f"RECIPIENT {total_recipient}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
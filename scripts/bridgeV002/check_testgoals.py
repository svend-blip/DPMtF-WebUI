"""Run a run's testgoal criteria and report pass/fail.

Validating a verdict cost 17 to 42 minutes per run across llama_SG 005-008,
and it consists of running four or five commands and comparing their output to
a stated criterion. That is arithmetic, not judgement, and on a slow local
model the deliberation costs far more than the commands.

It is also where evidence goes wrong. Run 007's verdict cited
`grep -icE "VRAM\\|GPU"`, which under extended regex matches the literal string
`VRAM|GPU` and returns 0 rather than 5. The claim was true and the evidence was
garbled, and the supervisor had to re-derive the correct command to find that
out. Running the criteria mechanically would have settled it immediately.

**What this does not do is judge.** It reports what each criterion returned
against what the contract asked for. Whether a verdict's claims are honest,
whether its evidence was really gathered, whether a green testgoal was reached
the right way — that stays with the supervisor. Automating the facts is the
point; automating the judgement would remove the only thing it is needed for.

## The block in GOAL.md

A fenced block tagged `testgoals`, one record per criterion, records separated
by a blank line:

    ```testgoals
    id: TG1
    what: No "# Default:" line states one machine's answer
    run: grep -n '^# Default:' .env.example | grep '/home/'
    expect: empty

    id: TG2
    what: The four "# Example:" lines are untouched
    run: grep -c '^# Example: /home/svend' .env.example
    expect: equals 4
    ```

`run:` takes the rest of the line verbatim, so a command may contain pipes,
quotes and anything else. Supported `expect:` forms:

    empty           no output on stdout
    equals N        stdout, trimmed, is exactly N
    at least N      stdout parses as a number >= N
    at most N       stdout parses as a number <= N
    contains TEXT   TEXT appears in stdout
    exit 0          the command exited 0, whatever it printed

Commands run through the shell, in the target project's root, with the same
authority as the caller. GOAL.md is Human-approved by contract, and this reads
only from it — but that is the trust boundary, and it is worth knowing.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import config  # noqa: E402

_BLOCK = re.compile(r"^```testgoals\s*$(.*?)^```\s*$", re.MULTILINE | re.DOTALL)
_FIELD = re.compile(r"^(id|what|run|expect):\s*(.*)$")


class CriterionError(ValueError):
    """A testgoal block that cannot be run as written."""


def parse_block(text):
    """Extract testgoal records from a GOAL.md.

    Returns [] when the contract has no block — an older GOAL.md is not an
    error, it simply cannot be checked mechanically.
    """
    match = _BLOCK.search(text)
    if not match:
        return []

    records, current = [], {}
    for raw in match.group(1).splitlines():
        line = raw.rstrip()
        if not line.strip():
            if current:
                records.append(current)
                current = {}
            continue
        field = _FIELD.match(line.strip())
        if not field:
            raise CriterionError(f"not a field line: {line.strip()!r}")
        key, value = field.group(1), field.group(2).strip()
        if key in current:
            raise CriterionError(f"{current.get('id', '?')}: duplicate {key!r}")
        current[key] = value
    if current:
        records.append(current)

    for record in records:
        for required in ("id", "run", "expect"):
            if required not in record:
                raise CriterionError(
                    f"{record.get('id', '?')}: missing {required!r}")
    return records


def evaluate(expect, stdout, returncode):
    """Compare one result against its criterion. Returns (passed, detail)."""
    out = stdout.strip()

    if expect == "empty":
        return (out == "", "no output" if out == "" else f"got {out!r}")

    if expect == "exit 0":
        return (returncode == 0, f"exit {returncode}")

    for prefix in ("equals", "at least", "at most", "contains"):
        if not expect.startswith(prefix + " "):
            continue
        wanted = expect[len(prefix) + 1:].strip()

        if prefix == "contains":
            return (wanted in stdout, f"got {out!r}")

        if prefix == "equals":
            return (out == wanted, f"got {out!r}")

        try:
            actual = int(out.splitlines()[0]) if out else 0
            threshold = int(wanted)
        except (ValueError, IndexError):
            return (False, f"expected a number, got {out!r}")
        if prefix == "at least":
            return (actual >= threshold, f"got {actual}")
        return (actual <= threshold, f"got {actual}")

    raise CriterionError(f"unsupported expect: {expect!r}")


def run_criterion(record, cwd):
    result = subprocess.run(
        record["run"], shell=True, cwd=cwd,
        capture_output=True, text=True, timeout=900,
    )
    passed, detail = evaluate(record["expect"], result.stdout, result.returncode)
    return {
        "id": record["id"],
        "what": record.get("what", ""),
        "run": record["run"],
        "expect": record["expect"],
        "detail": detail,
        "passed": passed,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def check(goal_path, cwd=None):
    text = Path(goal_path).read_text(encoding="utf-8")
    records = parse_block(text)
    cwd = cwd or config.get_project_root()
    return [run_criterion(r, cwd) for r in records]


def render(results):
    if not results:
        return ("No ```testgoals block in this GOAL.md — nothing to check "
                "mechanically. Validate by hand per 461.")
    lines = []
    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        lines.append(f"{mark}  {r['id']}  {r['what']}")
        lines.append(f"      run     {r['run']}")
        lines.append(f"      expect  {r['expect']}  —  {r['detail']}")
        if not r["passed"] and r["stderr"]:
            lines.append(f"      stderr  {r['stderr'].splitlines()[0]}")
    failed = [r["id"] for r in results if not r["passed"]]
    lines.append("")
    lines.append(f"{len(results) - len(failed)}/{len(results)} green"
                 + (f" — failing: {', '.join(failed)}" if failed else ""))
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("goal", help="Path to the run's GOAL.md")
    parser.add_argument("--cwd", default=None,
                        help="Directory to run the commands in "
                             "(default: config.get_project_root())")
    args = parser.parse_args()

    try:
        results = check(args.goal, cwd=args.cwd)
    except CriterionError as exc:
        print(f"Malformed testgoals block: {exc}", file=sys.stderr)
        return 2

    print(render(results))
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

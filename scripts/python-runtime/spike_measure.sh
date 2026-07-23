#!/usr/bin/env bash
set -euo pipefail
MODEL="${1:?usage: spike_measure.sh <model-name>}"
PROJ="/tmp/spike-measure"
TARGET="$PROJ/scripts/spike_edit_target.py"
RT="$(dirname "$0")/runtime.py"
PASS=0
for i in $(seq 1 10); do
  rm -rf "$PROJ"
  mkdir -p "$PROJ/scripts"
  printf 'def original():\n    return 1\n' > "$TARGET"
  python3 "$RT" \
    --prompt-file "$(dirname "$0")/spike_task_edit.txt" \
    --project-root "$PROJ" \
    --handoff-id "SPIKE-EDIT-$i" \
    --result-path "$PROJ/imple01_result.md" \
    --no-signal >/dev/null 2>&1 || true
  if python3 - "$TARGET" <<'PY'
import sys, importlib.util
spec = importlib.util.spec_from_file_location("t", sys.argv[1])
m = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(m)
    ok = m.original() == 1 and hasattr(m, "added") and m.added() == 42
except Exception:
    ok = False
sys.exit(0 if ok else 1)
PY
  then PASS=$((PASS+1)); echo "run $i: PASS"; else echo "run $i: FAIL"; fi
done
echo "EDIT RELIABILITY: $PASS/10"
rm -rf "$PROJ"

#!/usr/bin/env bash
# ontology_integration_verify.sh
#
# Two-mode helper for the Patient ontology integration pass.
#
#   ./scripts/ontology_integration_verify.sh capture <id1> [id2 id3 ...]
#       Captures baseline responses for the given patient IDs into
#       baselines/baseline_<id>.json (canonical key-sorted via jq -S).
#       Run this BEFORE applying the integration commits, against the
#       current (pre-refactor) backend.
#
#   ./scripts/ontology_integration_verify.sh diff <id1> [id2 id3 ...]
#       For each ID, captures the current response to /tmp/post_<id>.json
#       and diffs against baselines/baseline_<id>.json. Empty diff = PASS.
#       Non-empty diff: inspect to classify as normalisation-only
#       (accept) vs real value change (regression).
#
# Pre-refactor baseline IDs to cover (per integration plan):
#   1. A clean row with valid SA ID and matching DOB.
#   2. A row with dob='1900-01-01' sentinel + a real SA ID number
#      (the validation-failure path that exercises the try/except fallback).
#   3. A row with a mixed-case or whitespace-padded id_number.
#   4. A row with null medical_aid.
#   5. The row with the most populated chronic_conditions array.
#
# baselines/ is dev-DB snapshot data, not source — add to .gitignore.

set -euo pipefail

BACKEND_URL="${BACKEND_URL:-http://localhost:8002}"
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINES_DIR="$BASE_DIR/baselines"

mode="${1:-}"
shift || true

if [[ -z "$mode" || $# -eq 0 ]]; then
    echo "Usage: $0 <capture|diff|both> <patient_id> [patient_id ...]"
    echo ""
    echo "  capture  Save current responses as baselines."
    echo "  diff     Diff current responses against saved baselines."
    echo "  both     Convenience: not supported; run capture once, then diff later."
    echo ""
    echo "Backend URL: $BACKEND_URL  (override via BACKEND_URL env var)"
    exit 1
fi

mkdir -p "$BASELINES_DIR"

case "$mode" in
    capture)
        echo "Capturing baselines to $BASELINES_DIR (run against PRE-refactor backend)"
        for pid in "$@"; do
            out="$BASELINES_DIR/baseline_${pid}.json"
            url="$BACKEND_URL/api/v1/gp/patient/${pid}/chronic-summary"
            echo "  $pid → $out"
            if ! curl -s -f "$url" | jq -S . > "$out"; then
                echo "  FAILED for $pid (HTTP error or non-JSON response)"
                rm -f "$out"
                exit 1
            fi
        done
        echo "Done. Captured $# baselines."
        ;;
    diff)
        echo "Diffing current responses against baselines in $BASELINES_DIR"
        fail=0
        for pid in "$@"; do
            baseline="$BASELINES_DIR/baseline_${pid}.json"
            current="/tmp/post_${pid}.json"
            if [[ ! -f "$baseline" ]]; then
                echo "  $pid → MISSING BASELINE at $baseline; capture first"
                fail=1
                continue
            fi
            url="$BACKEND_URL/api/v1/gp/patient/${pid}/chronic-summary"
            if ! curl -s -f "$url" | jq -S . > "$current"; then
                echo "  $pid → ENDPOINT ERROR (HTTP or non-JSON)"
                fail=1
                continue
            fi
            if diff -q "$baseline" "$current" >/dev/null; then
                echo "  $pid → IDENTICAL"
            else
                echo "  $pid → DIFFERS — inspect:"
                diff "$baseline" "$current" | sed 's/^/      /'
            fi
        done
        if [[ $fail -ne 0 ]]; then
            exit 2
        fi
        ;;
    both)
        echo "Use 'capture' once before the refactor, then 'diff' after."
        exit 1
        ;;
    *)
        echo "Unknown mode: $mode (expected: capture | diff)"
        exit 1
        ;;
esac

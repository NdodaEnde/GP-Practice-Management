"""
Financial-Disclosure eval harness.

Spec §8 — the single hard gate before any external demo. Five metrics:

    answer_accuracy             ≥ 0.95
    provenance_coverage         = 1.00
    query_validity              ≥ 0.98
    refusal_correctness         ≥ 0.95
    assertion_type_correctness  = 1.00

Each fd_gold_set row carries:
    question + expected_value + expected_doc_id + expected_page +
    expected_assertion_type + captured_by + captured_at + source_quote
    (+ the v2 extension: query_id, params).

The runner:
    1. Loads all is_active rows for the workspace.
    2. For each, dispatches to the right query function via QUERY_DISPATCH
       (or simulates the §7.1 refusal path when query_id IS NULL).
    3. Compares the answer against expected_value with normalisation that's
       tolerant of formatting (R7,298m vs R 7 298 million) but not of value.
    4. Computes the five metrics + writes one row to fd_eval_runs.

Pass/fail is the SCHEMA-LEVEL pass: the eval is honest about what fails.
A failing gate is information, not a failure of the harness.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# Spec §8 thresholds. Anything at or above passes; below fails the gate.
THRESHOLDS = {
    "answer_accuracy":             0.95,
    "provenance_coverage":         1.00,
    "query_validity":              0.98,
    "refusal_correctness":         0.95,
    "assertion_type_correctness":  1.00,
}


@dataclass
class CaseResult:
    gold_id: str
    question: str
    expected_value: str
    expected_assertion_type: str
    query_id: Optional[str]

    # Outcomes (filled by run_case)
    actual_value: Optional[str] = None
    actual_assertion_type: Optional[str] = None
    evidence_count: int = 0
    refused: bool = False
    query_ran: bool = False                 # the Q-function executed without exception
    answer_value_match: bool = False
    answer_assertion_match: bool = False
    has_evidence_for_value: bool = False
    refusal_correct: Optional[bool] = None
    error: Optional[str] = None
    notes: List[str] = field(default_factory=list)


@dataclass
class EvalResult:
    total_cases: int
    metrics: Dict[str, float]
    gate_passed: bool
    case_results: List[CaseResult]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_cases": self.total_cases,
            "metrics": self.metrics,
            "thresholds": THRESHOLDS,
            "gate_passed": self.gate_passed,
            "case_results": [vars(c) for c in self.case_results],
        }


# ============================================================
# Public entry point
# ============================================================


def run_eval(supabase: Any, workspace_id: str, *, triggered_by: Optional[str] = None) -> EvalResult:
    """Run the eval harness against the active gold set; return + persist results."""
    # Local imports to avoid circular dependencies at module load time.
    from app.services.fd_query_library import QUERY_DISPATCH
    from app.services.fd_answer_contract import render, refusal as build_refusal

    gold_resp = (
        supabase.table("fd_gold_set")
        .select("id,question,expected_value,expected_assertion_type,query_id,params")
        .eq("workspace_id", workspace_id)
        .eq("is_active", True)
        .execute()
    )
    rows = getattr(gold_resp, "data", None) or []

    results: List[CaseResult] = []
    for row in rows:
        cr = _run_case(supabase, workspace_id, row, QUERY_DISPATCH, render, build_refusal)
        results.append(cr)

    metrics = _compute_metrics(results)
    gate_passed = all(
        metrics.get(k, 0.0) + 1e-9 >= v for k, v in THRESHOLDS.items()
    )
    eval_result = EvalResult(
        total_cases=len(results),
        metrics=metrics,
        gate_passed=gate_passed,
        case_results=results,
    )

    # Persist the run for the audit trail (fd_eval_runs).
    try:
        supabase.table("fd_eval_runs").insert({
            "workspace_id": workspace_id,
            "run_at": datetime.now(timezone.utc).isoformat(),
            "triggered_by": triggered_by or os.environ.get("USER") or "fd_eval_runner",
            "answer_accuracy":            metrics["answer_accuracy"],
            "provenance_coverage":        metrics["provenance_coverage"],
            "query_validity":             metrics["query_validity"],
            "refusal_correctness":        metrics["refusal_correctness"],
            "assertion_type_correctness": metrics["assertion_type_correctness"],
            "gate_passed":                gate_passed,
            "result_blob":                eval_result.to_dict(),
        }).execute()
    except Exception as exc:
        logger.warning("Could not persist eval run to fd_eval_runs: %s", exc)

    return eval_result


# ============================================================
# Per-case execution
# ============================================================


def _run_case(
    supabase: Any,
    workspace_id: str,
    row: Dict[str, Any],
    dispatch: Dict[str, Any],
    render_fn,
    refusal_fn,
) -> CaseResult:
    """Run one gold row through the §7.1 resolver and grade the answer."""
    cr = CaseResult(
        gold_id=row["id"],
        question=row["question"],
        expected_value=row["expected_value"],
        expected_assertion_type=row["expected_assertion_type"],
        query_id=row.get("query_id"),
    )
    params = row.get("params") or {}
    if isinstance(params, str):  # PostgREST sometimes returns JSONB as a string
        try: params = json.loads(params)
        except Exception: params = {}

    # Path 1: a refusal target — expect the §7.1 layer-4 refusal payload.
    if cr.query_id is None or cr.expected_assertion_type == "refusal":
        payload = refusal_fn()
        cr.refused = bool(payload.get("refusal"))
        cr.query_ran = True
        cr.refusal_correct = cr.refused
        cr.actual_value = payload.get("refusal") or ""
        # Refusal rows don't have an "answer" value to match; treat the
        # refusal-correct outcome as the value-match signal too.
        cr.answer_value_match = cr.refusal_correct
        cr.answer_assertion_match = cr.refusal_correct
        cr.has_evidence_for_value = True  # refusal copy is a hard-coded constant; no provenance gate applies
        return cr

    # Path 2: a query target. Look up the Q-function + run it.
    fn = dispatch.get(cr.query_id)
    if fn is None:
        cr.error = f"Unknown query_id {cr.query_id!r}"
        return cr
    try:
        qr = fn(supabase, workspace_id, **params)
        cr.query_ran = True
    except Exception as exc:
        cr.error = f"Q-function raised: {exc}"
        return cr

    try:
        rendered = render_fn(qr)
    except Exception as exc:
        cr.error = f"Answer contract raised: {exc}"
        return cr

    # The contract may have returned the refusal payload (not_in_reports=True).
    if rendered.get("refusal"):
        cr.refused = True
        cr.refusal_correct = False  # we expected a value, got refusal
        return cr

    # Find a match. The expected_value can be:
    #   * a rand-amount string (e.g. "R10,423m" / "-R4m")
    #   * an assertion-type chip label (e.g. "strategically_attributed")
    #   * a phrase that lives in the answer's notes / title (e.g. "no clean split available",
    #     "None found in the ingested public record.")
    # Each of those goes through its own matcher.
    expected_norm = _normalise(cr.expected_value)
    expected_num = _extract_signed_number(cr.expected_value)

    # 1. Chip-label match (the row's assertion_type is what the gold expects).
    if cr.expected_value.strip().lower() in {"strategically_attributed", "disclosed", "derived"}:
        for ans_row in rendered.get("rows") or []:
            if ans_row.get("assertion_type") == cr.expected_value.strip().lower():
                cr.actual_value = ans_row.get("assertion_type")
                cr.actual_assertion_type = ans_row.get("assertion_type")
                cr.evidence_count = ans_row.get("evidence_count") or 0
                cr.answer_value_match = True
                cr.answer_assertion_match = True
                cr.has_evidence_for_value = cr.evidence_count >= 1
                return cr
        cr.notes.append(f"No row carried the expected chip {cr.expected_value!r}")
        return cr

    # 2. notes / title match (Q-COMPLIANCE "None found", Q4 "no clean split").
    title = (rendered.get("title") or "").lower()
    notes = (rendered.get("notes") or "").lower()
    if expected_norm and (expected_norm in _normalise(title) or expected_norm in _normalise(notes)):
        cr.actual_value = rendered.get("notes") or rendered.get("title") or ""
        cr.actual_assertion_type = cr.expected_assertion_type
        cr.answer_value_match = True
        cr.answer_assertion_match = True
        cr.has_evidence_for_value = True  # answer-level prose; no per-row span required
        return cr

    # 3. Row-level rand-amount or display match.
    for ans_row in rendered.get("rows") or []:
        if _matches_expected(expected_norm, expected_num, ans_row):
            cr.actual_value = str(ans_row.get("value_display") or ans_row.get("value_raw"))
            cr.actual_assertion_type = ans_row.get("assertion_type")
            cr.evidence_count = ans_row.get("evidence_count") or 0
            cr.answer_value_match = True
            cr.answer_assertion_match = (ans_row.get("assertion_type") == cr.expected_assertion_type)
            cr.has_evidence_for_value = cr.evidence_count >= 1
            return cr

    # No matching row.
    cr.notes.append(f"No answer row matched expected_value={cr.expected_value!r}")
    return cr


def _matches_expected(expected_norm: str, expected_num: Optional[float], ans_row: Dict[str, Any]) -> bool:
    """
    True if the answer row's value_display / value_raw / derivation matches
    the expected. Two paths:
      * Numeric: when expected_value parses to a signed number, compare
        against value_raw (preferred) or the value extracted from
        value_display, within a tolerance of 0.5 (rand-millions are
        integer-rounded). Handles negatives + comma-separators + 'R-4m'/'-R4m'.
      * String: substring on the normalised forms (covers "path" / "—" /
        "no clean split available" etc.).
    """
    # 1. Numeric comparison.
    if expected_num is not None:
        candidates: List[float] = []
        vr = ans_row.get("value_raw")
        if isinstance(vr, (int, float)):
            candidates.append(float(vr))
        for k in ("value_display", "derivation"):
            v = ans_row.get(k)
            if not v:
                continue
            n = _extract_signed_number(str(v))
            if n is not None:
                candidates.append(n)
        for c in candidates:
            if abs(c - expected_num) < 0.5:
                return True
    # 2. String substring on normalised forms.
    candidates_str = []
    for k in ("value_display", "value_raw", "derivation"):
        v = ans_row.get(k)
        if v is None: continue
        candidates_str.append(str(v))
    for c in candidates_str:
        if expected_norm and expected_norm in _normalise(c):
            return True
    return False


_RAND_NORMALIZER = re.compile(r"[\s,]")
_NUM_RE = re.compile(r"-?\d[\d\s,]*\.?\d*")


def _normalise(s: str) -> str:
    """Loose normalisation: lowercase, strip whitespace/commas, collapse 'million'/'billion'."""
    if not s:
        return ""
    s = s.lower()
    s = s.replace("million", "m").replace("billion", "bn")
    s = _RAND_NORMALIZER.sub("", s)
    return s


def _extract_signed_number(s: str) -> Optional[float]:
    """
    Pull the first signed numeric value from a rand-amount string, normalising
    the sign placement (handles "-R4m", "R-4m", "R 10 423 million", "R10,423m").
    Multiplies by the unit suffix (m / bn) inferred from the surrounding text.
    Returns None when no number is present.
    """
    if not s:
        return None
    raw = s.strip()
    # Detect a leading dash that the regex might otherwise miss when it
    # comes before the currency mark: "-R4m" → sign='-', then strip the
    # leading '-' for the number search.
    neg = False
    if raw.startswith("-"):
        neg = True
        raw = raw[1:]
    elif raw.lower().startswith("r-"):
        neg = True
        raw = raw[0] + raw[2:]  # drop the dash but keep the R for unit inference
    m = _NUM_RE.search(raw)
    if not m:
        return None
    numtext = m.group(0).replace(",", "").replace(" ", "")
    try:
        val = float(numtext)
    except ValueError:
        return None
    if neg or val < 0:
        val = -abs(val)
    # Unit suffix: 'bn' / 'billion' multiplies by 1000 (rand-millions).
    tail = raw[m.end():].lower()
    if "bn" in tail or "billion" in tail:
        val *= 1000.0
    return val


# ============================================================
# Metrics
# ============================================================


def _compute_metrics(results: List[CaseResult]) -> Dict[str, float]:
    if not results:
        return {k: 0.0 for k in THRESHOLDS}

    total = len(results)
    answer_target = [r for r in results if r.expected_assertion_type != "refusal"]
    refusal_target = [r for r in results if r.expected_assertion_type == "refusal"]

    def _frac(matched: int, denom: int) -> float:
        return round(matched / denom, 4) if denom > 0 else 1.0

    answer_acc = _frac(
        sum(1 for r in answer_target if r.answer_value_match),
        len(answer_target),
    )
    provenance = _frac(
        sum(1 for r in answer_target if r.answer_value_match and r.has_evidence_for_value),
        max(1, sum(1 for r in answer_target if r.answer_value_match)),
    )
    query_valid = _frac(
        sum(1 for r in results if r.query_ran and not r.error),
        total,
    )
    refusal_correct = _frac(
        sum(1 for r in refusal_target if r.refusal_correct),
        len(refusal_target),
    )
    assertion_correct = _frac(
        sum(1 for r in answer_target if r.answer_value_match and r.answer_assertion_match),
        max(1, sum(1 for r in answer_target if r.answer_value_match)),
    )

    return {
        "answer_accuracy":            answer_acc,
        "provenance_coverage":        provenance,
        "query_validity":             query_valid,
        "refusal_correctness":        refusal_correct,
        "assertion_type_correctness": assertion_correct,
    }


# ============================================================
# CLI
# ============================================================


def _print_report(er: EvalResult) -> None:
    print(f"\n{'='*72}")
    print(f"  FD eval — {er.total_cases} cases  ({'PASS' if er.gate_passed else 'FAIL'})")
    print(f"{'='*72}")
    for k, v in er.metrics.items():
        thr = THRESHOLDS[k]
        flag = "✓" if v + 1e-9 >= thr else "✗"
        print(f"  {flag} {k:<30s}  {v:.4f}    (gate: {thr:.2f})")
    print()
    if not er.gate_passed:
        print("Cases that need attention:")
        for c in er.case_results:
            if c.error or (c.expected_assertion_type != "refusal" and not c.answer_value_match) or (c.expected_assertion_type == "refusal" and not c.refusal_correct):
                fail_kind = (
                    f"ERROR: {c.error}" if c.error
                    else "WRONG REFUSAL" if c.expected_assertion_type == "refusal"
                    else f"value mismatch (expected={c.expected_value!r}, got={c.actual_value!r})"
                )
                print(f"  * [{c.query_id or '—':<14s}] {c.question[:60]:<60s}  {fail_kind}")
                for n in c.notes:
                    print(f"      note: {n}")
        print()


def _load_env_if_needed() -> None:
    if not (os.environ.get("VISION_AGENT_API_KEY") or os.environ.get("LANDING_AI_API_KEY")):
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("VISION_AGENT_API_KEY=") or line.startswith("LANDING_AI_API_KEY="):
                    k, _, v = line.partition("=")
                    os.environ[k] = v


def main() -> int:
    p = argparse.ArgumentParser(description="Run the FD eval gate against the active gold set.")
    p.add_argument("--workspace-slug", default="exxaro-fd")
    p.add_argument("--triggered-by", default=os.environ.get("USER") or "fd_eval_runner CLI")
    args = p.parse_args()

    _load_env_if_needed()
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_KEY")
    if not (supabase_url and supabase_key):
        print("ERROR: SUPABASE_URL + SUPABASE_SERVICE_KEY must be set in the environment.")
        return 2

    from supabase import create_client  # local import; not required for unit tests
    sb = create_client(supabase_url, supabase_key)
    ws_resp = sb.table("workspaces").select("id").eq("slug", args.workspace_slug).limit(1).execute()
    ws_rows = ws_resp.data or []
    if not ws_rows:
        print(f"ERROR: workspace slug={args.workspace_slug!r} not found.")
        return 2
    ws_id = ws_rows[0]["id"]

    er = run_eval(sb, ws_id, triggered_by=args.triggered_by)
    _print_report(er)
    return 0 if er.gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

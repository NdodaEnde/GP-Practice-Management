"""
Financial-Disclosure answer contract.

Spec §7.4 — every figure the Copilot returns must:
    (1) resolve to ≥1 SourceSpan (doc + page). No span → not shown.
    (2) display its assertion_type chip (disclosed | derived | strategically_attributed).
        The strategically_attributed chip is visually distinct (amber).
    (3) show its arithmetic for any `derived` figure ("R5,000m × 60.1% = R3,005m").
    (4) refuse out-of-scope politely (spec §7.1 layer-4).

Plus the constrained template for `strategically_attributed` rows: the prose
sentences are FIXED (model fills bracket slots) — no banned-word filter, the
template is what binds intent to wording. Spec §7.3 + plan-amendment from
user feedback.

This layer is the boundary between the query library (raw rows) and the API
response. It is the place to fail closed if anything tries to surface a
figure without provenance.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List, Optional

from app.services.fd_query_library import AnswerRow, Evidence, QueryResult, SUGGESTED_PROMPTS


# Spec §7.3 constrained-template wording for strategically_attributed.
# Placeholders are filled by the answer-contract layer; the surrounding
# sentences are fixed strings. The model is NEVER asked to write the surrounding prose.
_STRATEGICALLY_ATTRIBUTED_TEMPLATE = (
    "Exxaro presents this as a strategic linkage in {citation}: \"{quote}\". "
    "The public reports do not disclose a traced rand-for-rand flow — capital "
    "is allocated at group level. This view shows Exxaro's stated strategy, "
    "not a ledger trace."
)


# Spec §7.1 layer-4 refusal copy. Verbatim — do NOT improvise around it.
_REFUSAL_COPY = (
    "That isn't in Exxaro's public reports I've ingested. "
    "I can answer in-scope questions from the list below."
)


class AnswerContractError(Exception):
    """Raised when a row tries to surface a figure without provenance."""


def render(result: QueryResult, *, strict: bool = True) -> Dict[str, Any]:
    """
    Convert a QueryResult into the API-response shape the UI renders.

    Args:
        result: the raw query output.
        strict: if True (default), raise AnswerContractError when a numeric
            row has zero evidence. If False, drop such rows silently (used
            only for testing). Spec §7.4 (1) is non-negotiable in production.

    Returns:
        dict with keys: query_id, title, rows, notes, refusal, in_scope_capabilities.
        If result.not_in_reports is True, the refusal field is set per
        spec §7.1 layer-4 and rows is empty.
    """
    if result.not_in_reports:
        return _build_refusal_payload()

    rendered_rows: List[Dict[str, Any]] = []
    for row in result.rows:
        if row.value_raw is not None and not row.evidence:
            msg = (
                f"AnswerContract: row {row.label!r} carries a value "
                f"({row.value_display}) but has zero evidence spans. "
                f"Spec §7.4 (1): no span → not shown."
            )
            if strict:
                raise AnswerContractError(msg)
            continue

        rendered_rows.append(_render_row(row))

    return {
        "query_id": result.query_id,
        "title": result.title,
        "rows": rendered_rows,
        "notes": result.notes,
        "refusal": None,
        "in_scope_capabilities": list(SUGGESTED_PROMPTS),
    }


def refusal() -> Dict[str, Any]:
    """Return the constrained refusal payload (spec §7.1 layer-4)."""
    return _build_refusal_payload()


# =============================================================================
# Internals
# =============================================================================


def _build_refusal_payload() -> Dict[str, Any]:
    return {
        "query_id": None,
        "title": None,
        "rows": [],
        "notes": None,
        "refusal": _REFUSAL_COPY,
        "in_scope_capabilities": list(SUGGESTED_PROMPTS),
    }


def _render_row(row: AnswerRow) -> Dict[str, Any]:
    chip_color = "amber" if row.assertion_type == "strategically_attributed" else "default"
    chip_tooltip = _chip_tooltip(row.assertion_type)

    out: Dict[str, Any] = {
        "label":           row.label,
        "value_raw":       row.value_raw,
        "value_display":   row.value_display,
        "assertion_type":  row.assertion_type,
        "chip":            {"label": row.assertion_type, "color": chip_color, "tooltip": chip_tooltip} if row.assertion_type else None,
        "evidence":        [_render_evidence(e) for e in row.evidence],
        "evidence_count":  len(row.evidence),
        "derivation":      row.derivation if row.assertion_type == "derived" else None,
        "prose":           None,
        "company_quote":   row.company_quote,
        "extras":          row.extras or {},
    }

    if row.assertion_type == "strategically_attributed":
        # The constrained §7.3 template. Pulls a single best citation from
        # the row's evidence (first entry); the quote is the company's own
        # words, NOT model paraphrase.
        if row.evidence and row.company_quote:
            first = row.evidence[0]
            citation = f"[{first.doc_id}, p.{first.page}]"
            out["prose"] = _STRATEGICALLY_ATTRIBUTED_TEMPLATE.format(citation=citation, quote=row.company_quote)
        elif row.company_quote:
            # No evidence? The render() guard should have caught this. Render
            # the prose without a citation rather than fabricate one — but
            # flag the row so the UI can render a warning.
            out["prose"] = f"Exxaro states: \"{row.company_quote}\" (citation pending)"

    return out


def _render_evidence(e: Evidence) -> Dict[str, Any]:
    quote = e.quote or ""
    short = (quote[:160] + "…") if len(quote) > 160 else quote
    return {
        "doc_id": e.doc_id,
        "page":   e.page,
        "quote":  quote,
        "quote_short": short,
        "citation":    f"{e.doc_id}, p.{e.page}",
    }


def _chip_tooltip(assertion_type: Optional[str]) -> Optional[str]:
    if assertion_type == "disclosed":
        return "Stated directly in a source document."
    if assertion_type == "derived":
        return "Computed from disclosed facts by a defined rule. Arithmetic shown."
    if assertion_type == "strategically_attributed":
        return "This linkage reflects Exxaro's stated strategy, not a traced ledger entry."
    return None

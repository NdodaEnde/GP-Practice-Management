"""
Financial-Disclosure parameterised query library.

Spec §7.2: the six hand-written queries the Copilot's suggested prompts map to.
Each function pulls data from fd_* tables and returns a QueryResult — a typed
object the answer-contract layer converts into the user-facing response shape
(spec §7.4: value + assertion_type chip + evidence + derivation).

The functions in this module are the *only* path to numeric answers in the MVP.
spec §7.1 layered resolution:
    Layer 1  — suggested-prompt buttons hit these functions by name → 0 risk
    Layer 2  — open question → intent classifier → nearest match (Q1..Q-DELTA)
    Layer 3  — grounded retrieval (step 6, pgvector — not yet built)
    Layer 4  — refusal: out-of-scope copy from spec §7.1

The library deliberately does NOT touch the LLM. It's pure data assembly; the
answer-contract layer handles user-facing wording (including the constrained
template for `strategically_attributed`).

Honesty rules embedded in this module:
    * Q1 (ownership-weighted FCF) returns assertion_type='derived' with a
      visible derivation string ("R5,000m × 60.1% = R3,005m"), per spec
      §7.4 (3) — no black-box "Attributable revenue: R4,207m".
    * Q3 (funding path) marks every ALLOCATED_TO / FINANCES edge with its
      stored assertion_type. For Coal Asset → CapitalFund or CapitalFund →
      diversification-asset edges the stamp is 'strategically_attributed';
      the answer contract renders the spec §7.3 template for those rows.
    * Q4 (split) returns numerator/denominator separately so the percentage
      is visibly *derived*, not stated.
    * Q-COMPLIANCE returns "none found" honestly when the public record has
      no expansion-capital-into-coal edge — that is itself a correct answer.

Every function takes (supabase, workspace_id, ...params) and returns a
QueryResult. Errors propagate as exceptions; callers wrap them into HTTP
responses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Public dataclasses
# =============================================================================


@dataclass(frozen=True)
class Evidence:
    """A single grounded source span for one answer row."""

    doc_id: str
    page: int
    quote: str  # truncated for display by the answer-contract layer


@dataclass(frozen=True)
class AnswerRow:
    """One row of a query answer — what shows up on a line in the Copilot UI."""

    label: str                                          # 'Grootegeluk Coal Mine', 'Future Minerals', etc.
    value_raw: Optional[float]                          # numeric value (None for non-numeric rows)
    value_display: str                                  # 'R4,207m', '42%', '—', 'restated'
    assertion_type: Optional[str]                       # 'disclosed' | 'derived' | 'strategically_attributed' | None
    evidence: List[Evidence] = field(default_factory=list)
    derivation: Optional[str] = None                    # visible arithmetic for derived figures
    company_quote: Optional[str] = None                 # for strategically_attributed rows
    extras: Dict[str, Any] = field(default_factory=dict)  # query-specific extras (e.g. 'change_type': 'restated')


@dataclass
class QueryResult:
    """Aggregate output of one parameterised query."""

    query_id: str                                       # 'Q1' | 'Q2' | 'Q3' | 'Q4' | 'Q_COMPLIANCE' | 'Q_DELTA'
    title: str                                          # human-readable
    rows: List[AnswerRow]
    notes: Optional[str] = None
    not_in_reports: bool = False                        # set True when no relevant data — UI signals refusal


# =============================================================================
# Catalog — used by the intent classifier in fd_endpoints.py
# =============================================================================


SUGGESTED_PROMPTS: Tuple[Dict[str, str], ...] = (
    {"query_id": "Q1",            "label": "Which coal assets generated the most cash?", "params_doc": "fiscal_year (int)"},
    {"query_id": "Q2",            "label": "Which renewable / future-mineral projects received funding?", "params_doc": "(none)"},
    {"query_id": "Q3",            "label": "Show the funding path from Grootegeluk to Cennergi.", "params_doc": "source_asset_id (default GROOT-001), dst_org_id (default CENNERGI-001)"},
    {"query_id": "Q4",            "label": "What share of diversification capital went into manganese?", "params_doc": "(none)"},
    {"query_id": "Q_COMPLIANCE",  "label": "Any expansion capital touching a coal asset?", "params_doc": "(none)"},
    {"query_id": "Q_DELTA",       "label": "What changed between two reporting years?", "params_doc": "prev (int), curr (int)"},
)


# =============================================================================
# Q1 — Coal assets ranked by attributable FCF (ownership-weighted)
# =============================================================================


def Q1_coal_assets_by_attributable_fcf(
    supabase: Any,
    workspace_id: str,
    fiscal_year: int,
) -> QueryResult:
    """
    Top coal assets by ownership-weighted free cash flow for one fiscal year.

    For each Coal asset:
        attributable_fcf = reported_fcf × Exxaro.OWNS(effective_pct, default 1.0)
        assertion_type   = 'derived'
        derivation       = "Rxxx m × yy.y% = Rxxx m"
        evidence         = source spans of the FinancialFact + the OWNS edge

    Spec §7.2 Q1 + §6.2 attributable rollup + §7.4 (3) visible arithmetic.
    """
    rows: List[AnswerRow] = []

    # 1. All Coal assets in this workspace.
    assets_resp = (
        supabase.table("fd_assets")
        .select("canonical_id,name")
        .eq("workspace_id", workspace_id)
        .eq("commodity", "Coal")
        .execute()
    )
    for asset in getattr(assets_resp, "data", None) or []:
        asset_cid: str = asset["canonical_id"]
        asset_name: str = asset["name"]

        # 2. FCF FinancialFact for this asset + fiscal_year, status='active'.
        ff_id = f"{asset_cid}-FCF-{fiscal_year}"
        ff_resp = (
            supabase.table("fd_financial_facts")
            .select("value_zar_m,status,basis")
            .eq("workspace_id", workspace_id)
            .eq("canonical_id", ff_id)
            .limit(1)
            .execute()
        )
        ff_rows = getattr(ff_resp, "data", None) or []
        if not ff_rows or ff_rows[0]["status"] != "active":
            continue
        reported_fcf = float(ff_rows[0]["value_zar_m"])

        # 3. Ownership: Exxaro -OWNS-> asset_cid (effective_pct). Default 1.0.
        owns_resp = (
            supabase.table("fd_edges")
            .select("payload")
            .eq("workspace_id", workspace_id)
            .eq("dst_canonical_id", asset_cid)
            .eq("relation", "OWNS")
            .limit(1)
            .execute()
        )
        owns_rows = getattr(owns_resp, "data", None) or []
        effective_pct = 1.0
        owns_evidence_spans: List[Evidence] = []
        if owns_rows:
            payload = owns_rows[0].get("payload") or {}
            effective_pct = float(payload.get("effective_pct") or 1.0)
            owns_evidence_spans = _fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source="EXXARO-001", relation="EVIDENCED_BY")

        attributable = reported_fcf * effective_pct

        # 4. Evidence on the FinancialFact itself.
        ff_evidence_spans = _fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source=ff_id, relation="EVIDENCED_BY")

        # 5. Build the visible derivation only when effective_pct < 1 (else arithmetic is trivial).
        if effective_pct < 1.0:
            derivation = f"R{reported_fcf:,.0f}m × {effective_pct*100:.1f}% = R{attributable:,.0f}m"
        else:
            derivation = None

        rows.append(
            AnswerRow(
                label=asset_name,
                value_raw=attributable,
                value_display=f"R{attributable:,.0f}m",
                assertion_type="derived" if effective_pct < 1.0 else "disclosed",
                evidence=_dedupe_evidence(ff_evidence_spans + owns_evidence_spans),
                derivation=derivation,
                extras={"reported_fcf_zar_m": reported_fcf, "effective_pct": effective_pct, "fiscal_year": fiscal_year},
            )
        )

    rows.sort(key=lambda r: (r.value_raw or 0), reverse=True)
    return QueryResult(
        query_id="Q1",
        title=f"Coal assets by attributable free cash flow, FY{fiscal_year}",
        rows=rows,
        notes="Attributable = reported FCF × effective ownership. Derived from disclosed figures (spec §6.2).",
        not_in_reports=(len(rows) == 0),
    )


# =============================================================================
# Q2 — Renewable / future-mineral projects that received funding
# =============================================================================


def Q2_renewable_or_future_mineral_funding(
    supabase: Any,
    workspace_id: str,
) -> QueryResult:
    """
    Outgoing FINANCES edges from the Diversification fund — projects in the
    renewable / manganese space. assertion_type is read off the edge (the
    mapper stamped it at write time — see fd_ontology_mapper._stamp_assertion_type).
    """
    rows: List[AnswerRow] = []

    # Diversification-fund FINANCES edges.
    fund_id = "FUND-DIVERSIFICATION-001"
    edges_resp = (
        supabase.table("fd_edges")
        .select("dst_canonical_id,dst_type,payload,assertion_type")
        .eq("workspace_id", workspace_id)
        .eq("src_canonical_id", fund_id)
        .eq("relation", "FINANCES")
        .execute()
    )
    for edge in getattr(edges_resp, "data", None) or []:
        dst_cid = edge["dst_canonical_id"]
        dst_type = edge["dst_type"]
        payload = edge.get("payload") or {}
        amount_zar_m = payload.get("amount_zar_m")
        company_quote = payload.get("company_quote")

        dst_name = _resolve_label_for(supabase, workspace_id, dst_cid, dst_type)

        evidence = _fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source=fund_id)
        if dst_cid:
            evidence += _fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source=dst_cid)

        rows.append(
            AnswerRow(
                label=dst_name or dst_cid,
                value_raw=float(amount_zar_m) if amount_zar_m is not None else None,
                value_display=(f"R{float(amount_zar_m):,.0f}m" if amount_zar_m is not None else "—"),
                assertion_type=edge.get("assertion_type"),
                evidence=_dedupe_evidence(evidence),
                company_quote=company_quote,
                extras={"dst_canonical_id": dst_cid, "dst_type": dst_type},
            )
        )

    rows.sort(key=lambda r: (r.value_raw or 0), reverse=True)
    return QueryResult(
        query_id="Q2",
        title="Renewable / future-minerals destinations of diversification capital",
        rows=rows,
        not_in_reports=(len(rows) == 0),
    )


# =============================================================================
# Q3 — Funding path from a source asset to a destination (honestly stamped)
# =============================================================================


def Q3_funding_path(
    supabase: Any,
    workspace_id: str,
    source_asset_id: str = "GROOT-001",
    destination_id: str = "CENNERGI-001",
) -> QueryResult:
    """
    Trace edges Asset -[GENERATES]-> FinancialFact -[ALLOCATED_TO]-> CapitalFund
    -[FINANCES]-> destination. Each ALLOCATED_TO / FINANCES edge carries its
    assertion_type from the write boundary (spec §3.3); the answer-contract
    layer renders the §7.3 wording for any 'strategically_attributed' link.

    Returns rows in path order: source → ff → fund → destination. The UI
    animates them as the funding path (spec §7.5 Demo 1).
    """
    rows: List[AnswerRow] = []

    # Pull all candidate paths via three separate queries.
    gen_resp = (
        supabase.table("fd_edges")
        .select("dst_canonical_id,payload")
        .eq("workspace_id", workspace_id)
        .eq("src_canonical_id", source_asset_id)
        .eq("relation", "GENERATES")
        .execute()
    )
    candidate_ff_ids: List[str] = [e["dst_canonical_id"] for e in getattr(gen_resp, "data", None) or []]

    for ff_id in candidate_ff_ids:
        # ALLOCATED_TO from FinancialFact -> CapitalFund
        alloc_resp = (
            supabase.table("fd_edges")
            .select("dst_canonical_id,payload,assertion_type")
            .eq("workspace_id", workspace_id)
            .eq("src_canonical_id", ff_id)
            .eq("relation", "ALLOCATED_TO")
            .execute()
        )
        # Also catch the ALLOCATED_TO that originates directly from the Asset
        # (the StrategicNarrative pattern from the mapper)
        alloc_from_asset_resp = (
            supabase.table("fd_edges")
            .select("dst_canonical_id,payload,assertion_type")
            .eq("workspace_id", workspace_id)
            .eq("src_canonical_id", source_asset_id)
            .eq("relation", "ALLOCATED_TO")
            .execute()
        )
        alloc_rows = (getattr(alloc_resp, "data", None) or []) + (getattr(alloc_from_asset_resp, "data", None) or [])

        for alloc in alloc_rows:
            fund_id = alloc["dst_canonical_id"]
            # FINANCES from CapitalFund -> destination
            fin_resp = (
                supabase.table("fd_edges")
                .select("dst_canonical_id,dst_type,payload,assertion_type")
                .eq("workspace_id", workspace_id)
                .eq("src_canonical_id", fund_id)
                .eq("relation", "FINANCES")
                .execute()
            )
            for fin in getattr(fin_resp, "data", None) or []:
                dst_cid = fin["dst_canonical_id"]
                if not _matches_destination(supabase, workspace_id, dst_cid, fin["dst_type"], destination_id):
                    continue
                # Each path produces one row.
                source_label = _resolve_label_for(supabase, workspace_id, source_asset_id, "Asset")
                fund_label = _resolve_label_for(supabase, workspace_id, fund_id, "CapitalFund")
                dst_label = _resolve_label_for(supabase, workspace_id, dst_cid, fin["dst_type"])

                alloc_quote = (alloc.get("payload") or {}).get("company_quote")
                fin_quote = (fin.get("payload") or {}).get("company_quote")
                alloc_assertion = alloc.get("assertion_type")
                fin_assertion = fin.get("assertion_type")

                # Worst-case (most cautious) assertion_type drives the row's chip.
                row_assertion = "strategically_attributed" if "strategically_attributed" in (alloc_assertion, fin_assertion) else "disclosed"

                evidence = _dedupe_evidence(
                    _fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source=source_asset_id)
                    + _fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source=fund_id)
                    + _fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source=dst_cid)
                )

                rows.append(
                    AnswerRow(
                        label=f"{source_label} → {fund_label} → {dst_label}",
                        value_raw=None,
                        value_display="path",
                        assertion_type=row_assertion,
                        evidence=evidence,
                        company_quote=alloc_quote or fin_quote,
                        extras={
                            "source_asset_id": source_asset_id,
                            "fund_id": fund_id,
                            "destination_id": dst_cid,
                            "alloc_assertion": alloc_assertion,
                            "fin_assertion": fin_assertion,
                        },
                    )
                )

    return QueryResult(
        query_id="Q3",
        title=f"Funding path from {source_asset_id} to {destination_id}",
        rows=rows,
        notes="If any link is strategically_attributed, the path reflects Exxaro's stated strategy, not a traced ledger flow (spec §3.3, §7.3).",
        not_in_reports=(len(rows) == 0),
    )


# =============================================================================
# Q4 — Diversification capital split: manganese vs renewables (derived)
# =============================================================================


def Q4_diversification_split(supabase: Any, workspace_id: str) -> QueryResult:
    """
    Of the diversification capital we can identify in the public reports,
    how much went to manganese vs renewables? Returns numerator + denominator
    + percentage as a derived figure with visible arithmetic.
    """
    fund_id = "FUND-DIVERSIFICATION-001"
    edges_resp = (
        supabase.table("fd_edges")
        .select("dst_canonical_id,dst_type,payload,assertion_type")
        .eq("workspace_id", workspace_id)
        .eq("src_canonical_id", fund_id)
        .eq("relation", "FINANCES")
        .execute()
    )
    edges = getattr(edges_resp, "data", None) or []

    manganese = 0.0
    renewables = 0.0
    other = 0.0
    sources_seen: List[str] = []
    for e in edges:
        amount = float((e.get("payload") or {}).get("amount_zar_m") or 0.0)
        if amount <= 0:
            continue
        dst_cid = e["dst_canonical_id"]
        sources_seen.append(dst_cid)
        # Look up dst commodity / type
        if e["dst_type"] == "Asset":
            asset_resp = (
                supabase.table("fd_assets")
                .select("commodity,name")
                .eq("workspace_id", workspace_id)
                .eq("canonical_id", dst_cid)
                .limit(1)
                .execute()
            )
            commodity = (getattr(asset_resp, "data", None) or [{}])[0].get("commodity") or "Other"
            if commodity == "Manganese":
                manganese += amount
            elif commodity == "Renewable":
                renewables += amount
            else:
                other += amount
        elif e["dst_type"] == "Acquisition":
            # Manganese acquisition by canonical-id convention (look for 'MN' or 'MANGANESE')
            up = dst_cid.upper()
            if "MN" in up or "MANGANESE" in up:
                manganese += amount
            else:
                other += amount
        else:
            other += amount

    total = manganese + renewables + other
    if total <= 0:
        return QueryResult(
            query_id="Q4",
            title="Diversification capital split — manganese vs renewables",
            rows=[],
            notes="The ingested reports don't disclose enough diversification-fund FINANCES edges to compute a split.",
            not_in_reports=True,
        )

    pct_mn = round(100 * manganese / total)
    pct_re = round(100 * renewables / total)

    evidence = _dedupe_evidence(
        _fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source=fund_id)
    )

    derivation = (
        f"Of R{total:,.0f}m diversification capital we can identify: "
        f"R{manganese:,.0f}m to manganese + R{renewables:,.0f}m to renewables"
        + (f" + R{other:,.0f}m to other" if other > 0 else "")
    )

    rows = [
        AnswerRow(
            label="Manganese",
            value_raw=manganese,
            value_display=f"R{manganese:,.0f}m ({pct_mn}%)",
            assertion_type="derived",
            evidence=evidence,
            derivation=derivation,
            extras={"pct": pct_mn, "total": total, "is_split": True},
        ),
        AnswerRow(
            label="Renewables",
            value_raw=renewables,
            value_display=f"R{renewables:,.0f}m ({pct_re}%)",
            assertion_type="derived",
            evidence=evidence,
            derivation=derivation,
            extras={"pct": pct_re, "total": total, "is_split": True},
        ),
    ]
    return QueryResult(
        query_id="Q4",
        title="Diversification capital split — manganese vs renewables",
        rows=rows,
        notes="Computed from the FINANCES edges we ingested from public reports — not necessarily the company's full internal allocation (spec §7.5 Demo 2).",
    )


# =============================================================================
# Q-COMPLIANCE — Expansion capital touching a coal asset (any?)
# =============================================================================


def Q_COMPLIANCE_expansion_into_coal(supabase: Any, workspace_id: str) -> QueryResult:
    """
    Spec §3.4: 'no Expansion fund FINANCES a Coal asset'. This query looks
    for violations *with provenance* — or returns 'none found in the ingested
    public record' (which is a correct, honest answer; that's the demo).
    """
    edges_resp = (
        supabase.table("fd_edges")
        .select("src_canonical_id,dst_canonical_id,dst_type,payload,assertion_type")
        .eq("workspace_id", workspace_id)
        .eq("relation", "FINANCES")
        .execute()
    )
    rows: List[AnswerRow] = []
    for e in getattr(edges_resp, "data", None) or []:
        # Need both: src is an Expansion fund AND dst is a Coal asset.
        src_fund_resp = (
            supabase.table("fd_capital_funds")
            .select("fund_type,name")
            .eq("workspace_id", workspace_id)
            .eq("canonical_id", e["src_canonical_id"])
            .limit(1)
            .execute()
        )
        src_fund = (getattr(src_fund_resp, "data", None) or [{}])[0]
        if src_fund.get("fund_type") != "Expansion":
            continue
        if e["dst_type"] != "Asset":
            continue
        dst_asset_resp = (
            supabase.table("fd_assets")
            .select("commodity,name")
            .eq("workspace_id", workspace_id)
            .eq("canonical_id", e["dst_canonical_id"])
            .limit(1)
            .execute()
        )
        dst_asset = (getattr(dst_asset_resp, "data", None) or [{}])[0]
        if dst_asset.get("commodity") != "Coal":
            continue

        amount = (e.get("payload") or {}).get("amount_zar_m")
        rows.append(
            AnswerRow(
                label=f"{src_fund.get('name')} → {dst_asset.get('name')}",
                value_raw=float(amount) if amount is not None else None,
                value_display=(f"R{float(amount):,.0f}m" if amount is not None else "—"),
                assertion_type=e.get("assertion_type"),
                evidence=_fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source=e["src_canonical_id"]),
                company_quote=(e.get("payload") or {}).get("company_quote"),
                extras={"violation": True},
            )
        )

    return QueryResult(
        query_id="Q_COMPLIANCE",
        title="Any expansion-fund FINANCES → coal-asset linkage in the public record?",
        rows=rows,
        notes=(
            "None found in the ingested public record."
            if not rows
            else "Violations found — see rows. Each linkage shows the company's own quote (no traced cash flow)."
        ),
        not_in_reports=False,
    )


# =============================================================================
# Q-DELTA — What changed between two reporting years?
# =============================================================================


def Q_DELTA_year_over_year(
    supabase: Any,
    workspace_id: str,
    prev: int,
    curr: int,
) -> QueryResult:
    """
    Surfaces 'new' / 'restated' / 'withdrawn' FinancialFacts between two
    reporting years. Spec §6.1 v0.3 + §7.2 Q-DELTA. Powers spec §7.5 Demo 3.

    A withdrawn metric = present in `prev` but absent and not restated in
    `curr`. The TBox keeps them with status='withdrawn' — never deleted, per
    the audit-trail rule.
    """
    if curr <= prev:
        raise ValueError(f"Q_DELTA: curr ({curr}) must be greater than prev ({prev})")

    rows: List[AnswerRow] = []

    # 1. Current-year facts. For each, decide change_type.
    curr_resp = (
        supabase.table("fd_financial_facts")
        .select("canonical_id,metric,value_zar_m,fiscal_year,status,basis")
        .eq("workspace_id", workspace_id)
        .eq("fiscal_year", curr)
        .execute()
    )
    for ff in getattr(curr_resp, "data", None) or []:
        ff_cid = ff["canonical_id"]
        # Is this a restatement edge target?
        sup_resp = (
            supabase.table("fd_edges")
            .select("dst_canonical_id")
            .eq("workspace_id", workspace_id)
            .eq("src_canonical_id", ff_cid)
            .eq("relation", "SUPERSEDES")
            .limit(1)
            .execute()
        )
        sup_rows = getattr(sup_resp, "data", None) or []
        if sup_rows:
            old_cid = sup_rows[0]["dst_canonical_id"]
            old_resp = (
                supabase.table("fd_financial_facts")
                .select("value_zar_m,fiscal_year")
                .eq("workspace_id", workspace_id)
                .eq("canonical_id", old_cid)
                .limit(1)
                .execute()
            )
            old = (getattr(old_resp, "data", None) or [{}])[0]
            change_type = "restated"
            prior_value = old.get("value_zar_m")
            evidence = _fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source=ff_cid)
            rows.append(
                AnswerRow(
                    label=f"{ff['metric']} (fy{ff['fiscal_year']})",
                    value_raw=float(ff["value_zar_m"]),
                    value_display=f"R{float(ff['value_zar_m']):,.0f}m  (was R{float(prior_value or 0):,.0f}m)",
                    assertion_type="disclosed",
                    evidence=evidence,
                    extras={"change_type": "restated", "prior_value_zar_m": prior_value, "fact_canonical_id": ff_cid},
                )
            )
        else:
            # New if no FinancialFact exists in `prev` for the same metric+subject.
            metric = ff["metric"]
            subj = ff_cid.rsplit("-", 2)[0] if "-" in ff_cid else ""
            prior_id = f"{subj}-{metric}-{prev}"
            prior_resp = (
                supabase.table("fd_financial_facts")
                .select("canonical_id")
                .eq("workspace_id", workspace_id)
                .eq("canonical_id", prior_id)
                .limit(1)
                .execute()
            )
            change_type = "unchanged" if (getattr(prior_resp, "data", None) or []) else "new"
            if change_type == "unchanged":
                continue
            evidence = _fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source=ff_cid)
            rows.append(
                AnswerRow(
                    label=f"{ff['metric']} (fy{ff['fiscal_year']})",
                    value_raw=float(ff["value_zar_m"]),
                    value_display=f"R{float(ff['value_zar_m']):,.0f}m  (new)",
                    assertion_type="disclosed",
                    evidence=evidence,
                    extras={"change_type": "new", "fact_canonical_id": ff_cid},
                )
            )

    # 2. Withdrawn: rows present in prev with status='withdrawn'.
    withdrawn_resp = (
        supabase.table("fd_financial_facts")
        .select("canonical_id,metric,value_zar_m,fiscal_year")
        .eq("workspace_id", workspace_id)
        .eq("fiscal_year", prev)
        .eq("status", "withdrawn")
        .execute()
    )
    for ff in getattr(withdrawn_resp, "data", None) or []:
        rows.append(
            AnswerRow(
                label=f"{ff['metric']} (fy{ff['fiscal_year']}) [withdrawn]",
                value_raw=None,
                value_display=f"R{float(ff['value_zar_m']):,.0f}m  (no longer reported)",
                assertion_type="disclosed",
                evidence=_fetch_evidence_spans(supabase, workspace_id, asset_cid_or_source=ff["canonical_id"]),
                extras={"change_type": "withdrawn", "fact_canonical_id": ff["canonical_id"]},
            )
        )

    summary = f"{sum(1 for r in rows if r.extras.get('change_type') == 'new')} new, " \
              f"{sum(1 for r in rows if r.extras.get('change_type') == 'restated')} restated, " \
              f"{sum(1 for r in rows if r.extras.get('change_type') == 'withdrawn')} withdrawn"
    return QueryResult(
        query_id="Q_DELTA",
        title=f"What changed between FY{prev} and FY{curr}?",
        rows=rows,
        notes=summary,
        not_in_reports=(len(rows) == 0),
    )


# =============================================================================
# Helpers
# =============================================================================


def _fetch_evidence_spans(
    supabase: Any,
    workspace_id: str,
    *,
    asset_cid_or_source: str,
    relation: str = "EVIDENCED_BY",
    limit: int = 5,
) -> List[Evidence]:
    """
    Pull up to `limit` SourceSpan rows linked to `asset_cid_or_source` via
    EVIDENCED_BY edges. Spans are returned in insertion order.
    """
    edges_resp = (
        supabase.table("fd_edges")
        .select("dst_canonical_id")
        .eq("workspace_id", workspace_id)
        .eq("src_canonical_id", asset_cid_or_source)
        .eq("relation", relation)
        .limit(limit)
        .execute()
    )
    span_ids = [e["dst_canonical_id"] for e in getattr(edges_resp, "data", None) or []]
    if not span_ids:
        return []
    spans_resp = (
        supabase.table("fd_source_spans")
        .select("id,doc_id,page,quote")
        .eq("workspace_id", workspace_id)
        .in_("id", span_ids)
        .execute()
    )
    return [
        Evidence(doc_id=s["doc_id"], page=int(s["page"]), quote=s.get("quote") or "")
        for s in getattr(spans_resp, "data", None) or []
    ]


def _dedupe_evidence(evidence: List[Evidence]) -> List[Evidence]:
    """De-duplicate spans by (doc_id, page, quote) while preserving order."""
    seen = set()
    out: List[Evidence] = []
    for e in evidence:
        key = (e.doc_id, e.page, e.quote)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _resolve_label_for(
    supabase: Any,
    workspace_id: str,
    canonical_id: str,
    node_type: str,
) -> Optional[str]:
    """Best-effort: pull a human-readable name from the right node table."""
    table_for_type = {
        "Asset":           "fd_assets",
        "CapitalFund":     "fd_capital_funds",
        "StrategicPillar": "fd_strategic_pillars",
        "Org":             "fd_orgs",
        "Acquisition":     "fd_acquisitions",
    }
    table = table_for_type.get(node_type)
    if not table:
        return canonical_id
    resp = (
        supabase.table(table)
        .select("name")
        .eq("workspace_id", workspace_id)
        .eq("canonical_id", canonical_id)
        .limit(1)
        .execute()
    )
    rows = getattr(resp, "data", None) or []
    if rows and rows[0].get("name"):
        return rows[0]["name"]
    return canonical_id


def _matches_destination(
    supabase: Any,
    workspace_id: str,
    candidate_cid: str,
    candidate_type: str,
    target: str,
) -> bool:
    """
    Q3 destination matching. The caller may pass an exact canonical_id (e.g.
    'CENNERGI-001') OR a relaxed family name (e.g. 'CENNERGI' to also catch
    'CENNERGI-WIND-001' if that ever exists). Match by uppercase prefix.
    """
    if not candidate_cid:
        return False
    if candidate_cid == target:
        return True
    if candidate_cid.upper().startswith(target.upper()):
        return True
    # Also consider: target is the parent of the candidate's `owned_via`.
    if candidate_type == "Asset":
        reg_resp = (
            supabase.table("fd_entity_registry")
            .select("owned_via")
            .eq("workspace_id", workspace_id)
            .eq("canonical_id", candidate_cid)
            .limit(1)
            .execute()
        )
        rows = getattr(reg_resp, "data", None) or []
        if rows and rows[0].get("owned_via") == target:
            return True
    return False


# Query function lookup — used by the intent classifier.
QUERY_DISPATCH = {
    "Q1": Q1_coal_assets_by_attributable_fcf,
    "Q2": Q2_renewable_or_future_mineral_funding,
    "Q3": Q3_funding_path,
    "Q4": Q4_diversification_split,
    "Q_COMPLIANCE": Q_COMPLIANCE_expansion_into_coal,
    "Q_DELTA": Q_DELTA_year_over_year,
}

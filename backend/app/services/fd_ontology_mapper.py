"""
Financial-Disclosure ontology mapper.

Spec §4.4 and §5: turns an ADE extraction result into atomic, evidenced facts
in the fd_* tables. This is where the assertion-type honesty rules live —
enforced at the write boundary, not patched on at the answer layer.

The mapper is deliberately strict:

* Every surface form goes through fd_entity_resolver. Confidence < 0.80 →
  the fact is quarantined to fd_facts_needs_review and the node/edge is NOT
  written. A wrong silent merge is worse than a missing node.

* Every fact node (FinancialFact, ESGFact, etc.) MUST be evidenced by at
  least one SourceSpan. No grounding → no node. fd_processor.py is
  responsible for translating LandingAI extraction_metadata into the
  ``ProvenanceCtx`` shape this module consumes.

* OWNS edges are gated even harder: no SourceSpan → IngestError. The
  effective_pct on an OWNS edge multiplies every downstream "derived"
  rollup, so the multiplier itself must be sourced (spec §6.2 + plan rule).

* Coal-asset → CapitalFund linkages, and CapitalFund → renewable/manganese-asset
  linkages, are stamped ``strategically_attributed`` before insertion — never
  ``disclosed`` (spec §3.3 hard rule). The DB CHECK constraint catches typos;
  this stamping enforces the *intent*.

* All inserts are idempotent: ``INSERT … ON CONFLICT (workspace_id,
  canonical_id) DO UPDATE`` for nodes; ``INSERT … ON CONFLICT
  (workspace_id, src_canonical_id, dst_canonical_id, relation, valid_from)
  DO UPDATE`` for edges. Re-running the mapper against the same ADE output
  is a no-op on the rows it produced.

This module is consumed by fd_processor.py; it does not call LandingAI
itself and has no notion of file paths.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.fd_entity_resolver import (
    CONFIDENCE_GATE,
    quarantine_for_review,
    resolve_surface_form,
)

logger = logging.getLogger(__name__)


# ============================================================
# Public dataclasses — what callers pass in and what we hand back.
# ============================================================


@dataclass(frozen=True)
class Provenance:
    """
    A single grounded source span for one extracted field / fact.

    The mapper deduplicates spans by (workspace_id, doc_id, page, char_start)
    so re-extracting the same fact from the same chunk is a no-op.
    """

    doc_id: str
    page: int
    char_start: int
    char_end: int
    quote: str


# Mapping from a "field path" (e.g. "financial_facts[0].value_zar_m") to the list
# of Provenance entries grounding it. fd_processor.py builds this from
# LandingAI's extraction_metadata before handing to map_and_persist().
ProvenanceCtx = Dict[str, List[Provenance]]


@dataclass
class MapResult:
    """Aggregate result of one mapper run, returned to the caller for logging / UI."""

    nodes_written: Dict[str, int] = field(default_factory=lambda: {
        "fd_orgs": 0,
        "fd_assets": 0,
        "fd_capital_funds": 0,
        "fd_strategic_pillars": 0,
        "fd_financial_facts": 0,
        "fd_esg_facts": 0,
        "fd_acquisitions": 0,
        "fd_source_spans": 0,
    })
    edges_written: Dict[str, int] = field(default_factory=lambda: {
        "GENERATES": 0,
        "OWNS": 0,
        "ALLOCATED_TO": 0,
        "FINANCES": 0,
        "SUPERSEDES": 0,
        "EVIDENCED_BY": 0,
    })
    quarantined: int = 0
    rejected: List[str] = field(default_factory=list)


class IngestError(Exception):
    """Raised when a rule violation cannot be safely quarantined (e.g. an OWNS edge with no provenance)."""


# ============================================================
# Public entry point.
# ============================================================


def map_and_persist(
    supabase: Any,
    *,
    workspace_id: str,
    doc_id: str,
    extraction_dict: Dict[str, Any],
    provenance_ctx: ProvenanceCtx,
) -> MapResult:
    """
    Map a FinancialDisclosureExtraction (already validated, .model_dump()'d)
    into fd_* rows, with provenance and assertion-type stamping.

    Args:
        supabase: a supabase-py client (service-role).
        workspace_id: UUID of the Mining/FD workspace.
        doc_id: stable identifier of the source report — matches
            fd_documents.doc_id and fd_source_spans.doc_id. e.g.
            ``"EXXARO-IR-2024"``.
        extraction_dict: the validated extraction result.
        provenance_ctx: mapping of field-path → list of Provenance entries.
            fd_processor.py is responsible for building this from LandingAI's
            extraction_metadata. The mapper looks up provenance per row via
            field-path keys it constructs at insertion time, e.g.
            ``"financial_facts[3]"``. If a key is missing or its list is
            empty, the corresponding fact is rejected (no span, no node).

    Returns:
        MapResult — counts of what was written, quarantined, and rejected.
    """

    result = MapResult()

    # ---------- 1. Resolve + upsert the entity-style top-level lists ----------
    # These are the *nodes* the FinancialFacts / Acquisitions / etc. will link to.

    org_ids = _upsert_entity_list(
        supabase, workspace_id, extraction_dict.get("orgs", []),
        provenance_ctx, "orgs",
        entity_type="Org",
        table_name="fd_orgs",
        builder=_build_org_row,
        result=result,
    )
    asset_ids = _upsert_entity_list(
        supabase, workspace_id, extraction_dict.get("assets", []),
        provenance_ctx, "assets",
        entity_type="Asset",
        table_name="fd_assets",
        builder=_build_asset_row,
        result=result,
    )
    fund_ids = _upsert_entity_list(
        supabase, workspace_id, extraction_dict.get("capital_funds", []),
        provenance_ctx, "capital_funds",
        entity_type="CapitalFund",
        table_name="fd_capital_funds",
        builder=_build_capital_fund_row,
        result=result,
    )
    pillar_ids = _upsert_entity_list(
        supabase, workspace_id, extraction_dict.get("strategic_pillars", []),
        provenance_ctx, "strategic_pillars",
        entity_type="StrategicPillar",
        table_name="fd_strategic_pillars",
        builder=_build_pillar_row,
        result=result,
    )

    # ---------- 2. Upsert acquisitions (own node class) ----------
    acquisition_ids: List[Optional[str]] = []
    for idx, acq in enumerate(extraction_dict.get("acquisitions", [])):
        field_path = f"acquisitions[{idx}]"
        spans = provenance_ctx.get(field_path, [])
        sf = (acq.get("surface_form") or "").strip()
        if not sf:
            result.rejected.append(f"{field_path}: empty surface_form")
            acquisition_ids.append(None)
            continue
        if not spans:
            result.rejected.append(f"{field_path}: no provenance span")
            acquisition_ids.append(None)
            continue

        resolve_res = resolve_surface_form(supabase, workspace_id, sf, "Acquisition")
        cid: Optional[str]
        if not resolve_res.is_confident:
            # Acquisitions tend to be one-off names; we *create* a canonical_id
            # for unseen ones rather than quarantining them — they're the only
            # entity type where a confident match is the exception, not the
            # norm. Pre-seeded ones (e.g. ACQ-KALAHARI-MN-001) hit the exact
            # branch in the resolver; brand-new ones get a derived canonical_id.
            cid = _derive_acquisition_canonical_id(sf)
        else:
            cid = resolve_res.canonical_id
        _upsert_node(supabase, "fd_acquisitions", _build_acquisition_row(workspace_id, cid, acq), result)
        result.nodes_written["fd_acquisitions"] += 1
        acquisition_ids.append(cid)
        # Attach EVIDENCED_BY edges from the acquisition node.
        for span in spans:
            _attach_evidence(supabase, workspace_id, cid, "Acquisition", span, result, doc_id_for_node=doc_id)

    # ---------- 3. Financial facts (one fd_financial_facts row each, attached to its subject) ----------
    financial_fact_ids: List[Optional[str]] = []
    for idx, ff in enumerate(extraction_dict.get("financial_facts", [])):
        field_path = f"financial_facts[{idx}]"
        spans = provenance_ctx.get(field_path, [])
        subj_sf = (ff.get("subject_surface_form") or "").strip()
        subj_type = ff.get("subject_type")
        metric = ff.get("metric")
        value_zar_m = ff.get("value_zar_m")
        fy = ff.get("fiscal_year")

        if not (subj_sf and subj_type and metric and value_zar_m is not None and fy):
            result.rejected.append(f"{field_path}: missing required field(s)")
            financial_fact_ids.append(None)
            continue
        if not spans:
            result.rejected.append(f"{field_path}: no provenance span — disclosed figures require ≥1 span (spec §5)")
            financial_fact_ids.append(None)
            continue

        subj_resolve = resolve_surface_form(supabase, workspace_id, subj_sf, subj_type)
        if not subj_resolve.is_confident:
            qid = quarantine_for_review(
                supabase, workspace_id,
                raw_surface_form=subj_sf,
                best_match_canonical_id=subj_resolve.canonical_id,
                surface_form_confidence=subj_resolve.confidence,
                ade_output={"field_path": field_path, "row": ff},
                doc_id=doc_id,
                page=spans[0].page if spans else None,
            )
            result.quarantined += 1
            logger.info("Quarantined %s subject %r → fd_facts_needs_review %s", field_path, subj_sf, qid)
            financial_fact_ids.append(None)
            continue

        ff_cid = f"{subj_resolve.canonical_id}-{metric}-{fy}"
        _upsert_node(
            supabase, "fd_financial_facts",
            _build_financial_fact_row(workspace_id, ff_cid, ff),
            result,
        )
        result.nodes_written["fd_financial_facts"] += 1
        financial_fact_ids.append(ff_cid)

        # Evidence edges
        for span in spans:
            _attach_evidence(supabase, workspace_id, ff_cid, "FinancialFact", span, result, doc_id_for_node=doc_id)

        # GENERATES edge: only for asset-subject FCF / EBITDA / Revenue
        if subj_type == "Asset" and metric in {"FCF", "EBITDA", "RevenueGross", "AttributableEBITDA"}:
            _upsert_edge(
                supabase, workspace_id,
                src_canonical_id=subj_resolve.canonical_id, src_type="Asset",
                dst_canonical_id=ff_cid, dst_type="FinancialFact",
                relation="GENERATES",
                payload={"metric": metric, "fiscal_year": fy},
                assertion_type="disclosed",
                valid_from=date(fy, 1, 1),
                result=result,
            )

    # ---------- 4. ESG facts ----------
    for idx, esg in enumerate(extraction_dict.get("esg_facts", [])):
        field_path = f"esg_facts[{idx}]"
        spans = provenance_ctx.get(field_path, [])
        subj_sf = (esg.get("subject_surface_form") or "").strip()
        subj_type = esg.get("subject_type")
        metric = esg.get("metric")
        value = esg.get("value")
        unit = esg.get("unit")
        fy = esg.get("fiscal_year")
        if not (subj_sf and subj_type and metric and value is not None and unit and fy):
            result.rejected.append(f"{field_path}: missing required field(s)")
            continue
        if not spans:
            result.rejected.append(f"{field_path}: no provenance span")
            continue

        subj_resolve = resolve_surface_form(supabase, workspace_id, subj_sf, subj_type)
        if not subj_resolve.is_confident:
            qid = quarantine_for_review(
                supabase, workspace_id,
                raw_surface_form=subj_sf,
                best_match_canonical_id=subj_resolve.canonical_id,
                surface_form_confidence=subj_resolve.confidence,
                ade_output={"field_path": field_path, "row": esg},
                doc_id=doc_id,
                page=spans[0].page,
            )
            result.quarantined += 1
            continue

        esg_cid = f"{subj_resolve.canonical_id}-{metric}-{fy}"
        _upsert_node(
            supabase, "fd_esg_facts",
            _build_esg_fact_row(workspace_id, esg_cid, esg),
            result,
        )
        result.nodes_written["fd_esg_facts"] += 1
        for span in spans:
            _attach_evidence(supabase, workspace_id, esg_cid, "ESGFact", span, result, doc_id_for_node=doc_id)

    # ---------- 5. Ownership facts → OWNS edges (PROVENANCE-GATED) ----------
    for idx, own in enumerate(extraction_dict.get("ownership_facts", [])):
        field_path = f"ownership_facts[{idx}]"
        spans = provenance_ctx.get(field_path, [])
        owner_sf = (own.get("owner_surface_form") or "").strip()
        owned_sf = (own.get("owned_surface_form") or "").strip()
        effective_pct = own.get("effective_pct")

        if not (owner_sf and owned_sf and effective_pct is not None):
            result.rejected.append(f"{field_path}: missing required field(s)")
            continue
        if not spans:
            # Spec §6.2 + plan rule: no source span, no OWNS edge. The
            # effective_pct multiplies every downstream derived rollup — without
            # a sourced multiplier we'd silently fabricate attributable figures.
            #
            # Two failure modes are indistinguishable here: either the fact
            # isn't actually in the report (model hallucination → reject), or
            # the fact IS in the report but ADE didn't emit grounding for it
            # (quarantine, let a human confirm). Quarantine handles both
            # safely: the OWNS edge is NOT written, the surface form lands in
            # needs_review with the unsourced effective_pct in ade_output, and
            # a human can either reject it or supply the missing span.
            qid = quarantine_for_review(
                supabase, workspace_id,
                raw_surface_form=f"{owner_sf} OWNS {owned_sf} ({effective_pct})",
                best_match_canonical_id=None,
                surface_form_confidence=0.0,
                ade_output={
                    "field_path": field_path,
                    "row": own,
                    "reason": "OWNS edge has no grounding span — spec §6.2 refusal",
                },
                doc_id=doc_id,
                page=None,
            )
            result.quarantined += 1
            result.rejected.append(
                f"{field_path}: OWNS {owner_sf!r} → {owned_sf!r} effective_pct={effective_pct} "
                f"quarantined (no source span — spec §6.2)"
            )
            logger.warning(
                "Quarantined unsourced OWNS edge: %s → %s, effective_pct=%s "
                "(needs_review row %s)", owner_sf, owned_sf, effective_pct, qid,
            )
            continue

        owner_resolve = resolve_surface_form(supabase, workspace_id, owner_sf, "Org")
        owned_type = "Asset"  # ownership is usually of an asset; could also be an Org for holding-co stakes
        owned_resolve = resolve_surface_form(supabase, workspace_id, owned_sf, owned_type)
        if not owner_resolve.is_confident:
            owned_resolve_org = resolve_surface_form(supabase, workspace_id, owned_sf, "Org")
            if owned_resolve_org.is_confident:
                # E.g. Exxaro owns Cennergi (the subsidiary) — owned target is Org, not Asset
                owned_resolve = owned_resolve_org
                owned_type = "Org"
        if not (owner_resolve.is_confident and owned_resolve.is_confident):
            qid = quarantine_for_review(
                supabase, workspace_id,
                raw_surface_form=f"{owner_sf} OWNS {owned_sf}",
                best_match_canonical_id=None,
                surface_form_confidence=min(owner_resolve.confidence, owned_resolve.confidence),
                ade_output={"field_path": field_path, "row": own},
                doc_id=doc_id,
                page=spans[0].page,
            )
            result.quarantined += 1
            continue

        # Parse valid_from if available
        vf_raw = own.get("valid_from_raw")
        vf: Optional[date] = _parse_iso_date(vf_raw) if vf_raw else None

        # Insert the OWNS edge with provenance attached as the first span.
        _upsert_edge(
            supabase, workspace_id,
            src_canonical_id=owner_resolve.canonical_id, src_type="Org",
            dst_canonical_id=owned_resolve.canonical_id, dst_type=owned_type,
            relation="OWNS",
            payload={"effective_pct": float(effective_pct)},
            assertion_type=None,  # OWNS is structural, not numeric — no assertion_type
            valid_from=vf,
            result=result,
        )
        # Evidence
        for span in spans:
            _attach_evidence(supabase, workspace_id, owner_resolve.canonical_id, "Org", span, result, doc_id_for_node=doc_id)

    # ---------- 6. Strategic narratives → ALLOCATED_TO / FINANCES edges, stamped strategically_attributed ----------
    for idx, narr in enumerate(extraction_dict.get("strategic_narratives", [])):
        field_path = f"strategic_narratives[{idx}]"
        spans = provenance_ctx.get(field_path, [])
        src_sf = (narr.get("source_surface_form") or "").strip()
        dst_sf = (narr.get("destination_surface_form") or "").strip()
        relation = narr.get("relation")
        quote = (narr.get("company_quote") or "").strip()

        if not (src_sf and dst_sf and relation):
            result.rejected.append(f"{field_path}: missing source/destination/relation")
            continue
        if not quote:
            # Spec §4.4 hard rule: "No quote, no edge."
            result.rejected.append(
                f"{field_path}: refusing strategic-narrative edge from {src_sf!r} → {dst_sf!r} "
                f"without a company_quote (spec §4.4)"
            )
            continue
        if not spans:
            result.rejected.append(f"{field_path}: no provenance span")
            continue

        # Strategic-narrative endpoints are higher-level than the strict §3.2
        # signatures — the company narrates capital flow at the level of
        # pillars ("coal operations → renewable energy") and aggregate
        # framings ("our coal business → energy transition minerals"). The
        # mapper accepts any registry-typed canonical ID on either side; the
        # §3.3 honesty stamping at _stamp_assertion_type ensures the edge's
        # assertion_type still falls under 'strategically_attributed' when
        # the linkage matches the Coal→Diversification or Diversification→
        # renewable/manganese-asset shapes.
        _NARRATIVE_TYPES = ("Asset", "CapitalFund", "StrategicPillar", "Org", "Acquisition")
        src_cid, src_type = _try_resolve_multitype(supabase, workspace_id, src_sf, _NARRATIVE_TYPES)
        dst_cid, dst_type = _try_resolve_multitype(supabase, workspace_id, dst_sf, _NARRATIVE_TYPES)

        if not (src_cid and dst_cid):
            qid = quarantine_for_review(
                supabase, workspace_id,
                raw_surface_form=f"{src_sf} {relation} {dst_sf}",
                best_match_canonical_id=src_cid,
                surface_form_confidence=0.0,
                ade_output={"field_path": field_path, "row": narr},
                doc_id=doc_id,
                page=spans[0].page,
            )
            result.quarantined += 1
            continue

        # Stamp the assertion_type.
        assertion_type = _stamp_assertion_type(supabase, workspace_id, src_cid, src_type, dst_cid, dst_type, relation)

        _upsert_edge(
            supabase, workspace_id,
            src_canonical_id=src_cid, src_type=src_type,
            dst_canonical_id=dst_cid, dst_type=dst_type,
            relation=relation,
            payload={"company_quote": quote},
            assertion_type=assertion_type,
            valid_from=None,
            result=result,
        )
        for span in spans:
            _attach_evidence(supabase, workspace_id, src_cid, src_type, span, result, doc_id_for_node=doc_id)

    # ---------- 7. Restatements → SUPERSEDES edges + status flips ----------
    for idx, rest in enumerate(extraction_dict.get("restatements", [])):
        field_path = f"restatements[{idx}]"
        spans = provenance_ctx.get(field_path, [])
        subj_sf = (rest.get("subject_surface_form") or "").strip()
        metric = rest.get("metric")
        fy = rest.get("fiscal_year")
        new_val = rest.get("restated_value_zar_m")
        if not (subj_sf and metric and fy and new_val is not None):
            result.rejected.append(f"{field_path}: missing required field(s)")
            continue
        if not spans:
            result.rejected.append(f"{field_path}: no provenance span")
            continue
        subj_resolve = resolve_surface_form(supabase, workspace_id, subj_sf, "Asset")
        if not subj_resolve.is_confident:
            subj_resolve = resolve_surface_form(supabase, workspace_id, subj_sf, "StrategicPillar")
        if not subj_resolve.is_confident:
            result.rejected.append(f"{field_path}: could not resolve {subj_sf!r}")
            continue

        old_cid = f"{subj_resolve.canonical_id}-{metric}-{fy}"
        new_cid = f"{old_cid}-R"

        # 1. Mark the old fact 'restated' (if present) — soft update; if it's
        #    not in fd_financial_facts yet, nothing happens.
        supabase.table("fd_financial_facts").update({"status": "restated"}).match({
            "workspace_id": workspace_id, "canonical_id": old_cid,
        }).execute()

        # 2. Upsert the new restated fact as a fresh node, basis='restated'.
        _upsert_node(supabase, "fd_financial_facts", {
            "workspace_id": workspace_id,
            "canonical_id": new_cid,
            "metric": metric,
            "value_zar_m": float(new_val),
            "fiscal_year": int(fy),
            "basis": "restated",
            "status": "active",
        }, result)
        result.nodes_written["fd_financial_facts"] += 1

        # 3. SUPERSEDES edge new → old.
        _upsert_edge(
            supabase, workspace_id,
            src_canonical_id=new_cid, src_type="FinancialFact",
            dst_canonical_id=old_cid, dst_type="FinancialFact",
            relation="SUPERSEDES",
            payload={"reason": rest.get("reason")},
            assertion_type=None,
            valid_from=None,
            result=result,
        )
        for span in spans:
            _attach_evidence(supabase, workspace_id, new_cid, "FinancialFact", span, result, doc_id_for_node=doc_id)

    return result


# ============================================================
# Row builders — each returns the dict the Supabase insert expects.
# ============================================================


def _build_org_row(workspace_id: str, canonical_id: str, src: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "canonical_id": canonical_id,
        "name": src.get("surface_form") or canonical_id,
        "org_type": src.get("org_type"),
    }


def _build_asset_row(workspace_id: str, canonical_id: str, src: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "canonical_id": canonical_id,
        "name": src.get("surface_form") or canonical_id,
        "commodity": src.get("commodity") or "Other",
        "region": src.get("region"),
        "lifecycle": src.get("lifecycle"),
    }


def _build_capital_fund_row(workspace_id: str, canonical_id: str, src: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "canonical_id": canonical_id,
        "name": src.get("surface_form") or canonical_id,
        "fund_type": src.get("fund_type") or "Sustaining",
    }


def _build_pillar_row(workspace_id: str, canonical_id: str, src: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "canonical_id": canonical_id,
        "name": src.get("surface_form") or canonical_id,
    }


def _build_acquisition_row(workspace_id: str, canonical_id: str, src: Dict[str, Any]) -> Dict[str, Any]:
    announced = _parse_iso_date(src.get("announced_date")) if src.get("announced_date") else None
    return {
        "workspace_id": workspace_id,
        "canonical_id": canonical_id,
        "name": src.get("surface_form") or canonical_id,
        "value_zar_m": float(src["value_zar_m"]) if src.get("value_zar_m") is not None else 0.0,
        "announced_date": announced.isoformat() if announced else None,
        "status": src.get("status") or "Announced",
    }


def _build_financial_fact_row(workspace_id: str, canonical_id: str, src: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "canonical_id": canonical_id,
        "metric": src["metric"],
        "value_zar_m": float(src["value_zar_m"]),
        "fiscal_year": int(src["fiscal_year"]),
        "basis": src.get("basis") or "reported",
        "status": "active",
    }


def _build_esg_fact_row(workspace_id: str, canonical_id: str, src: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "canonical_id": canonical_id,
        "metric": src["metric"],
        "value": float(src["value"]),
        "unit": src["unit"],
        "fiscal_year": int(src["fiscal_year"]),
        "site_ref": src.get("site_ref"),
        "status": "active",
    }


# ============================================================
# Shared helpers
# ============================================================


def _upsert_entity_list(
    supabase: Any,
    workspace_id: str,
    items: Iterable[Dict[str, Any]],
    provenance_ctx: ProvenanceCtx,
    path_prefix: str,
    entity_type: str,
    table_name: str,
    builder,
    result: MapResult,
) -> List[Optional[str]]:
    """Resolve + idempotent-upsert a list of same-typed entities. Returns the canonical_ids in order."""
    cids: List[Optional[str]] = []
    for idx, item in enumerate(items):
        field_path = f"{path_prefix}[{idx}]"
        sf = (item.get("surface_form") or "").strip()
        if not sf:
            result.rejected.append(f"{field_path}: empty surface_form")
            cids.append(None)
            continue
        spans = provenance_ctx.get(field_path, [])
        resolve_res = resolve_surface_form(supabase, workspace_id, sf, entity_type)
        if not resolve_res.is_confident:
            qid = quarantine_for_review(
                supabase, workspace_id,
                raw_surface_form=sf,
                best_match_canonical_id=resolve_res.canonical_id,
                surface_form_confidence=resolve_res.confidence,
                ade_output={"field_path": field_path, "row": item},
                doc_id=None,
                page=spans[0].page if spans else None,
            )
            result.quarantined += 1
            cids.append(None)
            continue

        cid = resolve_res.canonical_id
        _upsert_node(supabase, table_name, builder(workspace_id, cid, item), result)
        result.nodes_written[table_name] += 1
        cids.append(cid)
        # Evidence (optional for top-level entities — they're indexed by registry, not the report)
        for span in spans:
            _attach_evidence(supabase, workspace_id, cid, entity_type, span, result, doc_id_for_node=span.doc_id)
    return cids


def _upsert_node(supabase: Any, table_name: str, row: Dict[str, Any], result: MapResult) -> None:
    """Idempotent upsert on (workspace_id, canonical_id)."""
    supabase.table(table_name).upsert(row, on_conflict="workspace_id,canonical_id").execute()


def _upsert_edge(
    supabase: Any,
    workspace_id: str,
    *,
    src_canonical_id: str,
    src_type: str,
    dst_canonical_id: str,
    dst_type: str,
    relation: str,
    payload: Dict[str, Any],
    assertion_type: Optional[str],
    valid_from: Optional[date],
    result: MapResult,
) -> None:
    """
    Idempotent upsert on the natural key
    (workspace_id, src_canonical_id, dst_canonical_id, relation, valid_from).

    Postgres treats NULL ≠ NULL in unique constraints, so the natural UNIQUE
    can't dedupe rows whose valid_from is NULL (EVIDENCED_BY, SUPERSEDES,
    undated linkages). Two prongs of defence:
        (1) DB-level: a partial unique index covering the NULL case (added
            in mining_fd_functions.sql).
        (2) App-level: manual existence-check before INSERT for NULL rows,
            since PostgREST's `on_conflict` parameter only takes column names
            and can't target a partial index's WHERE clause.

    For non-NULL valid_from the SDK upsert path works directly.
    """
    row = {
        "workspace_id": workspace_id,
        "src_canonical_id": src_canonical_id,
        "src_type": src_type,
        "dst_canonical_id": dst_canonical_id,
        "dst_type": dst_type,
        "relation": relation,
        "payload": payload,
        "assertion_type": assertion_type,
        "valid_from": valid_from.isoformat() if valid_from else None,
    }
    if valid_from is None:
        existing = (
            supabase.table("fd_edges")
            .select("id")
            .eq("workspace_id", workspace_id)
            .eq("src_canonical_id", src_canonical_id)
            .eq("dst_canonical_id", dst_canonical_id)
            .eq("relation", relation)
            .is_("valid_from", "null")
            .limit(1)
            .execute()
        )
        if (getattr(existing, "data", None) or []):
            edge_id = existing.data[0]["id"]
            supabase.table("fd_edges").update(
                {"payload": payload, "assertion_type": assertion_type}
            ).eq("id", edge_id).execute()
        else:
            supabase.table("fd_edges").insert(row).execute()
    else:
        supabase.table("fd_edges").upsert(
            row,
            on_conflict="workspace_id,src_canonical_id,dst_canonical_id,relation,valid_from",
        ).execute()
    result.edges_written[relation] += 1


def _attach_evidence(
    supabase: Any,
    workspace_id: str,
    node_canonical_id: str,
    node_type: str,
    span: Provenance,
    result: MapResult,
    *,
    doc_id_for_node: Optional[str] = None,
) -> None:
    """Create / upsert a SourceSpan + EVIDENCED_BY edge pointing at it."""
    quote = span.quote or ""
    content_hash = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    # Upsert the SourceSpan on its natural key (workspace_id, doc_id, page, char_start).
    span_row = {
        "workspace_id": workspace_id,
        "doc_id": span.doc_id,
        "page": span.page,
        "char_start": span.char_start,
        "char_end": span.char_end,
        "quote": quote,
        "content_hash": content_hash,
    }
    upsert = supabase.table("fd_source_spans").upsert(
        span_row,
        on_conflict="workspace_id,doc_id,page,char_start",
    ).execute()
    rows = getattr(upsert, "data", None) or []
    if not rows:
        return
    span_id = rows[0].get("id")
    result.nodes_written["fd_source_spans"] += 1

    _upsert_edge(
        supabase, workspace_id,
        src_canonical_id=node_canonical_id, src_type=node_type,
        dst_canonical_id=str(span_id), dst_type="SourceSpan",
        relation="EVIDENCED_BY",
        payload={},
        assertion_type=None,
        valid_from=None,
        result=result,
    )


def _try_resolve_multitype(
    supabase: Any,
    workspace_id: str,
    surface_form: str,
    candidate_types: Tuple[str, ...],
) -> Tuple[Optional[str], Optional[str]]:
    """Try resolving against each candidate entity_type in order; return the first confident hit."""
    for et in candidate_types:
        r = resolve_surface_form(supabase, workspace_id, surface_form, et)
        if r.is_confident:
            return r.canonical_id, et
    return None, None


def _stamp_assertion_type(
    supabase: Any,
    workspace_id: str,
    src_cid: str,
    src_type: str,
    dst_cid: str,
    dst_type: str,
    relation: str,
) -> str:
    """
    Apply the spec §3.3 honesty rules at the write boundary.

    The narrative endpoints come in at different levels of aggregation
    (Asset, CapitalFund, StrategicPillar, Org), so the rules check identity
    + commodity / fund_type / pillar at each src/dst type. Anything that
    matches the spec's 'coal cash → green / future-minerals' or 'expansion
    capex touching coal' shapes is stamped 'strategically_attributed';
    everything else with a quote falls through to 'disclosed'.

    Rules (in order; first match wins):
        1. Asset(Coal) -[*]→ anything in {CapitalFund/Pillar(Green/Future)/Asset(Renewable/Manganese)}
                                                                → strategically_attributed
        2. StrategicPillar(Coal Ops) -[*]→ anything that's a transition destination
                                                                → strategically_attributed
        3. CapitalFund(Diversification) -[*]→ Asset(Renewable/Manganese)/Pillar(Green/Future)
                                                                → strategically_attributed
        4. CapitalFund(Diversification) -[FINANCES]→ Acquisition → disclosed
           (acquisition value is line-item disclosed; the linkage is the only narrative bit)
        5. CapitalFund(Expansion) -[*]→ Asset(Coal)              → strategically_attributed
           (the Q-COMPLIANCE violation: any expansion capex into coal is, by definition,
            a strategy assertion not a ledger trace)
        6. Otherwise → disclosed (we already required a company_quote at §4.4)
    """
    # The set of destinations that mark "transition" intent — feeding any of
    # these from a Coal source means the company is stating a strategy, not
    # disclosing a traced cash flow.
    GREEN_PILLAR_IDS = {"PILLAR-GREEN-ENERGY-001", "PILLAR-FUTURE-MINERALS-001"}

    def _is_transition_destination(dst_cid: str, dst_type: str) -> bool:
        if dst_type == "StrategicPillar" and dst_cid in GREEN_PILLAR_IDS:
            return True
        if dst_type == "Asset":
            r = supabase.table("fd_assets").select("commodity").match({"workspace_id": workspace_id, "canonical_id": dst_cid}).limit(1).execute()
            rows = getattr(r, "data", None) or []
            return bool(rows) and rows[0].get("commodity") in ("Renewable", "Manganese")
        if dst_type == "Org" and dst_cid == "CENNERGI-001":
            # Cennergi is the renewable subsidiary — narratives that say
            # "coal funds Cennergi" are strategy, never a traced ledger flow.
            return True
        if dst_type == "CapitalFund":
            r = supabase.table("fd_capital_funds").select("fund_type").match({"workspace_id": workspace_id, "canonical_id": dst_cid}).limit(1).execute()
            rows = getattr(r, "data", None) or []
            return bool(rows) and rows[0].get("fund_type") == "Diversification"
        return False

    # 1. Asset(Coal) → transition destination
    if src_type == "Asset":
        r = supabase.table("fd_assets").select("commodity").match({"workspace_id": workspace_id, "canonical_id": src_cid}).limit(1).execute()
        rows = getattr(r, "data", None) or []
        if rows and rows[0].get("commodity") == "Coal" and _is_transition_destination(dst_cid, dst_type):
            return "strategically_attributed"

    # 2. StrategicPillar(Coal Ops) → transition destination
    if src_type == "StrategicPillar" and src_cid == "PILLAR-COAL-OPS-001":
        if _is_transition_destination(dst_cid, dst_type):
            return "strategically_attributed"

    # 3, 4, 5. CapitalFund-rooted narratives
    if src_type == "CapitalFund":
        r = supabase.table("fd_capital_funds").select("fund_type").match({"workspace_id": workspace_id, "canonical_id": src_cid}).limit(1).execute()
        rows = getattr(r, "data", None) or []
        if rows:
            fund_type = rows[0].get("fund_type")
            if fund_type == "Diversification":
                # 3. → renewable/manganese asset, or → Green/Future pillar
                if _is_transition_destination(dst_cid, dst_type) and dst_type in ("Asset", "StrategicPillar", "Org"):
                    return "strategically_attributed"
                # 4. → acquisition is the one place where the linkage is disclosed
                if dst_type == "Acquisition":
                    return "disclosed"
            if fund_type == "Expansion" and dst_type == "Asset":
                r2 = supabase.table("fd_assets").select("commodity").match({"workspace_id": workspace_id, "canonical_id": dst_cid}).limit(1).execute()
                rows2 = getattr(r2, "data", None) or []
                if rows2 and rows2[0].get("commodity") == "Coal":
                    # 5. Q-COMPLIANCE violation shape — any expansion capex into coal
                    return "strategically_attributed"
    # Default
    return "disclosed"


def _derive_acquisition_canonical_id(surface_form: str) -> str:
    """Deterministic, content-stable canonical_id for an acquisition not yet in the registry."""
    h = hashlib.sha256(surface_form.lower().encode("utf-8")).hexdigest()[:10]
    return f"ACQ-AUTO-{h.upper()}"


def _parse_iso_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except (ValueError, TypeError):
        return None

"""
Provenance resolution — the safe/unsafe difference for the query layer.

PR #13 made provenance a *structural contract*: every row carries a
`Provenance` with a `source_document_id` (or is an explicit live_entry).
That guarantees provenance is **present**. It does NOT guarantee it is
**verifiable** — and on the live dev corpus 15 of 24 sourced diagnoses
(62%) carry a `source_document_id` that points at a `digitised_documents`
row that no longer exists. A query that renders those rows
authoritatively with a dead "open source" link beside them is the exact
Phase-3 failure mode: a confident, plausible, wrong-feeling-correct answer
the clinician trusts.

This module closes that gap. `resolve_provenance()` takes a
`QueryResult` and turns every row's opaque `source_document_id` into a
`ResolvedSource` that is one of exactly three honest states:

  - OPENABLE     — the document exists *in this workspace*, a signed URL
                   was minted, the citation names the real scan.
  - UNRESOLVABLE — the id does not resolve to a document in this
                   workspace (missing row, or — structurally — a
                   cross-tenant id the workspace scope correctly refuses).
                   This is rendered *visibly*: an explicit reason and a
                   citation carrying the truncated id, never a blank or a
                   silent dead link.
  - NO_SOURCE    — a live_entry: a fact typed straight into the EHR with
                   no scan. Legitimately sourceless; NOT a failure and
                   NOT counted as unresolvable.

Two invariants are enforced *structurally* (in `__post_init__`), not by
convention, so a future change physically cannot reintroduce the unsafe
shape and the CI test in test_query_layer_invariants.py is asserting a
property the type already guarantees (defence in depth, the same pattern
`Provenance` and the runner use):

  1. **No silent dead link.** `openable` is true IFF a signed URL is
     present. You cannot construct an OPENABLE source without a URL, and
     a non-OPENABLE source cannot carry one.
  2. **Row/aggregate signals cannot drift.** `ResolvedQueryResult`
     refuses to exist unless `unresolvable_count` exactly equals the
     number of UNRESOLVABLE rows. The aggregate is the signal that gets
     read at cohort altitude (a 40-row answer where 25 sources are dead
     is the demo failure; a per-row marker nobody scans does not surface
     it) — so it must never disagree with the rows it summarises.

Tenant scope is part of the correctness mechanism here, not separate
from it: the document lookup is `.eq("workspace_id", workspace_id)`, so a
`source_document_id` that exists only in another practice resolves as
UNRESOLVABLE rather than leaking another tenant's scan. (Corpus produces
0 of the cross-tenant case — every one of the 15 missing ids is missing
globally — so that specific branch is labelled construct-validity-only
and exercised by a fabricated unit test, never claimed as
corpus-demonstrated. Design choice #7.)

Citations are honest: `filename` + `upload_date` (+ page when the
provenance carries one). `doc_type` is 0% populated on the corpus, so a
citation never claims "referral letter" / "lab report" — it does not
fabricate a document class it cannot stand behind.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from ontology.query.result import LIVE_ENTRY, Provenance, QueryResult

# Resolution states.
OPENABLE = "openable"
UNRESOLVABLE = "unresolvable"
NO_SOURCE = "no_source"
_STATES = (OPENABLE, UNRESOLVABLE, NO_SOURCE)

# The Supabase Storage bucket every digitised scan lives in. Same bucket
# the digitisation validation panel signs from (digitisation.py:268) —
# reused verbatim so a query-opened scan and a validation-opened scan are
# the identical object.
_STORAGE_BUCKET = "medical-records"
_SIGNED_URL_TTL_S = 3600


@dataclass(frozen=True)
class ResolvedSource:
    """The verifiable (or honestly-not) form of one row's provenance.

    `status` is one of OPENABLE / UNRESOLVABLE / NO_SOURCE. `openable`
    is derived, never set independently — so the silent-dead-link guard
    cannot be bypassed by setting a flag.
    """

    status: str
    document_id: Optional[str]
    signed_url: Optional[str]
    citation: str
    unresolvable_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in _STATES:
            raise ValueError(
                f"ResolvedSource.status must be one of {_STATES}, "
                f"got {self.status!r}"
            )
        # Invariant 1 — no silent dead link, enforced structurally.
        if self.status == OPENABLE and not self.signed_url:
            raise ValueError(
                "ResolvedSource is OPENABLE but carries no signed_url — "
                "this is exactly the silent dead link the resolver exists "
                "to make impossible"
            )
        if self.status != OPENABLE and self.signed_url:
            raise ValueError(
                f"ResolvedSource is {self.status} but carries a signed_url; "
                f"only OPENABLE sources may"
            )
        if self.status == UNRESOLVABLE and not self.unresolvable_reason:
            raise ValueError(
                "UNRESOLVABLE ResolvedSource must carry an explicit "
                "unresolvable_reason — an unexplained unresolvable is a "
                "blank, which is the unsafe rendering"
            )
        if not self.citation:
            raise ValueError("ResolvedSource must always carry a citation")

    @property
    def openable(self) -> bool:
        return self.status == OPENABLE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "openable": self.openable,
            "document_id": self.document_id,
            "signed_url": self.signed_url,
            "citation": self.citation,
            "unresolvable_reason": self.unresolvable_reason,
        }


@dataclass(frozen=True)
class ResolvedRow:
    """One answer row with its provenance resolved to a ResolvedSource."""

    data: Dict[str, Any]
    provenance: Provenance
    source: ResolvedSource

    def to_dict(self) -> Dict[str, Any]:
        return {
            **self.data,
            "provenance": self.provenance.to_dict(),
            "source": self.source.to_dict(),
        }


@dataclass(frozen=True)
class ResolvedQueryResult:
    """The envelope the HTTP surface returns. Carries the cohort-level
    `unresolvable_count` — the signal that gets read when a clinician
    scans a 40-row cohort and does not read every per-row citation.

    `unresolvable_count` counts UNRESOLVABLE rows ONLY. NO_SOURCE
    (live_entry) rows are `openable == False` but are NOT failures;
    counting them would inflate the dead-link number into its own
    confident-wrong-answer about how broken the sources are.
    """

    template_id: str
    template_version: int
    workspace_id: str
    rows: List[ResolvedRow]
    row_count: int
    data_maturity: str
    unresolvable_count: int

    def __post_init__(self) -> None:
        # Invariant 2 — row/aggregate signals cannot drift. The envelope
        # physically cannot exist if the aggregate disagrees with the
        # rows. PR B's superseded_count will add a sibling assertion here.
        actual = sum(1 for r in self.rows if r.source.status == UNRESOLVABLE)
        if self.unresolvable_count != actual:
            raise ValueError(
                f"unresolvable_count={self.unresolvable_count} disagrees "
                f"with {actual} UNRESOLVABLE rows — the cohort-level and "
                f"row-level safety signals must never drift apart"
            )
        if self.row_count != len(self.rows):
            raise ValueError(
                f"row_count={self.row_count} disagrees with {len(self.rows)} "
                f"rows"
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_version": self.template_version,
            "workspace_id": self.workspace_id,
            "row_count": self.row_count,
            "data_maturity": self.data_maturity,
            "unresolvable_count": self.unresolvable_count,
            "rows": [r.to_dict() for r in self.rows],
        }


def _fmt_date(value: Any) -> Optional[str]:
    """upload_date comes back from PostgREST as an ISO string. Render it
    as a human date ('7 May 2026'). Be tolerant of str / datetime / date
    / None; never raise from citation building."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        dt = value
    else:
        s = str(value).replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            try:
                dt = datetime.fromisoformat(s[:10])
            except ValueError:
                return str(value)[:10] or None
    return f"{dt.day} {dt.strftime('%B %Y')}"


def _citation_for_doc(doc: Dict[str, Any], prov: Provenance) -> str:
    """Honest citation: filename + upload date (+ page if known). No
    doc_type — it is 0% populated on the corpus; a citation must not
    assert a document class it cannot stand behind."""
    filename = doc.get("filename") or "source document"
    when = _fmt_date(doc.get("upload_date") or doc.get("created_at"))
    parts = [filename]
    if when:
        parts.append(when)
    if prov.page is not None:
        parts.append(f"page {prov.page}")
    return ", ".join(parts)


def _short_id(document_id: str) -> str:
    """Last 6 chars — locked decision #3: a truncated id reads as 'the
    system knows precisely which record and is telling me it is gone',
    the honest known-unknown, not a vague system fault."""
    return document_id[-6:]


def _sign(supabase, file_path: Optional[str]) -> Optional[str]:
    """Mint a signed URL, mirroring digitisation.py:268 exactly so a
    query-opened scan is the same object as a validation-opened scan.
    Returns None on any failure — the caller turns None into a *visible*
    UNRESOLVABLE, never a silent dead link."""
    if not file_path:
        return None
    try:
        signed = supabase.storage.from_(_STORAGE_BUCKET).create_signed_url(
            path=file_path,
            expires_in=_SIGNED_URL_TTL_S,
        )
    except Exception:  # noqa: BLE001 — any storage failure ⇒ visible unresolvable
        return None
    if not isinstance(signed, dict):
        return None
    return signed.get("signedURL") or signed.get("signed_url")


def resolve_provenance(
    supabase,
    result: QueryResult,
    *,
    workspace_id: str,
) -> ResolvedQueryResult:
    """Resolve every row's provenance to a ResolvedSource.

    One workspace-scoped batch query against `digitised_documents` (the
    `.eq("workspace_id", workspace_id)` is both the correctness join and
    the tenant scope — a cross-practice id resolves UNRESOLVABLE, never
    leaks). Signed URLs are minted per resolvable doc.

    Never raises on a missing/odd document: the whole point is that the
    unresolvable path is *first-class and visible*, not an exception or a
    blank.
    """
    if not workspace_id:
        # Defence in depth behind the runner (which already refuses an
        # unscoped query): a resolver without a workspace could only
        # produce an unscoped document lookup.
        raise ValueError(
            "resolve_provenance requires a workspace_id from the trusted "
            "caller context; refusing an unscoped document lookup"
        )

    needed = sorted(
        {
            r.provenance.source_document_id
            for r in result.rows
            if r.provenance.source_document_id
            and r.provenance.source_kind != LIVE_ENTRY
        }
    )

    docs: Dict[str, Dict[str, Any]] = {}
    if needed:
        resp = (
            supabase.table("digitised_documents")
            .select("id, filename, file_path, upload_date, created_at")
            .in_("id", needed)
            .eq("workspace_id", workspace_id)  # tenant scope == correctness
            .execute()
        )
        for d in (getattr(resp, "data", None) or []):
            docs[d["id"]] = d

    resolved: List[ResolvedRow] = []
    for row in result.rows:
        prov = row.provenance
        doc_id = prov.source_document_id

        if prov.source_kind == LIVE_ENTRY or not doc_id:
            source = ResolvedSource(
                status=NO_SOURCE,
                document_id=None,
                signed_url=None,
                citation="entered directly in the EHR (no source document)",
            )
        else:
            doc = docs.get(doc_id)
            if doc is None:
                # The dominant 62% case, OR a cross-tenant id the
                # workspace scope correctly refused. Either way: visible.
                source = ResolvedSource(
                    status=UNRESOLVABLE,
                    document_id=doc_id,
                    signed_url=None,
                    citation=(
                        f"source document no longer available "
                        f"(id …{_short_id(doc_id)})"
                    ),
                    unresolvable_reason="source_document_not_found_in_workspace",
                )
            else:
                url = _sign(supabase, doc.get("file_path"))
                if not url:
                    # Found the row but cannot retrieve the object right
                    # now — STILL visible, STILL not a silent dead link.
                    source = ResolvedSource(
                        status=UNRESOLVABLE,
                        document_id=doc_id,
                        signed_url=None,
                        citation=(
                            f"source document found but not retrievable "
                            f"right now (id …{_short_id(doc_id)})"
                        ),
                        unresolvable_reason="signed_url_unavailable",
                    )
                else:
                    source = ResolvedSource(
                        status=OPENABLE,
                        document_id=doc_id,
                        signed_url=url,
                        citation=_citation_for_doc(doc, prov),
                    )

        resolved.append(
            ResolvedRow(data=row.data, provenance=prov, source=source)
        )

    unresolvable_count = sum(
        1 for r in resolved if r.source.status == UNRESOLVABLE
    )
    return ResolvedQueryResult(
        template_id=result.template_id,
        template_version=result.template_version,
        workspace_id=workspace_id,
        rows=resolved,
        row_count=len(resolved),
        data_maturity=result.data_maturity,
        unresolvable_count=unresolvable_count,
    )

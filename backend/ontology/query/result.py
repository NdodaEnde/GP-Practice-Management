"""
The query result contract — frozen.

Every row from every template carries a Provenance. This is the
structural expression of the roadmap's "provenance in every answer":
"Mrs Khumalo: HbA1c 8.9% (Lancet lab report, 8 March 2026, page 1)"
with a one-click link to the source scan.

`source_document_id` may be None ONLY when `source_kind == 'live_entry'`
— a fact a clinician typed directly into the EHR has no source scan.
The contract makes that explicit and honest rather than fabricating a
document id. The runner enforces this invariant on every row.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

LIVE_ENTRY = "live_entry"


@dataclass(frozen=True)
class Provenance:
    source_kind: str                       # 'diagnosis'|'prescription'|'vital'|'live_entry'|...
    source_document_id: Optional[str] = None
    occurred_on: Optional[str] = None      # ISO date the fact was recorded/observed
    snippet: Optional[str] = None          # short human context (e.g. the ICD code)
    page: Optional[int] = None

    def __post_init__(self) -> None:
        if self.source_document_id is None and self.source_kind != LIVE_ENTRY:
            raise ValueError(
                f"provenance with no source_document_id must have "
                f"source_kind={LIVE_ENTRY!r}, got {self.source_kind!r} — "
                f"refusing to present a sourced fact with no source"
            )

    @classmethod
    def from_jsonb(cls, blob: Optional[Dict[str, Any]]) -> "Provenance":
        """Build from the jsonb the RPC returns. A row arriving with no
        provenance object at all is a template bug (the CI invariant
        test exists to prevent it ever shipping) — fail loud here too."""
        if not isinstance(blob, dict):
            raise ValueError(
                f"row arrived without a provenance object "
                f"(got {type(blob).__name__}) — the template's RPC must "
                f"build provenance in the same join that produced the fact"
            )
        return cls(
            source_kind=blob.get("source_kind") or LIVE_ENTRY,
            source_document_id=blob.get("source_document_id"),
            occurred_on=blob.get("occurred_on"),
            snippet=blob.get("snippet"),
            page=blob.get("page"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_kind": self.source_kind,
            "source_document_id": self.source_document_id,
            "occurred_on": self.occurred_on,
            "snippet": self.snippet,
            "page": self.page,
        }


@dataclass(frozen=True)
class QueryRow:
    """One answer row: the data columns + its mandatory provenance."""
    data: Dict[str, Any]              # all non-provenance columns
    provenance: Provenance

    def to_dict(self) -> Dict[str, Any]:
        return {**self.data, "provenance": self.provenance.to_dict()}


@dataclass(frozen=True)
class QueryResult:
    template_id: str
    template_version: int
    workspace_id: str
    rows: List[QueryRow]
    row_count: int
    data_maturity: str = "populated"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "template_version": self.template_version,
            "workspace_id": self.workspace_id,
            "row_count": self.row_count,
            "data_maturity": self.data_maturity,
            "rows": [r.to_dict() for r in self.rows],
        }

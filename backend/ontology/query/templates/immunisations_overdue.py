"""
Template: immunisations_overdue  (Phase 4 PR G, option B)

"Which patients have an overdue next immunisation dose?" — a recall
cohort. STATELESS recomputed cohort (locked Decision 3 / §2.0): NOT an
OpenLoop, no per-row lifecycle. A new StandingQuery kind materialising
into briefing_items through the same chokepoint morning_briefing uses.

Backed by query_immunisations_overdue (migration 029 — surfaced for the
user's per-migration call; the RUN_INTEGRATION test cannot pass until it
is applied). Provenance is honest live_entry: the immunizations table
has no source_document_id (immunisations are EHR-direct), so the
resolver renders NO_SOURCE, never an error.

data_maturity = "thin" (G-3 locked): 1 overdue of 31 on the live corpus
— real, but ONE instance. A reader must not infer volume.
"""

from __future__ import annotations

from ontology.query.registry import register_template
from ontology.query.spec import TemplateSpec

register_template(TemplateSpec(
    id="immunisations_overdue",
    version=1,
    rpc_name="query_immunisations_overdue",
    description="Patients with an overdue next immunisation dose "
                "(series not complete, next_dose_due < today).",
    data_maturity="thin",
    params=[],
    output_columns=[
        "patient_id",
        "first_name",
        "last_name",
        "dob",
        "vaccine_name",
        "next_dose_due",
        "provenance",
    ],
))

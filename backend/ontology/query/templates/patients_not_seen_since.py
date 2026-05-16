"""
Template: patients_not_seen_since

"Which patients in this practice have not been seen in the last N days
(or never)?" — the core of a recall / overdue-review briefing.

Backed by query_patients_not_seen_since (migration 026). Provenance is
the patient's most recent encounter; a NULL-source encounter (the
dominant demo-gp case) resolves NO_SOURCE (live_entry), never an error.
"""

from __future__ import annotations

from ontology.query.registry import register_template
from ontology.query.spec import ParamSpec, TemplateSpec
from ontology.query.templates._validators import validate_days

register_template(TemplateSpec(
    id="patients_not_seen_since",
    version=1,
    rpc_name="query_patients_not_seen_since",
    description="Patients with no encounter in the last N days (or never).",
    data_maturity="populated",
    params=[
        ParamSpec(
            name="days_since",
            py_type=int,
            rpc_arg="p_days_since",
            required=False,
            default=180,
            validator=validate_days,
        ),
    ],
    output_columns=[
        "patient_id",
        "first_name",
        "last_name",
        "dob",
        "last_consultation",
        "provenance",
    ],
))

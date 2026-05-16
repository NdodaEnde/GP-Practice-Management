"""
Template: patient_recent_consultations

"What were this patient's last few visits about?" — recent encounters,
newest first. Pre-consult brief staple.

Backed by query_patient_recent_consultations (migration 026).
Provenance from the encounter; NULL-source ⇒ live_entry.
"""

from __future__ import annotations

from ontology.query.registry import register_template
from ontology.query.spec import ParamSpec, TemplateSpec
from ontology.query.templates._validators import (
    validate_limit,
    validate_patient_id,
)

register_template(TemplateSpec(
    id="patient_recent_consultations",
    version=1,
    rpc_name="query_patient_recent_consultations",
    description="A patient's most recent encounters, newest first.",
    data_maturity="populated",
    params=[
        ParamSpec(
            name="patient_id",
            py_type=str,
            rpc_arg="p_patient_id",
            required=True,
            validator=validate_patient_id,
        ),
        ParamSpec(
            name="limit",
            py_type=int,
            rpc_arg="p_limit",
            required=False,
            default=50,
            validator=validate_limit,
        ),
    ],
    output_columns=[
        "encounter_id",
        "encounter_date",
        "chief_complaint",
        "status",
        "provenance",
    ],
))

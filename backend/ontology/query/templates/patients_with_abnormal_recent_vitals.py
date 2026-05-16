"""
Template: patients_with_abnormal_recent_vitals

"Who had a high BP reading recently?" — abnormal (systolic>140 or
diastolic>90) vitals within N days.

data_maturity = "thin": the live corpus has 0 vitals in demo-gp and 5
globally (2 abnormal). The shape is correct; the data is honestly thin
until vitals capture is populated. Surfaced in the registry, never
hidden behind an empty result that looks like "all clear".

Backed by query_patients_with_abnormal_recent_vitals (migration 026).
"""

from __future__ import annotations

from ontology.query.registry import register_template
from ontology.query.spec import ParamSpec, TemplateSpec
from ontology.query.templates._validators import validate_days

register_template(TemplateSpec(
    id="patients_with_abnormal_recent_vitals",
    version=1,
    rpc_name="query_patients_with_abnormal_recent_vitals",
    description="Patients with abnormal BP (sys>140 / dia>90) in N days.",
    data_maturity="thin",
    params=[
        ParamSpec(
            name="within_days",
            py_type=int,
            rpc_arg="p_within_days",
            required=False,
            default=90,
            validator=validate_days,
        ),
    ],
    output_columns=[
        "patient_id",
        "first_name",
        "last_name",
        "bp_systolic",
        "bp_diastolic",
        "measured_datetime",
        "provenance",
    ],
))

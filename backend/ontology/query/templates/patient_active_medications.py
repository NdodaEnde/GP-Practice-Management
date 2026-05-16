"""
Template: patient_active_medications

"What is this patient currently on?" — active, non-voided prescription
items for one patient. Pre-consult brief staple.

Backed by query_patient_active_medications (migration 026). Provenance
from the prescription item; NULL-source ⇒ live_entry (the dominant
demo-gp case).
"""

from __future__ import annotations

from ontology.query.registry import register_template
from ontology.query.spec import ParamSpec, TemplateSpec
from ontology.query.templates._validators import validate_patient_id

register_template(TemplateSpec(
    id="patient_active_medications",
    version=1,
    rpc_name="query_patient_active_medications",
    description="Active, non-voided prescription items for one patient.",
    data_maturity="populated",
    params=[
        ParamSpec(
            name="patient_id",
            py_type=str,
            rpc_arg="p_patient_id",
            required=True,
            validator=validate_patient_id,
        ),
    ],
    output_columns=[
        "medication_name",
        "dosage",
        "frequency",
        "prescription_date",
        "provenance",
    ],
))

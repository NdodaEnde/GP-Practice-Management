"""
Template: patients_with_lab_threshold

"Who has an HbA1c over 8?" — patients with a numeric lab result for a
given test code at or above a threshold.

data_maturity = "schema_only": the live corpus has exactly 1 lab_result
globally and no LOINC coding (test_system='local'). The shape is
schema-correct and ready for real lab ingestion; until then it honestly
returns ~nothing, and that thinness is surfaced in the registry, never
disguised as a clean cohort.

Backed by query_patients_with_lab_threshold (migration 026).
"""

from __future__ import annotations

from ontology.query.registry import register_template
from ontology.query.spec import ParamSpec, TemplateSpec
from ontology.query.templates._validators import (
    validate_min_value,
    validate_test_code,
)

register_template(TemplateSpec(
    id="patients_with_lab_threshold",
    version=1,
    rpc_name="query_patients_with_lab_threshold",
    description="Patients whose lab result for a test code is >= a value.",
    data_maturity="schema_only",
    params=[
        ParamSpec(
            name="test_code",
            py_type=str,
            rpc_arg="p_test_code",
            required=True,
            validator=validate_test_code,
        ),
        ParamSpec(
            name="min_value",
            py_type=float,
            rpc_arg="p_min_value",
            required=False,
            default=0.0,
            validator=validate_min_value,
        ),
    ],
    output_columns=[
        "patient_id",
        "first_name",
        "last_name",
        "test_name",
        "result_numeric",
        "reference_high",
        "provenance",
    ],
))

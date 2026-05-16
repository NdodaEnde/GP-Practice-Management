"""
Template: patients_with_diagnosis_prefix

"Which patients in this practice have a diagnosis whose ICD-10 code
starts with <prefix>?"  e.g. 'E11' → type-2 diabetes cohort,
'I10' → hypertension cohort.

Chosen as PR 6's single proven shape because diagnoses is the
best-populated coded clinical table on the dev corpus (code reliably
set, indexed) and it exercises the Patient⋈Diagnosis join plus
provenance sourced from diagnoses.source_document_id — the exact
pattern every later template repeats.

Backed by query_patients_with_diagnosis_prefix (migration 024).
"""

from __future__ import annotations

from ontology.query.registry import register_template
from ontology.query.spec import ParamSpec, TemplateSpec


def _validate_icd10_prefix(v: str) -> None:
    s = v.strip()
    if not s:
        raise ValueError("icd10_prefix must be non-empty")
    if len(s) > 8:
        raise ValueError("icd10_prefix too long (max 8 chars)")
    # ICD-10 codes are alnum + dot; reject anything that could be a
    # LIKE/SQL metacharacter (defence in depth — the RPC also
    # parameterises, but fail closed at the edge).
    if any(c in s for c in "%_\\'\";"):
        raise ValueError("icd10_prefix contains illegal characters")


def _validate_limit(v: int) -> None:
    if v < 1 or v > 500:
        raise ValueError("limit must be between 1 and 500")


_ORDER_BY = ("name", "last_consultation")


def _validate_order_by(v: str) -> None:
    if v not in _ORDER_BY:
        raise ValueError(f"order_by must be one of {_ORDER_BY}")


# PR B: version 2 — adds order_by ('name' | 'last_consultation') and a
# last_consultation output column. Supersedes v1 (migration 026 DROP+
# CREATEs the backing function because the return shape changed).
register_template(TemplateSpec(
    id="patients_with_diagnosis_prefix",
    version=2,
    rpc_name="query_patients_with_diagnosis_prefix",
    description="Patients whose diagnosis ICD-10 code starts with a prefix; "
                "optionally ordered by last consultation.",
    data_maturity="populated",
    params=[
        ParamSpec(
            name="icd10_prefix",
            py_type=str,
            rpc_arg="p_icd10_prefix",
            required=True,
            validator=_validate_icd10_prefix,
        ),
        ParamSpec(
            name="limit",
            py_type=int,
            rpc_arg="p_limit",
            required=False,
            default=100,
            validator=_validate_limit,
        ),
        ParamSpec(
            name="order_by",
            py_type=str,
            rpc_arg="p_order_by",
            required=False,
            default="name",
            validator=_validate_order_by,
        ),
    ],
    output_columns=[
        "patient_id",
        "first_name",
        "last_name",
        "dob",
        "diagnosis_code",
        "diagnosis_display",
        "last_consultation",
        "provenance",
    ],
))

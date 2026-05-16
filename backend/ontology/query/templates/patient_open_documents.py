"""
Template: patient_open_documents

"Which documents are still waiting on me?" — digitised documents not
yet finalised (status <> 'validated'), optionally scoped to one
patient. Morning-briefing staple.

Backed by query_patient_open_documents (migration 026). Provenance is
self-referential: the document IS the source, so these rows are always
OPENABLE when the stored object exists.
"""

from __future__ import annotations

from ontology.query.registry import register_template
from ontology.query.spec import ParamSpec, TemplateSpec
from ontology.query.templates._validators import (
    validate_limit,
    validate_patient_id,
)

register_template(TemplateSpec(
    id="patient_open_documents",
    version=1,
    rpc_name="query_patient_open_documents",
    description="Documents not yet finalised, optionally for one patient.",
    data_maturity="populated",
    params=[
        ParamSpec(
            name="patient_id",
            py_type=str,
            rpc_arg="p_patient_id",
            required=False,
            default=None,
            validator=validate_patient_id,
        ),
        ParamSpec(
            name="limit",
            py_type=int,
            rpc_arg="p_limit",
            required=False,
            default=100,
            validator=validate_limit,
        ),
    ],
    output_columns=[
        "document_id",
        "filename",
        "status",
        "upload_date",
        "provenance",
    ],
))

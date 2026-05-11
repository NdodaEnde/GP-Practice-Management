# app/api/ontology.py
"""
Ontology surface endpoints.

Read-only endpoints that expose the ontology layer's introspectable shape
to downstream consumers — frontend TypeScript codegen, OpenAPI docs, and
operations dashboards.

This router carries NO clinical data and NO write paths. Mutations go
through the ActionExecutor (separate plan, not yet built); structured
read endpoints stay on their domain routers (e.g. gp_router).

Scope today: Patient only. Document and Consultation are declared in the
ontology package but not yet wired to a read endpoint or hydrated from
the existing schema; they get added to /schema when their integration
passes land.
"""

from fastapi import APIRouter

from app.core.logging import get_logger
from ontology import Patient

logger = get_logger(__name__)

ontology_router = APIRouter(prefix="/api/ontology", tags=["Ontology"])


@ontology_router.get("/ping")
async def ping():
    """Lightweight health check for the ontology surface.

    Returns the list of object types currently exposed by /schema. Useful
    as a deployment smoke test ("did the ontology import wire up cleanly
    in this environment?") without paying the cost of emitting the full
    schemas.
    """
    return {
        "status": "ok",
        "object_types": ["Patient"],
    }


@ontology_router.get("/schema")
async def get_schema():
    """Return the introspectable schema for every ontology object type
    currently surfaced through the platform.

    Shape: a dict keyed by object_type_name, with each value being the
    output of `Cls.ontology_schema()` — properties, FHIR mapping, PII
    classification, search behaviour, link metadata. This is what the
    frontend TypeScript codegen step consumes (deferred to a later pass).

    When Document and Consultation integrations land, this dict gains
    their entries.
    """
    return {
        "Patient": Patient.ontology_schema(),
    }

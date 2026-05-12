"""
Pytest fixtures for the GP Practice Management backend.

Tiered test access:

  - `unit`               — no fixtures needed, pure Python.
  - `integration`        — needs RUN_INTEGRATION=1 + a running Supabase
                           (no LandingAI dependency). Uses the FAST
                           `validated_document_row` fixture which inserts
                           a row directly into digitised_documents.
  - `slow_integration`   — needs RUN_INTEGRATION=1 AND a running
                           microservice on :5001. Uses the SLOW
                           `validated_document_e2e` fixture which uploads
                           + parses + validates a real fixture file via
                           the microservice.

Run modes:

    pytest backend/tests/                              # unit only (fast)
    RUN_INTEGRATION=1 pytest backend/tests/ -m integration
    RUN_INTEGRATION=1 pytest backend/tests/ -m "integration or slow_integration"
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterator

import pytest


# ----------------------------------------------------------------------------
# Environment gating
# ----------------------------------------------------------------------------

def _integration_enabled() -> bool:
    return os.environ.get("RUN_INTEGRATION") == "1"


def _microservice_url() -> str:
    return os.environ.get("MICROSERVICE_URL", "http://localhost:5001")


@pytest.fixture(scope="session")
def supabase_client():
    """Real Supabase client. Skips if RUN_INTEGRATION isn't set or env is missing."""
    if not _integration_enabled():
        pytest.skip("RUN_INTEGRATION=1 required for integration tests")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        pytest.skip("SUPABASE_URL / SUPABASE_SERVICE_KEY missing from env")
    from supabase import create_client
    return create_client(url, key)


@pytest.fixture(scope="session")
def supabase_client_b():
    """SECOND independent Supabase client instance — used by the Phase 0
    advisory-lock semantics test to verify locks acquired by one client
    are visible (or not) to another client through the HTTP-pooled
    PostgREST layer.

    Distinct from supabase_client (above) which is the primary client.
    Same SUPABASE_URL + SUPABASE_SERVICE_KEY, separate create_client() call,
    so PostgREST treats them as separate requests."""
    if not _integration_enabled():
        pytest.skip("RUN_INTEGRATION=1 required for integration tests")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        pytest.skip("SUPABASE_URL / SUPABASE_SERVICE_KEY missing from env")
    from supabase import create_client
    return create_client(url, key)


# ----------------------------------------------------------------------------
# Seed fixtures — workspace + practice cleanup
# ----------------------------------------------------------------------------

@pytest.fixture
def seed_practice(supabase_client) -> Iterator[Dict[str, str]]:
    """Create a throwaway workspace + tenant in Supabase, yield their IDs,
    clean up after the test.

    Workspace IDs are slug-style (per setup_supabase.sql's TEXT PRIMARY KEY
    pattern); tests can use these directly as practice_id / workspace_id
    in Action calls."""
    sb = supabase_client
    tenant_id = f"test-tenant-{uuid.uuid4().hex[:8]}"
    workspace_id = f"test-workspace-{uuid.uuid4().hex[:8]}"

    sb.table("tenants").insert({
        "id": tenant_id,
        "name": "Test Tenant (autocreated)",
    }).execute()
    sb.table("workspaces").insert({
        "id": workspace_id,
        "tenant_id": tenant_id,
        "name": "Test Workspace (autocreated)",
        "type": "gp",
    }).execute()

    yield {"tenant_id": tenant_id, "workspace_id": workspace_id}

    # Cleanup: cascade-friendly order
    try:
        sb.table("workspaces").delete().eq("id", workspace_id).execute()
        sb.table("tenants").delete().eq("id", tenant_id).execute()
    except Exception:  # noqa: BLE001
        # Cleanup is best-effort; the next test run uses different IDs.
        pass


@pytest.fixture
def validated_document_row(supabase_client, seed_practice) -> Iterator[Dict[str, Any]]:
    """FAST fixture: insert a row directly into digitised_documents with
    status='validated' and a known extraction JSONB shape — no parser, no
    LandingAI, no microservice required.

    The extraction JSONB matches the structure that extraction_promoter
    consumes (patient_demographics, diagnoses, medications, vitals,
    progress_notes). Used by integration-tier tests that exercise the
    executor's logic against a deterministic input.

    Cleans up the row after the test."""
    sb = supabase_client
    doc_id = str(uuid.uuid4())
    workspace_id = seed_practice["workspace_id"]

    extraction = {
        "patient_demographics": {
            "first_name": "Test",
            "surname": "Patient",
            "date_of_birth": "1985-03-14",
            "id_number": "8503140001087",
            "telephone_cell": "+27821234567",
            "email": "test@example.co.za",
            "address": "12 Test Rd",
        },
        "diagnoses": [
            {"condition_name": "Hypertension", "icd10_code": "I10"},
        ],
        "medications": [
            {"medication_name": "Atenolol", "dosage_info": "50mg daily"},
        ],
        "vitals": [
            {"bp_systolic": 130, "bp_diastolic": 85, "consultation_date": "2026-05-01"},
        ],
        "progress_notes": [
            {
                "consultation_date": "2026-05-01",
                "notes": "Stable on current treatment.",
            },
        ],
    }
    sb.table("digitised_documents").insert({
        "id": doc_id,
        "workspace_id": workspace_id,
        "filename": f"test_fixture_{doc_id[:8]}.pdf",
        "status": "validated",
        "extraction": extraction,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    yield {"document_id": doc_id, "extraction": extraction, **seed_practice}

    try:
        sb.table("digitised_documents").delete().eq("id", doc_id).execute()
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture
def validated_document_e2e(supabase_client, seed_practice) -> Iterator[Dict[str, Any]]:
    """SLOW fixture: uploads + parses + validates a real fixture file via
    the running microservice. Marked for use only by slow_integration tests.

    Requires:
      - Microservice running on :5001 (or MICROSERVICE_URL env var).
      - A fixture file at backend/tests/fixtures/sample_consultation.pdf
        (committed alongside this conftest).

    This fixture is for tests that genuinely need to exercise the LandingAI
    parser. Most tests should use validated_document_row instead.

    NOTE: For PR 1, the e2e fixture is wired but the actual fixture file is
    not yet committed — the slow_integration tests that depend on it will
    skip cleanly if the file doesn't exist. The fixture is provided as
    infrastructure; the file is a PR 2 deliverable."""
    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "sample_consultation.pdf"
    )
    if not os.path.exists(fixture_path):
        pytest.skip(f"fixture file {fixture_path} not committed yet (PR 2 deliverable)")
    pytest.skip("slow_integration fixture not implemented in PR 1")
    yield {}  # unreachable

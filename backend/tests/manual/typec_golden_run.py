"""
Piece 2 — the SUFFICIENT live verification (golden path), brought to the
bar for review. NOT a pytest. NOT auto-run. Requires RUN_TYPEC_GOLDEN=1
AND an explicit invocation, so it can never fire accidentally or be
collected by a suite.

WHAT IT IS (earns-split / hazards, stated up front):
  * Engine-layer drive of the EXACT calls the Type-C path makes:
    GPDocumentProcessor.process_and_save_patient_file (the call the
    document_watcher's _process_single_document makes) + execute(
    PromoteDocumentToPatientRecord(...)) mirrored VERBATIM from
    app/api/digitisation.py:1289-1314. It does NOT start the
    document_watcher (the watcher auto-processes real queued PHI docs —
    a credit+PHI hazard; avoided by driving the engine directly).
  * NOT a browser UI click-through (that needs app+frontend up + the
    watcher hazard solved separately). This proves the pipeline the
    Type-C UI invokes, end to end, at the engine/executor layer.
  * SYNTHETIC ONLY: backend/tests/fixtures/clean_consult.pdf (the
    auditable synthetic fixture). No real patient data, ever.
  * SPENDS LandingAI credits: one synthetic doc = 1 parse + N extract.
  * WRITES LIVE SUPABASE, then tears down residue-safe and proves it
    clean by an INDEPENDENT read-back.

PREMISES CLOSED AT FILE:LINE BEFORE THIS WAS WRITTEN (do not re-derive):
  A. execute(action,*,actor:ActorContext,supabase,...) ; ActorContext
     directly constructible (base.py:108-125).
  B. Real Type-C approve construction mirrored verbatim
     (digitisation.py:1289-1314).
  C. Forward promote => ONE canonical action_audit_log row, written by
     the Python executor (_finalise->_write_audit_row, unconditional;
     migration 015's audit INSERT @1342 is the *reverse* function,
     never reached here). That one row carries COMPLETE affected_objects
     (primitives.py PromoteExtractionsViaPromoter.apply copies every
     RPC-returned entry into ctx.audit_row_in_progress before persist).

The TEARDOWN is the load-bearing part — review it harder than the
orchestration. Orchestration failure is loud (errors, nothing persists).
Teardown failure is the silent live-Supabase residue this whole
sub-thread exists to prevent.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Run-as-a-file robustness (first-run scaffolding fix, the PR-F/G/H
# class): invoked as `python tests/manual/typec_golden_run.py`,
# sys.path[0] is THIS file's dir (backend/tests/manual), not backend/ —
# so the deferred `from app...`/`from ontology...`/`import server`
# imports inside run() raise ModuleNotFoundError before the pipeline
# executes. Put backend/ on the path so the AUTHORISED run can actually
# run. This changes only import resolution; the orchestration, teardown,
# and three-key independent read-back are untouched.
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "clean_consult.pdf"

# type -> table. Any affected_objects type NOT in this map is a LOUD
# error in teardown (an unmapped created type = potential silent
# residue; never skipped silently).
_TYPE_TABLE = {
    "Patient": "patients",
    "Consultation": "encounters",
    "Diagnosis": "diagnoses",
    "Vital": "vitals",
    "Allergy": "allergies",
    "Prescription": "prescriptions",
    "PrescriptionItem": "prescription_items",
}
# FK-safe delete order (children before parents): items->scripts,
# clinical children->encounters->patient; clinical rows before the
# source document.
_DELETE_ORDER = [
    "prescription_items", "prescriptions", "diagnoses", "vitals",
    "allergies", "encounters", "patients",
]

# Independent residue read-back table sets — VERIFIED at file:line
# against migration 015's INSERT column lists (not assumed):
#   * workspace_id present: patients, encounters, diagnoses, vitals,
#     allergies, prescriptions. prescription_items INSERT (015:1019-1036)
#     has NO workspace_id column -> a .eq("workspace_id",...) on it
#     errors, it does not verify; it is therefore EXCLUDED here and
#     covered by the source_document_id sweep + the id-driven teardown.
#   * source_document_id present (= p_document_id): encounters,
#     diagnoses, vitals, allergies, prescriptions, prescription_items.
#     patients INSERT (015:700-740) has NO source_document_id (entity,
#     matched/created) -> covered by the run-captured tracked patient id.
# The source_document_id sweep is the LOAD-BEARING independent check: it
# depends on neither workspace_id correctness (the unverified Fork-2
# premise) nor affected_objects-completeness — it keys off the one column
# the SQL provably stamps on every document-derived clinical write.
_WS_TABLES = ["patients", "encounters", "diagnoses", "vitals",
              "allergies", "prescriptions"]
_SRCDOC_TABLES = ["encounters", "diagnoses", "vitals", "allergies",
                  "prescriptions", "prescription_items"]


def _load_env(sb_mod):
    envf = Path(__file__).resolve().parents[2] / ".env"
    for ln in envf.read_text().splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#") and "=" in ln:
            k, v = ln.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _client():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"],
                          os.environ["SUPABASE_SERVICE_KEY"])


def run():
    if os.environ.get("RUN_TYPEC_GOLDEN") != "1":
        print("REFUSING: set RUN_TYPEC_GOLDEN=1 to run (credit + live write).")
        sys.exit(2)
    if not _FIXTURE.exists():
        print(f"REFUSING: synthetic fixture missing: {_FIXTURE}")
        sys.exit(2)

    _load_env(None)
    sb = _client()

    sfx = uuid.uuid4().hex[:8]
    tenant_id = f"test-tn-{sfx}"
    workspace_id = f"test-ws-{sfx}"
    doc_id = f"test-doc-{sfx}"
    created_audit_id = None
    created_patient_id = None
    parsed_doc_id = session_id = None

    try:
        # --- seed throwaway synthetic tenant+workspace (seed_practice idiom)
        sb.table("tenants").insert(
            {"id": tenant_id, "name": "Test Tenant (typec golden)"}).execute()
        sb.table("workspaces").insert(
            {"id": workspace_id, "tenant_id": tenant_id,
             "name": "Test WS (typec golden)", "type": "gp"}).execute()
        sb.table("digitised_documents").insert({
            "id": doc_id, "workspace_id": workspace_id,
            "filename": "clean_consult.pdf",
            "file_path": f"test/fixtures/{doc_id}.pdf",
            "status": "validated",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        # --- parse + extract: the EXACT engine call the watcher makes,
        #     driven directly (no watcher loop). Real LandingAI.
        from app.services.gp_processor import GPDocumentProcessor
        proc = GPDocumentProcessor(supabase_client=sb)
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            proc.process_and_save_patient_file(
                file_path=str(_FIXTURE), filename="clean_consult.pdf",
                organization_id=workspace_id, document_id=doc_id,
                workspace_id=workspace_id))
        print("PARSE/EXTRACT actuals:", {
            "success": result.get("success"),
            "pages": result.get("pages_processed"),
            "chunks": len(result.get("chunks") or []),
            "parsed_doc_id": result.get("parsed_doc_id"),
            "validation_session_id": result.get("validation_session_id"),
        })
        parsed_doc_id = result.get("parsed_doc_id")
        session_id = result.get("validation_session_id")
        assert result.get("success"), f"parse/extract failed: {result.get('error')}"

        # --- read the real extracted JSONB the doctor would review
        sess = (sb.table("gp_validation_sessions").select("extractions")
                .eq("id", session_id).execute().data)
        extractions = (sess[0]["extractions"] if sess else {}) or {}
        print("EXTRACTION actuals (synthetic) — SHAPE:",
              {k: (len(v) if isinstance(v, list) else "obj")
               for k, v in extractions.items()})
        # VALUES for the value-by-value oracle check (synthetic data —
        # safe to print; the oracle is knowable precisely because it is
        # synthetic). The oracle-relevant slices, full, not shape.
        for _k in ("patient_demographics", "diagnoses", "medications",
                   "vitals_history", "progress_notes"):
            print(f"  EXTRACTED {_k}: {extractions.get(_k)}")

        # --- approve/promote: VERBATIM mirror of digitisation.py:1289-1314
        from app.actions import ActorContext, execute
        from ontology.actions.promote_document import (
            PatientMatchEvidence, PromoteDocumentToPatientRecord)
        actor_id = "typec-golden-synthetic-actor"
        confirmation = PatientMatchEvidence(
            confirmed_by_user_id=actor_id,
            confirmed_at=datetime.now(timezone.utc),
            match_signals=["force_create"],
            confidence_score=0.0,
        )
        action = PromoteDocumentToPatientRecord(
            document_id=doc_id, target_patient_id="",
            confirmation=confirmation, actor_user_id=actor_id,
            practice_id=workspace_id, workspace_id=workspace_id,
            extractions=extractions, forced_patient_id=None,
            force_create_patient=True,
        )
        ar = execute(action,
                     actor=ActorContext(user_id=actor_id,
                                        email="typec-golden@synthetic.local"),
                     supabase=sb)
        created_audit_id = ar.audit_id
        # Capture the single created/linked patient id AT RUN TIME (we
        # hold it directly, like session_id) — patients has no
        # source_document_id, so this tracked id is its independent
        # residue key (independent of workspace_id / Fork-2).
        created_patient_id = next(
            (e["id"] for e in ar.affected_objects
             if e.get("type") == "Patient"
             and e.get("op") in ("created", "linked")),
            None)
        # Observability: surface the failure reason BEFORE the finally
        # teardown removes the audit row that carries error_detail. A
        # precondition_failed/effect_failed must be diagnosable from the
        # output, not swallowed by residue-safety. (Harness diagnostic
        # fix — touches only this print; teardown/read-back unchanged.)
        _err = getattr(ar, "error", None)
        print("PROMOTE actuals:", {
            "outcome": ar.outcome, "audit_id": ar.audit_id,
            "created_patient_id": created_patient_id,
            "error": (None if _err is None else {
                "code": getattr(_err, "code", None),
                "message": getattr(_err, "message", None),
                "context": getattr(_err, "context", None),
            }),
            "affected_objects": ar.affected_objects,
        })

        # --- provenance read-back: the created rows are REAL extracted
        #     values, not fabricated (actuals before interpretation).
        for e in ar.affected_objects:
            t = e.get("type")
            tbl = _TYPE_TABLE.get(t)
            if tbl and e.get("op") == "created":
                row = (sb.table(tbl).select("*")
                       .eq("id", e["id"]).execute().data)
                print(f"PROVENANCE {t}({e['id']}): "
                      f"{'present' if row else 'MISSING'}")
                # The PERSISTED row's literal values — the certification
                # target for the value-by-value oracle trace. Printed
                # BEFORE the finally-teardown deletes it (the values were
                # being swallowed by residue-safety; surfaced now).
                if row:
                    print(f"  VALUES {t}: {row[0]}")

    finally:
        # ============== TEARDOWN (the load-bearing part) ==============
        # Driven off the PERSISTED audit row's affected_objects (re-read
        # from action_audit_log by audit_id — operate on what the DB
        # actually stored, the verified-complete single canonical row;
        # NOT the in-process ActionResult).
        persisted_affected = []
        if created_audit_id:
            arow = (sb.table("action_audit_log")
                    .select("affected_objects")
                    .eq("id", created_audit_id).execute().data)
            persisted_affected = (arow[0].get("affected_objects")
                                  if arow else []) or []

        # group created ids by table; LOUD on any unmapped created type
        by_table: dict = {t: [] for t in _DELETE_ORDER}
        unmapped = []
        for e in persisted_affected:
            if e.get("op") != "created":
                continue
            t = e.get("type")
            if t == "Document":
                continue  # my synthetic doc; deleted wholesale below
            tbl = _TYPE_TABLE.get(t)
            if tbl is None:
                unmapped.append(e)
            else:
                by_table[tbl].append(e["id"])
        if unmapped:
            print(f"TEARDOWN HALT: unmapped created type(s) {unmapped} — "
                  f"NOT skipped silently; manual review required.")

        for tbl in _DELETE_ORDER:
            for rid in by_table.get(tbl, []):
                try:
                    sb.table(tbl).delete().eq("id", rid).execute()
                except Exception as ex:  # noqa: BLE001
                    print(f"teardown delete {tbl}/{rid} error: {ex}")

        # my synthetic doc artifacts, by tracked id (created-by-me)
        for tbl, rid in (("gp_validation_sessions", session_id),
                         ("gp_parsed_documents", parsed_doc_id),
                         ("digitised_documents", doc_id)):
            if rid:
                try:
                    sb.table(tbl).delete().eq("id", rid).execute()
                except Exception as ex:  # noqa: BLE001
                    print(f"teardown delete {tbl}/{rid} error: {ex}")

        # the single canonical audit row: null the self-FKs first (PR-F
        # §5.1 idiom — defensive; NULL on a forward-only run), then delete
        if created_audit_id:
            try:
                sb.table("action_audit_log").update(
                    {"reverses_audit_id": None,
                     "reversed_by_audit_id": None}
                ).eq("id", created_audit_id).execute()
                sb.table("action_audit_log").delete().eq(
                    "id", created_audit_id).execute()
            except Exception as ex:  # noqa: BLE001
                print(f"teardown audit-row error: {ex}")

        for tbl, rid in (("workspaces", workspace_id),
                         ("tenants", tenant_id)):
            try:
                sb.table(tbl).delete().eq("id", rid).execute()
            except Exception as ex:  # noqa: BLE001
                print(f"teardown delete {tbl}/{rid} error: {ex}")

        # ===== INDEPENDENT residue read-back — THREE keys =====
        # Separate from the teardown's own belief: queries the DB
        # directly. CAN FAIL ON ITS OWN, loudly, regardless of whether
        # the teardown thought it succeeded. Three independent keys; the
        # source_document_id sweep is load-bearing because it depends on
        # NEITHER workspace_id correctness (unverified Fork-2) NOR
        # affected_objects-completeness.
        residue = []

        # (1) LOAD-BEARING: source_document_id == doc_id over the 6
        #     clinical tables that carry it (verified at file:line).
        #     Independent of Fork-2 AND of affected_objects-completeness.
        for tbl in _SRCDOC_TABLES:
            n = (sb.table(tbl).select("id")
                 .eq("source_document_id", doc_id).execute().data) or []
            if n:
                residue.append(f"{tbl}: {len(n)} (by source_document_id)")

        # (2) workspace_id sweep — ONLY the 6 tables that have the column
        #     (prescription_items excluded: no workspace_id col -> the
        #     query would error, not verify). Corroborating, not relied on.
        for tbl in _WS_TABLES:
            n = (sb.table(tbl).select("id")
                 .eq("workspace_id", workspace_id).execute().data) or []
            if n:
                residue.append(f"{tbl}: {len(n)} (by workspace_id)")

        # (3) tracked ids we hold directly from the run (incl. patients —
        #     no source_document_id column; this is its independent key).
        for tbl, col, rid in (
            ("patients", "id", created_patient_id),
            ("gp_validation_sessions", "id", session_id),
            ("gp_parsed_documents", "id", parsed_doc_id),
            ("digitised_documents", "id", doc_id),
            ("action_audit_log", "id", created_audit_id),
            ("workspaces", "id", workspace_id),
            ("tenants", "id", tenant_id),
        ):
            if not rid:
                continue
            n = (sb.table(tbl).select("id").eq(col, rid).execute().data) or []
            if n:
                residue.append(f"{tbl}: {len(n)} (id={rid})")

        if residue:
            print("RESIDUE NOT CLEAN — independent read-back found:")
            for r in residue:
                print("  " + r)
            sys.exit(1)
        print("RESIDUE CLEAN — independent read-back: 0 rows, three "
              "independent keys (source_document_id [load-bearing] AND "
              "workspace_id AND tracked-id, incl. patients-by-tracked-id).")


if __name__ == "__main__":
    run()

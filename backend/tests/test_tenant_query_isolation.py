"""
Tenant-query-isolation guard — the application-layer half of PR 5.

WHY THIS EXISTS
---------------

The backend talks to Supabase as `service_role`, which has
rolbypassrls = TRUE. Row Level Security (migration 018) therefore does
NOT constrain the backend's own queries — it only closes the
client-direct (anon / leaked-token) surface. The threat RLS cannot
catch here is the one that actually happens in practice: a developer
writes a query against a patient-identifiable table and forgets the
`workspace_id` / `tenant_id` filter, so the service-role query returns
another practice's data.

This test is the only layer that can catch that, because it inspects
the source statically rather than relying on a DB role that bypasses
RLS.

WHAT IT DOES
------------

AST-walks every backend source file. For each
`supabase…​.table("<HIGH_PII_TABLE>")` query chain it checks the
enclosing statement for a tenant-scoping predicate
(`.eq("workspace_id", …)`, `.eq("tenant_id", …)`, `.match({...})`,
`.contains("affected_objects", …)` — the audit-log containment idiom,
`.in_("workspace_id", …)`, …). A chain with none of those is a
candidate leak.

THE RATCHET
-----------

The codebase predates this guard and has a baseline of unscoped
chains. Auditing all ~170 by hand before the guard can land would
block the guard indefinitely, so instead:

  * BASELINE is a frozenset of stable keys ("relpath::lineno::table")
    captured at PR 5 time — the known, pre-existing unscoped chains.
  * The test FAILS if a NEW unscoped chain appears (regression) — this
    is the bleeding-stop.
  * The test ALSO fails if a BASELINE entry no longer exists (someone
    fixed or moved it) so the baseline stays honest and shrinks over
    time instead of rotting.

The BASELINE is NOT an assertion that those queries are safe. It is the
incremental-hardening worklist. Each removal is one query proven
workspace-scoped. The number only goes down.
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest


# High-PII tenant tables. Config/template tables (extraction_templates,
# prescription_templates, …) are intentionally excluded — lower risk,
# noisier, and RLS still covers their anon surface. Add a table here
# when it starts holding patient-identifiable data.
TENANT_TABLES: Set[str] = {
    "patients",
    "encounters",
    "diagnoses",
    "vitals",
    "allergies",
    "prescriptions",
    "prescription_items",
    "digitised_documents",
    "gp_validation_sessions",
    "action_audit_log",
    "sick_notes",
    "referrals",
    "clinical_notes",
    "invoices",
    "gp_invoices",
    "payments",
    "medical_aid_claims",
    "lab_orders",
    "immunizations",
    "procedures",
    # PR D: materialised standing-query rows. RLS-deny-all (migration
    # 027, the 018 idiom). Every standing.py / query.py briefing_items
    # chain carries .eq("workspace_id", …), so adding it here adds ZERO
    # new BASELINE keys — a new tenant table joins the scanned set
    # born-scoped, the ratchet doing its job (it only goes down).
    "briefing_items",
}

# Predicates that count as a tenant scope on a query chain. First-arg
# string literal must be one of these column names for .eq/.in_/.neq;
# .match({...}) is checked for the keys; .contains() on
# affected_objects is the audit-log document/patient containment idiom
# (the row IS the scoping — affected_objects @> [{type,id}]).
SCOPING_COLUMNS: Set[str] = {"workspace_id", "tenant_id"}
SCOPING_METHODS_KEYED = {"eq", "in_", "neq", "is_", "match", "filter"}
CONTAINMENT_OK = {"contains"}  # .contains("affected_objects", …) audit idiom

# Files to scan.
BACKEND = Path(__file__).resolve().parent.parent
SCAN_ROOTS = [
    BACKEND / "app",
    BACKEND / "server.py",
    BACKEND / "ontology",
]
SKIP_DIRS = {"__pycache__", ".venv", "tests", "migrations", "scripts"}


def _iter_py_files() -> List[Path]:
    out: List[Path] = []
    for root in SCAN_ROOTS:
        if root.is_file() and root.suffix == ".py":
            out.append(root)
        elif root.is_dir():
            for p in root.rglob("*.py"):
                if any(part in SKIP_DIRS for part in p.parts):
                    continue
                out.append(p)
    return out


def _first_str_arg(call: ast.Call):
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


class _ChainScanner(ast.NodeVisitor):
    """Find .table("<tenant>") calls and decide whether the enclosing
    statement scopes them."""

    def __init__(self, relpath: str):
        self.relpath = relpath
        self.unscoped: List[Tuple[str, int, str]] = []
        self._stmt_stack: List[ast.stmt] = []

    # Track the enclosing statement so we can scan its whole subtree
    # for a scoping predicate (supabase chains are single expressions;
    # statement-level scan keeps false-positives low).
    def generic_visit(self, node):
        if isinstance(node, ast.stmt):
            self._stmt_stack.append(node)
            super().generic_visit(node)
            self._stmt_stack.pop()
        else:
            super().generic_visit(node)

    def visit_Call(self, node: ast.Call):
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "table"
            and (tbl := _first_str_arg(node)) in TENANT_TABLES
        ):
            stmt = self._stmt_stack[-1] if self._stmt_stack else node
            if not self._stmt_is_scoped(stmt):
                self.unscoped.append((self.relpath, node.lineno, tbl))
        self.generic_visit(node)

    @staticmethod
    def _stmt_is_scoped(stmt: ast.AST) -> bool:
        for sub in ast.walk(stmt):
            if not isinstance(sub, ast.Call) or not isinstance(sub.func, ast.Attribute):
                continue
            m = sub.func.attr
            if m in CONTAINMENT_OK:
                # .contains("affected_objects", …) — the row's own
                # affected_objects array IS the scope.
                if _first_str_arg(sub) == "affected_objects":
                    return True
            if m in SCOPING_METHODS_KEYED:
                arg0 = _first_str_arg(sub)
                if arg0 in SCOPING_COLUMNS:
                    return True
                # .match({...}) / .filter — inspect dict keys / filter col
                if m == "match" and sub.args and isinstance(sub.args[0], ast.Dict):
                    for k in sub.args[0].keys:
                        if isinstance(k, ast.Constant) and k.value in SCOPING_COLUMNS:
                            return True
        return False


def _collect_unscoped() -> List[Tuple[str, int, str]]:
    found: List[Tuple[str, int, str]] = []
    for path in _iter_py_files():
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        rel = str(path.relative_to(BACKEND))
        scanner = _ChainScanner(rel)
        scanner.visit(tree)
        found.extend(scanner.unscoped)
    return found


def _key(item: Tuple[str, int, str]) -> str:
    rel, line, tbl = item
    return f"{rel}::{line}::{tbl}"


# ---------------------------------------------------------------------------
# BASELINE — pre-existing unscoped chains at PR 5 time. The worklist.
# Regenerate intentionally only when shrinking it (a fix) — never to
# silence a new regression. Generated by:
#   pytest -q tests/test_tenant_query_isolation.py -s   (prints the set)
# ---------------------------------------------------------------------------
BASELINE: Set[str] = {
    "app/api/clinical_actions.py::121::prescriptions",
    "app/api/digitisation.py::1009::gp_validation_sessions",
    "app/api/digitisation.py::1035::gp_validation_sessions",
    "app/api/digitisation.py::1084::gp_validation_sessions",
    "app/api/digitisation.py::1089::digitised_documents",
    "app/api/digitisation.py::1134::gp_validation_sessions",
    "app/api/digitisation.py::1212::gp_validation_sessions",
    "app/api/digitisation.py::1253::digitised_documents",
    "app/api/digitisation.py::1257::gp_validation_sessions",
    "app/api/digitisation.py::1336::digitised_documents",
    "app/api/digitisation.py::1361::digitised_documents",
    "app/api/digitisation.py::1438::digitised_documents",
    "app/api/digitisation.py::1559::digitised_documents",
    "app/api/digitisation.py::300::gp_validation_sessions",
    "app/api/digitisation.py::323::gp_validation_sessions",
    "app/api/digitisation.py::866::gp_validation_sessions",
    "app/api/gp_endpoints.py::292::patients",
    "app/api/gp_endpoints.py::296::patients",
    "app/api/gp_endpoints.py::353::gp_validation_sessions",
    "app/api/gp_endpoints.py::362::gp_validation_sessions",
    "app/api/gp_endpoints.py::371::patients",
    "app/api/gp_endpoints.py::373::patients",
    "app/api/gp_endpoints.py::423::patients",
    "app/api/gp_endpoints.py::539::patients",
    "app/api/gp_endpoints.py::589::patients",
    "app/api/gp_endpoints.py::593::patients",
    "app/api/gp_endpoints.py::594::patients",
    "app/api/gp_endpoints.py::595::patients",
    "app/api/gp_endpoints.py::664::gp_validation_sessions",
    "app/api/gp_endpoints.py::736::digitised_documents",
    "app/services/digitisation_export_worker.py::425::gp_validation_sessions",
    "app/services/document_watcher.py::209::digitised_documents",
    "app/services/document_watcher.py::223::digitised_documents",
    "app/services/document_watcher.py::244::digitised_documents",
    "app/services/document_watcher.py::279::digitised_documents",
    "app/services/document_watcher.py::314::digitised_documents",
    "app/services/document_watcher.py::347::digitised_documents",
    "app/services/document_watcher.py::363::digitised_documents",
    "app/services/gp_processor.py::520::gp_validation_sessions",
    "app/services/gp_processor.py::538::gp_validation_sessions",
    "app/services/gp_processor.py::570::patients",
    "app/services/gp_processor.py::594::patients",
    "app/services/gp_processor.py::619::patients",
    "app/services/patient_matching.py::214::patients",
    "app/services/semantic_search.py::157::digitised_documents",
    "app/services/semantic_search.py::170::digitised_documents",
    "app/services/semantic_search.py::183::gp_validation_sessions",
    "ontology/actions/edit_extraction_field.py::84::gp_validation_sessions",
    "ontology/actions/soft_delete_patient.py::54::prescriptions",
    "ontology/actions/soft_delete_patient.py::84::digitised_documents",
    "server.py::1066::patients",
    "server.py::1116::patients",
    "server.py::1130::patients",
    "server.py::1161::encounters",
    "server.py::1183::encounters",
    "server.py::1193::encounters",
    "server.py::1216::encounters",
    "server.py::1539::encounters",
    "server.py::1608::patients",
    "server.py::1733::digitised_documents",
    "server.py::1752::digitised_documents",
    "server.py::1787::digitised_documents",
    "server.py::1822::digitised_documents",
    "server.py::2009::gp_invoices",
    "server.py::2168::gp_invoices",
    "server.py::2267::digitised_documents",
    "server.py::2271::digitised_documents",
    "server.py::2313::digitised_documents",
    "server.py::2328::digitised_documents",
    "server.py::2417::digitised_documents",
    "server.py::2623::digitised_documents",
    "server.py::2765::patients",
    "server.py::2804::digitised_documents",
    "server.py::2883::digitised_documents",
    "server.py::2894::digitised_documents",
    "server.py::2923::digitised_documents",
    "server.py::2940::digitised_documents",
    "server.py::3022::digitised_documents",
    "server.py::3053::patients",
    "server.py::3076::digitised_documents",
    "server.py::3089::patients",
    "server.py::3164::gp_validation_sessions",
    "server.py::3221::digitised_documents",
    "server.py::3267::digitised_documents",
    "server.py::3291::digitised_documents",
    "server.py::3309::digitised_documents",
    "server.py::3331::digitised_documents",
    "server.py::3415::digitised_documents",
    "server.py::3450::digitised_documents",
    "server.py::3460::digitised_documents",
    "server.py::3486::digitised_documents",
    "server.py::3529::digitised_documents",
    "server.py::3548::digitised_documents",
    "server.py::3603::digitised_documents",
    "server.py::3623::digitised_documents",
    "server.py::3638::digitised_documents",
    "server.py::3835::digitised_documents",
    "server.py::3860::digitised_documents",
    "server.py::3871::gp_validation_sessions",
    "server.py::3898::gp_validation_sessions",
    "server.py::389::encounters",
    "server.py::3972::digitised_documents",
    "server.py::4010::patients",
    "server.py::427::encounters",
    "server.py::4589::encounters",
    "server.py::4614::clinical_notes",
    "server.py::4692::allergies",
    "server.py::4762::prescriptions",
    "server.py::4783::prescription_items",
    "server.py::479::allergies",
    "server.py::4804::prescriptions",
    "server.py::4813::prescription_items",
    "server.py::4833::prescriptions",
    "server.py::4839::prescription_items",
    "server.py::4877::sick_notes",
    "server.py::4894::sick_notes",
    "server.py::4934::referrals",
    "server.py::4951::referrals",
    "server.py::497::allergies",
    "server.py::5063::patients",
    "server.py::5093::prescriptions",
    "server.py::5103::prescription_items",
    "server.py::5191::prescription_items",
    "server.py::547::diagnoses",
    "server.py::607::diagnoses",
    "server.py::649::vitals",
    "server.py::675::vitals",
    "server.py::757::encounters",
}


def test_no_new_unscoped_tenant_queries():
    """Fails on any tenant-table query chain that lacks a workspace /
    tenant scope and is not in the BASELINE worklist."""
    current = {_key(i) for i in _collect_unscoped()}

    new_violations = sorted(current - BASELINE)
    fixed_or_moved = sorted(BASELINE - current)

    msg_parts = []
    if new_violations:
        msg_parts.append(
            "NEW unscoped tenant queries (add a workspace_id/tenant_id "
            "filter, or — only if provably global — add the key to "
            "BASELINE with a one-line justification):\n  "
            + "\n  ".join(new_violations)
        )
    if fixed_or_moved:
        msg_parts.append(
            "BASELINE entries no longer found (a query was fixed or "
            "moved — good; remove these stale keys from BASELINE so it "
            "keeps shrinking honestly):\n  "
            + "\n  ".join(fixed_or_moved)
        )
    assert not msg_parts, "\n\n".join(msg_parts)


if __name__ == "__main__":
    # Convenience: print the current set so the baseline can be seeded.
    for k in sorted(_key(i) for i in _collect_unscoped()):
        print(k)

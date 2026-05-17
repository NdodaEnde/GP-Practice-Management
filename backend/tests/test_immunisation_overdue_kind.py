"""
PR G (option B) — immunisation_overdue derived kind, DB-free suite.

Proves the template + StandingQuery kind are registered and shaped to
the verified standing-query contract, WITHOUT a DB. The materialisation
read-back (the real 1/31 row) is RUN_INTEGRATION
(test_immunisation_overdue_materialise.py) and cannot pass until the
user applies migration 029 — its own per-migration call.

Non-vacuity (the §D.1 discipline carried): the suite asserts the new
kind was ADDED, not substituted (exactly two registered kinds now, both
present), and that the provenance contract the kind passes actually
BITES (a TemplateSpec without 'provenance' is rejected) — a registration
test that only checked "it imports" would be the vacuous-green shape.
"""

from __future__ import annotations

import pytest

import ontology.query.registered  # noqa: F401  (fires register_template)
from ontology.query.registry import all_templates
from ontology.query.spec import TemplateSpec
from ontology.query import standing


def _template(tid):
    return next((t for t in all_templates() if t.id == tid), None)


def test_immunisations_overdue_template_registered_and_shaped():
    t = _template("immunisations_overdue")
    assert t is not None, "immunisations_overdue template not registered"
    assert t.rpc_name == "query_immunisations_overdue"
    assert t.rpc_name.startswith("query_")          # the spec contract
    assert t.data_maturity == "thin"                # G-3 locked — thin, stated
    assert "provenance" in t.output_columns         # every answer carries source
    assert t.params == []                            # no params (overdue-as-of-now)
    assert "next_dose_due" in t.output_columns


def test_standing_kind_registered_as_ADDED_not_substituted():
    kinds = {sq.kind for sq in standing.all_standing()}
    # the new kind is present...
    assert "immunisation_overdue" in kinds
    sq = standing.get_standing("immunisation_overdue")
    assert sq.template_id == "immunisations_overdue"
    assert sq.params == {}
    # ...AND morning_briefing is STILL present (added, not replaced) —
    # the non-vacuous registration assertion.
    assert "morning_briefing" in kinds
    assert kinds == {"morning_briefing", "immunisation_overdue"}, (
        f"expected exactly the two registered kinds, got {sorted(kinds)}"
    )


def test_provenance_contract_BITES__the_gate_the_kind_passes_is_non_vacuous():
    """The kind is valid only because it declares 'provenance'. Prove
    that contract is real: a spec WITHOUT provenance is rejected. (If
    this did not raise, 'provenance in output_columns' above would be a
    vacuous assertion — the §D.1 'prove the gate bites' discipline.)"""
    with pytest.raises(ValueError, match="provenance"):
        TemplateSpec(
            id="_nonvacuity_probe",
            version=1,
            rpc_name="query_nonvacuity_probe",
            description="probe — must be rejected (no provenance column)",
            data_maturity="thin",
            params=[],
            output_columns=["patient_id", "next_dose_due"],  # NO provenance
        )
    # and the rpc_name contract bites too
    with pytest.raises(ValueError, match="rpc_name"):
        TemplateSpec(
            id="_nonvacuity_probe2",
            version=1,
            rpc_name="immunisations_overdue",  # missing 'query_' prefix
            description="probe — must be rejected (bad rpc_name)",
            data_maturity="thin",
            params=[],
            output_columns=["patient_id", "provenance"],
        )


def test_immunisation_overdue_is_derived_NOT_an_openloop():
    """Locked Decision 3 / §2.0: this is a STATELESS StandingQuery kind,
    not an OpenLoop. Structural proof: it is in the standing registry and
    has NO loop_kind / state machine coupling — it routes through the
    same chokepoint morning_briefing does (a derived cohort), not through
    the OpenLoop actions."""
    from ontology.enums.open_loop_enums import LoopKind
    sq = standing.get_standing("immunisation_overdue")
    # the kind discriminator is a briefing_items.kind string, NOT a LoopKind
    assert sq.kind not in {k.value for k in LoopKind}
    assert sq.kind == "immunisation_overdue"

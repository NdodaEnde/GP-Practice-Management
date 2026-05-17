"""
PR H — the Phase-4 close-out gate (the project's terminal artifact).

Mirrors `test_standing_queries.py` (the PR-D §2.4 mechanism) in shape: a
factored `_assert` helper raising named AssertionErrors; a build-failing
`_present` NECESSARY test; a parametrized `_non_vacuous` test removing
each load-bearing phrase and asserting the gate BITES. Permanent CI (NOT
RUN_INTEGRATION — reads two files, no DB; must always run).

NECESSARY-NOT-SUFFICIENT: failing the build on a physically absent
load-bearing sentence is the automatable NECESSARY condition. NOT
sufficient — discharge requires the named verifier's human read of the
actual prose against the **not-invertible-to-met standard**: no sentence,
*especially the §A quotation* (pulls out of context more easily than
authored prose), may be invertible by an adversarial reader quoting in
isolation into "Phase 4 met its safety constraint." "Discharged" must
NEVER be read as "the parser passed".

STRENGTHENING 1 (the §D.1 cure, mechanical): the §A quotation is not
trusted on author-care. The gate READS the live source
(`provision_briefing_demo.py` lines 70-78) and asserts the close-out's
quotation is byte-faithful to it — proven to bite by a case mutating the
quotation.

MEDIUM-INDEPENDENT BY DESIGN: the gate checks the load-bearing *words /
sentences* are present, normalised across the .py-docstring → .md-
blockquote boundary (strip blockquote markers, collapse whitespace) —
exactly as the byte-faithfulness check does. A raw-substring gate would
be brittle to markdown reflow, which is itself a vacuity risk: a gate
accidentally defeatable by re-wrapping a line is not a gate. (This was
caught on the gate's first run — the byte-faithfulness check, correctly
normalised, passed; the raw-substring prose checks did not. Fixed to the
code bar before the run was accepted; this gate has NO residue net.)

SCAFFOLDING-TO-THE-CODE-BAR (strengthening 5, inherited PR-F/PR-G note):
the assertion is the ONLY safeguard here; a first-run scaffolding failure
in this test is the one place "harmless because residue caught it" is not
harmless.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CLOSEOUT = _REPO_ROOT / "ONTOLOGY_PROACTIVE_LAYER_POSTMORTEM.md"
_QUOTE_SOURCE = _REPO_ROOT / "backend" / "scripts" / "provision_briefing_demo.py"
_QUOTE_LINES = (70, 78)  # 1-indexed; the PR-B pre-merge accepted-outcome


def _norm(t: str) -> str:
    """Medium-independent: strip line-leading markdown blockquote markers,
    collapse all whitespace. Compares the WORDS across the
    .py-docstring → .md-blockquote boundary. Idempotent."""
    t = re.sub(r"(?m)^\s*>\s?", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _section(norm_text: str, start_marker: str, end_marker: str) -> str:
    """Slice between section markers in the NORMALISED stream (markers
    are short, never wrapped, so they survive normalisation)."""
    i = norm_text.find(start_marker)
    if i == -1:
        raise AssertionError(f"close-out section missing: {start_marker!r}")
    j = norm_text.find(end_marker, i + len(start_marker))
    return norm_text[i: j if j != -1 else len(norm_text)]


def _source_quotation() -> str:
    lines = _QUOTE_SOURCE.read_text().splitlines()
    a, b = _QUOTE_LINES
    return _norm("\n".join(lines[a - 1: b]))


def _assert_phase4_closeout_artifacts(raw_text: str) -> None:
    """The load-bearing assertions, all medium-independent. Factored so
    the non-vacuity test can prove each BITES. Raises AssertionError
    naming the missing element. Accepts raw OR pre-normalised text
    (_norm is idempotent)."""
    text = _norm(raw_text)
    low = text.lower()

    # (i) §A — the formally-UNMET locked Decision-5 sentence, verbatim.
    if ("formally unmet and re-inherited to phase 5" not in low
            or "openable-vs-unresolvable contrast seen by a human"
            not in low):
        raise AssertionError(
            "§A: the locked 'formally UNMET … re-inherited to Phase 5' "
            "defining-constraint sentence is absent or altered"
        )

    # (ii) §A — the quotation BYTE-FAITHFUL to the live source file
    #      (strengthening 1: not 'present', faithful to source).
    if _source_quotation() not in text:
        raise AssertionError(
            "§A: the close-out's pre-merge quotation is NOT byte-faithful "
            "to provision_briefing_demo.py:70-78 (the most load-bearing "
            "sentence is not verified against live source — the §D.1 gap)"
        )

    # (iii) §C — conversion-instrumentation anchors (hardest-guarded).
    sec_c = _section(text, "## §C.", "## §D.").lower()
    for anchor in ("conversion instrumentation", "standingquery",
                   "briefing_items"):
        if anchor not in sec_c:
            raise AssertionError(
                f"§C conversion-instrumentation note missing anchor "
                f"{anchor!r}"
            )

    # (iv) §C — the shared-trigger sentence.
    if "one review" not in sec_c:
        raise AssertionError("§C shared-trigger missing 'one review'")
    if "project_phase3_tracked_deferrals" not in sec_c:
        raise AssertionError(
            "§C shared-trigger does not name the memory key "
            "'project_phase3_tracked_deferrals'"
        )

    # (v) §D — the credential, load-bearing-EQUAL of §A (strengthening 4).
    sec_d = _section(text, "## §D.", "## §E.").lower()
    if "prophylaxis" not in sec_d or "compound" not in sec_d:
        raise AssertionError(
            "§D: the method-COMPOUNDING evidence (PR F's scar → PR G's "
            "prophylaxis) is absent — §D is the credential, gate-enforced "
            "equal to §A, not a supporting section"
        )
    if "credential" not in sec_d:
        raise AssertionError("§D: the scar-is-the-credential claim is absent")

    # (vi) the not-invertible-to-met anchor.
    if "not that the defining constraint was satisfied" not in low:
        raise AssertionError(
            "the not-invertible-to-met statement is absent — 'closes' is "
            "not explicitly distinguished from 'the constraint was "
            "satisfied'"
        )


def test_phase4_closeout_artifacts_present():
    """THE gate (necessary, automatable, build-failing). NOT sufficient —
    the named verifier's not-invertible-to-met human read is the
    sufficiency."""
    assert _CLOSEOUT.is_file(), f"Phase-4 close-out missing: {_CLOSEOUT}"
    assert _QUOTE_SOURCE.is_file(), f"quote source missing: {_QUOTE_SOURCE}"
    _assert_phase4_closeout_artifacts(_CLOSEOUT.read_text())


@pytest.mark.parametrize("removed", [
    "formally UNMET and re-inherited to Phase 5",
    "openable-vs-unresolvable contrast seen by a human",
    "conversion instrumentation",
    "one review",
    "project_phase3_tracked_deferrals",
    "prophylaxis",
    "credential",
    "not that the defining constraint was satisfied",
])
def test_phase4_closeout_gate_is_non_vacuous(removed):
    """Remove each load-bearing phrase from the NORMALISED close-out and
    assert the gate BITES. A presence-gate that never fails when a
    sentence is absent is worthless. Permanent CI."""
    norm = _norm(_CLOSEOUT.read_text())
    assert re.search(re.escape(removed), norm, re.I), \
        f"precondition: {removed!r} present in the normalised close-out"
    tampered = re.sub(re.escape(removed), "", norm, flags=re.I)
    with pytest.raises(AssertionError):
        _assert_phase4_closeout_artifacts(tampered)


def test_byte_faithfulness_assertion_bites_when_quotation_mutated():
    """Strengthening 1, proven non-vacuous: mutating ONE word inside the
    §A quotation must make the byte-faithfulness assertion fire — proving
    it verifies against live source, not author-care. Operates on the
    normalised text (where the quotation is contiguous)."""
    norm = _norm(_CLOSEOUT.read_text())
    mutated = norm.replace(
        "no orphan was injected to complete the demo",
        "an orphan was injected to complete the demo",
        1,
    )
    assert mutated != norm, "precondition: the quotation phrase is present"
    with pytest.raises(AssertionError, match="byte-faithful"):
        _assert_phase4_closeout_artifacts(mutated)

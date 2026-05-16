"""
nl_query — Phase 3 PR C. The thinnest possible natural-language mapping
onto the CLOSED query-template registry. SHIPS DISABLED.

WHAT THIS IS (and is not):
  - It is a constrained intent classifier whose entire output domain is
    {registered template id} × {typed params} ∪ refusal. The model's
    only callable surface is a tool schema generated from
    `all_templates()` every call, so it cannot drift from the registry,
    cannot emit SQL, cannot free-form, cannot name an unregistered
    template. NL2SQL is rejected outright (umbrella design choice #4).
  - It adds NO new data path. A successful classification is handed to
    the SAME `run_template` + `resolve_provenance` chokepoint `/run`
    uses, so NL answers structurally inherit PR A/B's verifiable-
    provenance + openable/no_source/unresolvable contract — there is no
    other way for this module to reach data.
  - It does NOT validate params. The runner (ParamSpec.coerce_and_
    validate + run_template's unknown-param rejection) is the single
    validation authority; surfacing validator internals into the tool
    schema would be the exact registry-drift the design forbids.

THE SAFETY PROPERTY (the one thing the merge stands on):
  With `settings.NL_QUERY_LLM_ENABLED` False (the merge default — the
  env var is absent and no commit sets it), there is NO path here that
  constructs an LLM client or makes any outbound network call, and the
  caller's question — which CAN ITSELF BE PII (a patient name in "show
  me Jane Doe's medications") — goes NOWHERE. There is NO scrubber and
  this module does not pretend one: a reliable name-stripper is itself
  unsolved, and claiming it would be the Phase-2 fake-property anti-
  pattern. The disabled-default IS the PII safety boundary — flag off ⇒
  the text never leaves the process ⇒ nothing to scrub. Enabling is a
  deliberate operator governance act (provider authorisation), never a
  code change.

  Structural enforcement: the provider import lives ONLY inside
  `_client()`; `classify_question`'s FIRST action is the flag gate,
  returning a hard refusal BEFORE `_client()`, before any import, before
  any network. Proven un-mockably by the named CI gate in
  tests/test_nl_query.py (three independent traps: a `_client` sentinel,
  a `socket.connect` trap, an `__import__` trap — all must stay silent
  with the flag off, on the real path, with a deliberately PII-bearing
  input).

WHAT IS *NOT* VERIFIED AT MERGE (unsoftened, same as the plan's §4/§7):
  The output-domain constraint above is proven. Whether the classifier
  picks the *right* registered template for a given real phrasing —
  mapping correctness — is ENTIRELY UNVERIFIED at merge. A wrong
  registered template is still runner-validated, still provenance-
  resolved, still looks authoritative: that misclassification is INSIDE
  the safety envelope of every structural gate and is invisible to all
  of them. "Constrained to the closed enum" means output-domain-
  constrained, NEVER mapping-correct. Accuracy is knowable only via the
  opt-in eval once a provider is authorised; mocked tests prove WIRING,
  not intelligence.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# NOTE: NO provider import at module scope. `from openai import OpenAI`
# lives only inside `_client()` (house pattern: semantic_search._client).
# A future refactor moving it here would silently defeat default-off;
# the __import__-trap in the named CI gate fails the build if it does.

REFUSE_TOOL = "refuse"  # synthetic in-band decline so the model is
                        # never forced to pick when it should not.

_REASON_DISABLED = "nl_disabled"
_REASON_OUT_OF_SET = "out_of_set"
_REASON_LOW_CONFIDENCE = "low_confidence"

_llm_client = None  # lazy singleton; constructed ONLY when enabled


@dataclass(frozen=True)
class NLRefusal:
    """A hard refusal. ALWAYS carries the answerable list — "refuse +
    what IS answerable, never a guess" is structural, not optional."""

    reason: str            # nl_disabled | out_of_set | low_confidence
    message: str
    answerable: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": "refused",
            "reason": self.reason,
            "message": self.message,
            "answerable": self.answerable,
        }


@dataclass(frozen=True)
class NLClassification:
    """A successful mapping to ONE registered template + raw params.
    Params are passed through UNINTERPRETED — the runner validates."""

    template_id: str
    params: Dict[str, Any]
    confidence_note: Optional[str] = None


def _json_type(py_type: type) -> str:
    return {int: "integer", float: "number", bool: "boolean",
            str: "string"}.get(py_type, "string")


def _answerable() -> List[Dict[str, Any]]:
    """The registry projection — IDENTICAL to what GET
    /api/query/templates exposes. Built from all_templates() so it
    cannot drift; never surfaces `validator` (a callable, unserialisable
    — confirmed for all 12 params across all 7 templates)."""
    from ontology.query import all_templates

    out: List[Dict[str, Any]] = []
    for t in all_templates():
        out.append({
            "id": t.id,
            "description": t.description,
            "params": [
                {
                    "name": p.name,
                    "type": _json_type(p.py_type),
                    "required": p.required,
                    "default": p.default,
                }
                for p in t.params
            ],
        })
    return out


def build_tool_schema() -> List[Dict[str, Any]]:
    """One constrained tool per registered template + the synthetic
    `refuse`. The tool set IS the registry, regenerated each call — it
    structurally cannot list an unregistered template nor omit a
    registered one, and exposes ONLY the serialisable projection (never
    a validator). This is the anti-drift mechanism; the
    tool-schema-is-exactly-the-registry CI gate asserts it."""
    tools: List[Dict[str, Any]] = []
    for t in _answerable():
        props: Dict[str, Any] = {}
        required: List[str] = []
        for p in t["params"]:
            props[p["name"]] = {
                "type": p["type"],
                "description": (
                    f"{p['name']} "
                    + ("(required)" if p["required"]
                       else f"(optional, default {p['default']!r})")
                ),
            }
            if p["required"]:
                required.append(p["name"])
        tools.append({
            "type": "function",
            "function": {
                "name": t["id"],
                "description": t["description"],
                "parameters": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                    "additionalProperties": False,
                },
            },
        })
    tools.append({
        "type": "function",
        "function": {
            "name": REFUSE_TOOL,
            "description": (
                "Decline. Use this when the question does not clearly "
                "map to exactly one of the templates above, or is "
                "ambiguous, or asks for something not registered. "
                "Refusing is correct and expected — never approximate "
                "to the nearest template."
            ),
            "parameters": {"type": "object", "properties": {},
                           "additionalProperties": False},
        },
    })
    return tools


def _flag_enabled() -> bool:
    # Imported here (not module scope) so the flag is read live and the
    # test can monkeypatch settings.NL_QUERY_LLM_ENABLED.
    from app.core.config import settings
    return bool(getattr(settings, "NL_QUERY_LLM_ENABLED", False))


def _client():
    """Lazy singleton. Mirrors semantic_search._client() EXACTLY, with
    the flag re-check FIRST (defence in depth: even a direct call
    refuses with the flag off — the provider import is never reached).
    `from openai import OpenAI` is inside this function, never module
    scope."""
    global _llm_client
    if not _flag_enabled():
        raise RuntimeError(
            "nl_query._client() called with NL_QUERY_LLM_ENABLED off — "
            "refusing to construct an LLM client"
        )
    if _llm_client is None:
        from openai import OpenAI  # provider import — gated, lazy
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY missing — cannot run NL classification"
            )
        _llm_client = OpenAI(api_key=api_key)
    return _llm_client


def _invoke(client, messages: List[Dict[str, Any]],
            tools: List[Dict[str, Any]], model: str) -> Any:
    """The ONLY provider-specific call shape. Isolated so the
    §5-deferred provider swap touches one function, not the classifier
    logic. `tool_choice="required"` forces selection from the closed
    set (the model must pick a registered template or `refuse` — it
    cannot free-form). temperature=0 for determinism; small max_tokens
    (we only need a tool call, never prose)."""
    return client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice="required",
        temperature=0,
        max_tokens=256,
    )


_SYSTEM = (
    "You map a clinician's question to EXACTLY ONE of the provided "
    "tools (each is a registered query template) and its typed "
    "parameters, or call `refuse`. You MUST call a tool. You may not "
    "answer in prose, write SQL, or invent a template. If the question "
    "does not clearly and unambiguously map to one template — including "
    "near-misses that differ from a template by a clinically material "
    "term — call `refuse`. Refusing is correct; approximating to the "
    "nearest template is a serious error."
)


def classify_question(
    question: str,
    *,
    model: Optional[str] = None,
) -> NLRefusal | NLClassification:
    """Map a question to a registered template, or refuse.

    LINE-1 SAFETY GATE: the flag check is the first thing this function
    does. With the flag off it returns a hard refusal BEFORE `_client()`,
    before any provider import, before any network — so the (possibly
    PII-bearing) question never leaves the process. Everything below the
    gate is unreachable when disabled.
    """
    # ── THE GATE (must remain the first executable statement) ──────────
    if not _flag_enabled():
        return NLRefusal(
            reason=_REASON_DISABLED,
            message=(
                "Natural-language queries are disabled. No text was sent "
                "anywhere. Use one of the answerable query shapes "
                "directly via /api/query/run."
            ),
            answerable=_answerable(),
        )

    # ── Below here only runs when an operator has deliberately enabled
    #    the LLM (governance act). ───────────────────────────────────────
    tools = build_tool_schema()
    registered_ids = {t["function"]["name"] for t in tools}
    client = _client()
    resp = _invoke(
        client,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": question},
        ],
        tools=tools,
        model=model or os.getenv("NL_QUERY_MODEL", "gpt-4o-mini"),
    )

    # Parse the tool call defensively — anything unexpected is a REFUSAL,
    # never a guess.
    try:
        choice = resp.choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None) or []
    except (AttributeError, IndexError, TypeError):
        tool_calls = []

    if not tool_calls:
        return NLRefusal(
            _REASON_LOW_CONFIDENCE,
            "Could not map the question to a query shape.",
            _answerable(),
        )

    call = tool_calls[0]
    name = getattr(getattr(call, "function", None), "name", None)

    if name == REFUSE_TOOL or name not in registered_ids:
        # Includes: explicit refuse, an unknown/hallucinated tool name,
        # or REFUSE_TOOL. Never executed; always the answerable list.
        return NLRefusal(
            _REASON_OUT_OF_SET,
            "The question does not map to a registered query shape.",
            _answerable(),
        )

    raw_args = getattr(getattr(call, "function", None), "arguments", "") or "{}"
    try:
        params = json.loads(raw_args)
        if not isinstance(params, dict):
            raise ValueError("arguments not an object")
    except (json.JSONDecodeError, ValueError):
        return NLRefusal(
            _REASON_LOW_CONFIDENCE,
            "The mapped parameters were not well-formed.",
            _answerable(),
        )

    # Pass through UNINTERPRETED. The runner validates every param
    # (ParamSpec) and rejects unknown ones; this module deliberately
    # does not re-implement validation.
    return NLClassification(template_id=name, params=params)

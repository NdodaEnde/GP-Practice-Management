"""
Shared caller-input validators for PR B briefing templates.

Defence in depth: the backing RPCs parameterise everything (no string
interpolation reaches SQL), but the registry validates at the edge so
malformed / injection-shaped input fails closed before the RPC is ever
called — and the *same* rule is applied everywhere a given param
appears, which is itself a safety property (one patient-id rule, not
six subtly different ones).
"""

from __future__ import annotations

_ID_BANNED = set("%_\\'\";")


def validate_patient_id(v: str) -> None:
    s = (v or "").strip()
    if not s:
        raise ValueError("patient_id must be non-empty")
    if len(s) > 64:
        raise ValueError("patient_id too long (max 64 chars)")
    if any(c in s for c in _ID_BANNED):
        raise ValueError("patient_id contains illegal characters")


def validate_limit(v: int) -> None:
    if v < 1 or v > 500:
        raise ValueError("limit must be between 1 and 500")


def validate_days(v: int) -> None:
    # 1 day .. ~27 years; a non-positive window is a caller bug.
    if v < 1 or v > 10000:
        raise ValueError("day window must be between 1 and 10000")


def validate_test_code(v: str) -> None:
    s = (v or "").strip()
    if not s:
        raise ValueError("test_code must be non-empty")
    if len(s) > 32:
        raise ValueError("test_code too long (max 32 chars)")
    if any(c in s for c in _ID_BANNED):
        raise ValueError("test_code contains illegal characters")


def validate_min_value(v: float) -> None:
    if v < 0:
        raise ValueError("min_value must be >= 0")

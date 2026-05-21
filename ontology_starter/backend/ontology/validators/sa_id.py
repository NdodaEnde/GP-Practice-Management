"""
SA ID number validation.

The 13-digit SA ID number encodes date of birth, sex, citizenship status,
and a Luhn checksum. Validating it properly gives the platform three
free things:

  1. A high-confidence cross-check on patient-reported DOB and sex.
     When the ID number's encoded DOB disagrees with the captured DOB,
     surface that as a validation discrepancy — it's almost always a
     transcription error from the receptionist.

  2. A strong signal for entity resolution. ID number exact-match is
     the gold standard for "is this the same patient" in SA.

  3. A check on data quality at intake. Invalid checksums catch fat-finger
     errors before they propagate into the patient record.

Format: YYMMDD SSSS C A Z
  YYMMDD = date of birth
  SSSS   = sequence number; 0000-4999 = female, 5000-9999 = male
  C      = citizenship: 0 = SA citizen, 1 = permanent resident
  A      = historically race indicator; now always 8 or 9
  Z      = Luhn checksum
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass(frozen=True)
class SAIDDecoded:
    """The structured information encoded in an SA ID number."""

    date_of_birth: date
    sex: str  # "M" or "F"
    is_sa_citizen: bool
    raw: str


class InvalidSAIDError(ValueError):
    """Raised when an SA ID number fails validation."""


def _luhn_check(number: str) -> bool:
    """Standard Luhn algorithm — the same one used by credit cards.

    SA ID numbers use a variant: digits at even positions (1-indexed from
    the right, excluding the check digit) are doubled, and if the doubled
    value is two digits the digits are summed.
    """
    digits = [int(c) for c in number]
    check_digit = digits[-1]
    body = digits[:-1]

    total = 0
    # Right-to-left, starting at position 1
    for i, d in enumerate(reversed(body), start=1):
        if i % 2 == 1:
            doubled = d * 2
            total += doubled if doubled < 10 else doubled - 9
        else:
            total += d

    computed_check = (10 - (total % 10)) % 10
    return computed_check == check_digit


def _infer_century(yy: int, today: Optional[date] = None) -> int:
    """SA ID numbers use a 2-digit year. Infer the century by assuming
    the person is alive and under 100 years old.

    A YY of 26 in 2026 could mean 1926 (100 years old) or 2026 (newborn).
    We pick the century that makes the person's age fall in [0, 100).
    """
    today = today or date.today()
    current_yy = today.year % 100
    current_century = today.year - current_yy

    # Try this century first
    candidate_this = current_century + yy
    if candidate_this <= today.year and today.year - candidate_this < 100:
        return current_century

    # Otherwise it's the previous century
    return current_century - 100


def validate_and_decode_sa_id(
    id_number: str,
    *,
    today: Optional[date] = None,
) -> SAIDDecoded:
    """Validate an SA ID number and return the structured info it encodes.

    Raises InvalidSAIDError with a clear message if anything is wrong —
    the message should be safe to surface to the user (e.g. 'Invalid
    checksum' or 'Date of birth is not a real date').

    Strips whitespace; otherwise the input must be exactly 13 digits.
    """
    if id_number is None:
        raise InvalidSAIDError("ID number is required.")

    cleaned = "".join(id_number.split())
    if not cleaned.isdigit():
        raise InvalidSAIDError("ID number must contain only digits.")
    if len(cleaned) != 13:
        raise InvalidSAIDError(f"ID number must be 13 digits, got {len(cleaned)}.")

    yy, mm, dd = int(cleaned[0:2]), int(cleaned[2:4]), int(cleaned[4:6])
    century = _infer_century(yy, today=today)
    try:
        dob = date(century + yy, mm, dd)
    except ValueError as exc:
        raise InvalidSAIDError(f"Encoded date of birth is not a valid date: {exc}") from exc

    sequence = int(cleaned[6:10])
    sex = "F" if sequence < 5000 else "M"

    citizenship_digit = int(cleaned[10])
    if citizenship_digit not in (0, 1):
        raise InvalidSAIDError("Citizenship digit must be 0 (SA) or 1 (permanent resident).")
    is_sa_citizen = citizenship_digit == 0

    if not _luhn_check(cleaned):
        raise InvalidSAIDError("Checksum does not match — ID number is invalid.")

    return SAIDDecoded(
        date_of_birth=dob,
        sex=sex,
        is_sa_citizen=is_sa_citizen,
        raw=cleaned,
    )


def is_valid_sa_id(id_number: str) -> bool:
    """Boolean convenience wrapper. Use the full decoder when you need
    the cross-check fields."""
    try:
        validate_and_decode_sa_id(id_number)
        return True
    except InvalidSAIDError:
        return False

"""
South African healthcare enums.

These are not generic. They reflect the categorical fields that actually
appear in SA medical aid forms, SA Stats Council questionnaires, and HPCSA
practice systems. If you're tempted to make these "international", resist —
the abstraction earns no business value and adds maintenance cost.
"""

from enum import Enum


class BiologicalSex(str, Enum):
    """Biological sex as recorded for clinical purposes.

    Deliberately separate from gender identity (which is a different property
    if and when you model it). Most SA medical aid claim forms still require
    this field as M/F because clinical reference ranges and dosing depend on it.
    """

    MALE = "M"
    FEMALE = "F"
    INTERSEX = "I"
    UNKNOWN = "U"


class Title(str, Enum):
    """Common SA titles. Free text would be fine but enums make the search
    facet cleaner and prevent variant spellings ('Dr.', 'DR', 'doctor')."""

    MR = "Mr"
    MRS = "Mrs"
    MS = "Ms"
    MISS = "Miss"
    DR = "Dr"
    PROF = "Prof"
    REV = "Rev"
    ADV = "Adv"
    OTHER = "Other"


class PopulationGroup(str, Enum):
    """Optional self-declared population group as used by Stats SA.

    Captured only when the patient volunteers it; never inferred. Useful
    for epidemiology, equity reporting, and (importantly) for medical aid
    schemes that require it for BEE-linked benefit reporting.
    """

    BLACK_AFRICAN = "black_african"
    COLOURED = "coloured"
    INDIAN_ASIAN = "indian_asian"
    WHITE = "white"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class HomeLanguage(str, Enum):
    """The 12 official SA languages (incl. SASL) plus 'other'."""

    AFRIKAANS = "af"
    ENGLISH = "en"
    ISINDEBELE = "nr"
    ISIXHOSA = "xh"
    ISIZULU = "zu"
    SEPEDI = "nso"
    SESOTHO = "st"
    SETSWANA = "tn"
    SISWATI = "ss"
    TSHIVENDA = "ve"
    XITSONGA = "ts"
    SASL = "sasl"           # SA Sign Language
    OTHER = "other"


class PatientStatus(str, Enum):
    """Lifecycle status of a patient record.

    Distinct from the soft-delete flag — a patient can be 'inactive'
    (no longer seen at this practice) without being deleted.
    """

    ACTIVE = "active"
    INACTIVE = "inactive"        # no recent visits, no transfer recorded
    TRANSFERRED_OUT = "transferred_out"
    DECEASED = "deceased"
    MERGED = "merged"            # this record was merged into another (ER outcome)


class IdentifierType(str, Enum):
    """Types of identity documents accepted in SA primary care."""

    SA_ID = "sa_id"                  # 13-digit SA ID number
    PASSPORT = "passport"
    REFUGEE_ID = "refugee_id"        # Section 22/24 permit
    ASYLUM_SEEKER = "asylum_seeker"
    BIRTH_CERTIFICATE = "birth_certificate"  # for minors without ID yet
    UNKNOWN = "unknown"              # registered without verified ID (e.g. emergency)

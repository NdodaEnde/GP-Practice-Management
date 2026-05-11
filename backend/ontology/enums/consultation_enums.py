"""
Consultation ontology enums.

These describe the categorical fields of a clinical encounter as they
actually appear in SA primary care. SA practice differs from US/UK norms
in ways worth flagging here:

  - Home visits are common (chronic-disease patients, post-discharge,
    rural patches where transport is the patient's bottleneck) — they're
    a normal encounter type, not a special case.

  - Telehealth became broadly legal after HPCSA's 2020 guidance update.
    It's now a separate encounter type rather than a flag on an in-person
    encounter, because billing codes differ and the medical-aid claim
    path is different.

  - Vaccination is its own type because SA Department of Health
    immunisation programmes (EPI childhood schedule, COVID, flu, HPV
    school programmes) often run through GP practices as standalone
    encounters with minimal clinical narrative.
"""

from enum import Enum


class EncounterType(str, Enum):
    """What kind of clinical encounter this is.

    Drives billing rules, the documentation template surfaced in the UI,
    and which open-loop detectors fire after promotion.
    """

    CONSULTATION = "consultation"      # standard general-practice visit
    FOLLOW_UP = "follow_up"            # explicit follow-up on a prior visit/condition
    EMERGENCY = "emergency"            # acute presentation, walk-in or after-hours
    TELEHEALTH = "telehealth"          # remote (video/phone), HPCSA-compliant
    HOME_VISIT = "home_visit"          # doctor sees patient at their residence
    PROCEDURE = "procedure"            # minor procedure (suturing, biopsy, IUD)
    SCREENING = "screening"            # asymptomatic check (cervical, prostate, BP days)
    VACCINATION = "vaccination"        # immunisation-only encounter


class EncounterSetting(str, Enum):
    """Where the encounter physically took place.

    Distinct from EncounterType: a TELEHEALTH encounter has setting REMOTE,
    a HOME_VISIT has setting PATIENT_HOME, an in-practice CONSULTATION
    has setting PRACTICE. The setting is what the billing system needs;
    the type is what the clinician thinks of it as.
    """

    PRACTICE = "practice"              # the doctor's rooms
    HOSPITAL = "hospital"              # admitting / ward round / consult-in
    CLINIC = "clinic"                  # community health centre / external clinic
    PATIENT_HOME = "patient_home"      # home visit
    REMOTE = "remote"                  # video / phone (telehealth)


class ConsultationStatus(str, Enum):
    """Lifecycle of a consultation record.

    PLANNED → IN_PROGRESS → COMPLETED is the happy path. CANCELLED and
    NO_SHOW are operational outcomes that still occupy a slot but don't
    represent a clinical encounter — they exist as records so the
    appointment grid stays honest and so cancellation patterns can be
    analysed.
    """

    PLANNED = "planned"                # appointment scheduled, not yet started
    IN_PROGRESS = "in_progress"        # the doctor is currently seeing the patient
    COMPLETED = "completed"            # encounter finished, notes captured
    CANCELLED = "cancelled"            # cancelled before the visit (by either party)
    NO_SHOW = "no_show"                # patient didn't arrive; clinician charted nothing

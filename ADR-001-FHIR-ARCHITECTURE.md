# ADR-001: FHIR architecture — hub-and-spoke, internal model canonical

**Status:** Accepted (2026-05-21)
**Context owner:** principal

## Decision

We do **not** store FHIR. The **internal relational model** (`patients`,
`diagnoses`, `vitals`, `prescriptions`, `encounters`, …) is the **single source
of truth**. **FHIR is the interchange contract at the system edges**, both
directions:

```
                    ┌──────────────────────────────┐
 digitisation ────▶ │  INTERNAL CANONICAL MODEL      │ ──▶ FHIR EXPORT  ─▶ client EHR   (egress, built)
 (extraction        │  (relational; source of truth) │
  schemas)          │                                │ ◀─ FHIR INGEST  ◀─ client EHR   (ingress, future)
                    └───────────────┬────────────────┘
                                    ▼
                              INTELLIGENCE  (reads the internal model)
```

- **Egress** (Essential / Digitisation → client EHR): internal record →
  `fhir_export.py` → FHIR R4 bundle. **Built and validated** (see below).
- **Ingress** (client → us, for Intelligence): client FHIR → a future ingest
  adapter → internal model. **Not built** — build when the first
  Intelligence-on-client-data engagement is real.
- **Intelligence reads only the internal canonical model**, so it is decoupled
  from the data's origin (digitisation today, client FHIR feed tomorrow).

## Why (not a FHIR-native database)

FHIR is an interchange format, not a storage format. Major EHRs (Epic, Cerner)
keep internal models and expose/accept FHIR at the edges. A FHIR-native rebuild
buys little and costs a lot. Keeping the relational model canonical:

- avoids a re-platform,
- keeps compliance a property of the **adapters** (export validates to R4;
  ingest parses R4), not the database,
- lets Intelligence run on one stable internal shape.

## Invariant this depends on

The internal model must be a **superset** of the FHIR fields we care about, so
neither adapter is lossy. (We found and fixed real export-side loss:
DS-EXPORT-2 contact details, DS-EXPORT-3 medical aid, DS-EXPORT-5 vitals.)
Anything clinically meaningful that FHIR can carry must have a home in our
schema.

## Compliance status (egress adapter)

Verified with the **official HL7 FHIR validator** (`validator_cli.jar`,
`-version 4.0.1`) against a representative export bundle:

- **Before hardening:** 53 errors (was actually emitting R5 under `fhir_r4`;
  missing `fullUrl`; vitals missing category/effective; BP not a panel; ICD-10
  display mismatch).
- **After:** **0 errors, 10 warnings** (warnings are best-practice only —
  resource narrative, Observation performer). The bundle is **FHIR R4
  conformant**.
- Library pinned to R4B (`fhir.resources.R4B.*`); BP emitted as a 85354-9 panel
  with components; ICD-10 display omitted (code-only, text in `code.text`).

Re-run the validator after any change to `fhir_export.py`:
```
java -jar validator_cli.jar <bundle>.json -version 4.0.1
```

## Open follow-ups (named, not blocking)

- **US Core profiles**: the `digitisation_export_fhir` capability advertises
  "US Core profile validation" — we validate against **base R4**, not US Core
  (a US IG; SA relevance is questionable). Either implement US Core validation
  or correct the capability copy. (US Core would add must-support + slicing
  constraints; base R4 conformance is the right first bar for SA EHR interop.)
- **Professional tier** has no FHIR export wired yet (same tables, just needs
  the capability grant + an EHR-side endpoint reusing `fhir_export.py`).
- **Outer batch wrapper**: the worker nests per-document bundles inside an outer
  `batch` Bundle; for distribution a single `collection` (or one bundle per
  patient) is cleaner. Per-document bundle is now conformant; the wrapper is a
  separate structural decision.
- **Ingress adapter**: FHIR → internal model, for Intelligence on client data.
- **Terminology**: NAPPI uses a custom system (not HL7-official); SNOMED not
  used. Acceptable for now; revisit if a client requires coded terminology
  binding validation.

# Ontology starter — Patient as the first object type

This is the spine you start growing. Five files do real work; the rest is
structure that lets you grow into the rest of the ontology cleanly.

## What's here

```
backend/ontology/
    __init__.py                   Public surface: import Patient, Prop, etc.
    base.py                       OntologyObject, PIILevel, SearchBehaviour, Prop()
    objects/
        patient.py                The first deeply-modelled object type
    enums/
        patient_enums.py          SA-specific enums (sex, language, ID type, etc.)
    validators/
        sa_id.py                  SA ID number validation + DOB/sex decoding
    links/
        registry.py               Declared relationships between object types
    actions/
        promote_document.py       The platform's highest-stakes mutation,
                                  modelled as a first-class Action.
```

## Verify it runs

```bash
cd backend
pip install pydantic
python3 -c "
from datetime import date, datetime
from uuid import uuid4
from ontology import Patient
from ontology.enums.patient_enums import BiologicalSex, IdentifierType

p = Patient(
    id=uuid4(),
    practice_id=uuid4(),
    created_at=datetime.utcnow(),
    updated_at=datetime.utcnow(),
    first_name='Thandi',
    surname='Mthembu',
    date_of_birth=date(1985, 3, 14),
    biological_sex=BiologicalSex.FEMALE,
    identifier_type=IdentifierType.SA_ID,
    identifier_number='8503140001087',
)
print(p.display_name())
print(f'Age: {p.age_in_years()}')
"
```

You should see: `Mthembu, Thandi (1985-03-14)` and the age.

## What to do next, in order

### Day 1: drop it in, refactor one endpoint

Copy `backend/ontology/` into your real codebase. Pick the GET-patient
endpoint that returns the most properties. Replace its response model
with `Patient`. Ship it. Behaviour unchanged; the ontology is now load-
bearing for one read path.

### Day 2-3: codegen the TypeScript types

Add `/api/ontology/schema` that returns `Patient.ontology_schema()`. Write
a script that hits it and generates TypeScript interfaces. Replace one
frontend component's hand-written `PatientProps` type with the generated
one. Now any change to `Patient` propagates to the frontend automatically.

### Week 1: write Document

Copy `objects/patient.py` to `objects/document.py`. Same shape. Properties
to model: `original_filename`, `upload_source`, `mime_type`, `page_count`,
`extracted_text` (search=SEMANTIC), `extraction_confidence`, `validation_status`,
`promoted_at`, `promoted_to_patient_id` (link_to="Patient"), `source_practice_id`.
Skip the SA-specific validators here — Document is generic.

### Week 2: write Consultation

Copy again. Properties: `patient_id` (link_to="Patient"), `consultation_date`,
`practising_doctor_id`, `chief_complaint` (search=SEMANTIC), `history`
(search=SEMANTIC), `examination_findings`, `assessment`, `plan`, `duration_minutes`,
`billing_codes`. PII level HIGH.

### Week 3: wire up the action executor

The `PromoteDocumentToPatientRecord` action in this starter is illustrative.
Now make it real: write the executor that takes an action, evaluates
preconditions against DB state, runs effects in a transaction, writes the
audit log row. One executor serves all future actions.

### Week 4: refactor your existing promotion endpoint through the executor

Same behaviour as before, but now everything funnels through the audited
action path. Build the audit-history view on the patient record. This is
the moment the "audit-ready by default" story becomes real.

## Patterns to keep, things to avoid

**Keep:**

- Every property declared with `Prop(...)` carrying PII level, FHIR mapping,
  and search behaviour. The metadata is the point.
- Class-level `__display_template__`, `__fhir_resource__`, `__pii_level__`.
- Domain validators in `validators/` with clear, user-safe error messages.
- Cross-field validation in `@model_validator` (like the SA ID DOB check).
- Links declared in one registry file, not scattered as foreign keys.
- Actions with declarative `preconditions()`, `effects()`, `reversal()`.

**Avoid:**

- Declaring more than 3 object types in week 1. Three deep beats fourteen
  shallow.
- Mutating ontology objects directly in endpoint handlers. All mutations
  go through actions, even simple ones — the audit trail is the payoff.
- Making `Patient` extensible for "international use cases". You're
  building for SA primary care. The abstraction earns no business value.
- Adding fields just because they exist in FHIR. Only model what your
  platform actually uses or surfaces. FHIR is the export format, not the
  ontology shape.

## Questions you'll hit

**"Why not just use SQLAlchemy models as the ontology?"**

Because SQLAlchemy models describe storage, not meaning. The ontology
carries PII tags, FHIR mappings, search behaviour, display semantics,
and link metadata — none of which belong on a storage layer. The mapper
between SQLAlchemy and ontology objects is a thin function, written once
per object type.

**"Where do I put business rules?"**

Three places, in order of preference:
1. Validators on the ontology object (for invariants: SA ID must
   cross-check, deceased_date must be after birth, etc.)
2. Preconditions on actions (for "this mutation only valid when...")
3. Effects on actions (for "when X happens, also do Y")

If a rule doesn't fit one of these three, it's probably a UI concern.

**"What about performance? Querying via the ontology sounds heavy."**

The ontology objects are read-shaped projections, hydrated from SQL.
Your queries still hit indexed tables. The ontology adds zero runtime
cost — it adds compile-time structure.

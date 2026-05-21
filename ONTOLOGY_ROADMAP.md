# Ontology Roadmap

You make complete sense, and this is the right question to be asking — because the gap between "I understand the ontology concept" and "I have a working ontology in production" is where most platforms either become real or quietly die as a collection of half-built features. Let me give you an honest roadmap.

Before I lay it out, one framing point that will save you from a common trap: **the ontology is not a project you finish, it's a spine you grow.** If you treat it as a 12-week migration where you stop shipping features and rebuild your data model, you'll lose momentum and probably lose the company. If you treat it as an architectural commitment that accretes one object type and one action at a time alongside normal feature work, you'll have a load-bearing ontology in 4-6 months without ever having a "we're not shipping this quarter" moment.

The roadmap below assumes the second approach.

---

## Phase 0: Decide what you're actually building (1 week, mostly thinking)

This phase has no code. It's the part everyone wants to skip and it's the part that determines whether the next four months pay off or not.

Three deliverables:

*A written ontology charter.* One page. What is the ontology *for* in your specific platform? Mine would say something like: "A typed, queryable, auditable model of clinical reality across a practice, designed to make every document's contribution to a patient's record traceable, every clinical decision supportable by evidence, and every query answerable in the language clinicians actually use." If you can't write this sentence, you don't yet know what you're building.

*An inventory of the implicit ontology you already have.* Open your codebase and list every domain concept that appears. Patient, Document, Consultation, Diagnosis, Medication, Vitals, LabResult, Practice, Doctor, MedicalAidScheme. For each, write down: where its schema currently lives (which Pydantic model, which SQLAlchemy table, which TypeScript interface), where its mutation logic lives (which endpoints, which workers), and where its consumers are (UI components, exports, search). You're mapping the territory before you redraw it.

*A "first three" decision.* Pick the three object types that will be the ontology's beachhead. They should be: (a) central to your platform's value proposition, (b) actively being worked on so the refactor compounds with feature work, and (c) connected by the most important relationships. For your platform, this is almost certainly Patient, Document, and Consultation — they're the spine of everything else and your highest-traffic objects.

Why this phase matters: the ontology is going to become the source of truth for these object types. If you start building it without knowing which three you're starting with, you'll either try to do all of them at once (and fail) or do them in the wrong order (and have to redo work).

---

## Phase 1: Plant the spine (weeks 1-3)

Goal: a single declarative source of truth for your first three object types, consumed by both backend and frontend, with zero behaviour change for users.

This phase is deliberately invisible to customers. You're moving deck chairs into a better arrangement so that everything you build after this moves faster.

*Week 1: The ontology package.*

Create `backend/ontology/` as a new Python package. Inside it, define `objects/patient.py`, `objects/document.py`, `objects/consultation.py`. Each file declares the object type as a Pydantic model with property metadata richer than what you have today — every property tagged with its PII classification, its FHIR mapping, its display label, its search behaviour, its validation rules.

Example shape (this is not literal code, just the texture):

```
class Patient(OntologyObject):
    __display_template__ = "{surname}, {first_name} ({date_of_birth})"
    __fhir_resource__ = "Patient"
    __pii_level__ = "high"

    first_name: str = Property(pii=True, fhir="name.given")
    surname: str = Property(pii=True, fhir="name.family", searchable=True)
    date_of_birth: date = Property(pii=True, fhir="birthDate", searchable=True)
    sa_id_number: Optional[str] = Property(pii=True, validator=validate_sa_id)
    medical_aid_scheme_id: Optional[UUID] = Property(link_to="MedicalAidScheme")
    ...
```

The point isn't the syntax — pick whatever Pydantic patterns suit your codebase. The point is that every property's *meaning* (not just its type) lives in one place.

Your existing SQLAlchemy models stay where they are. The ontology objects are a *layer above* the persistence layer, not a replacement for it. Add a thin mapper that hydrates ontology objects from DB rows.

*Week 2: The links registry.*

Create `backend/ontology/links.py` and declare the link types between your first three objects:

```
Document --extracts_data_for--> Patient (with confidence_score, validation_status)
Document --extracts_data_for--> Consultation (with confidence_score)
Patient --has_consultation--> Consultation (cardinality: 1:N)
Consultation --documented_by--> Document (cardinality: N:M)
```

This is a declarative registry — not new tables, not new code paths. It describes the relationships that *already exist* in your database, but explicitly, with metadata, in one place.

Add a `traverse()` helper that knows how to walk these links efficiently. For now it just compiles down to SQL joins, but it speaks in ontology terms: `patient.traverse("has_consultation").filter(date__gte=...)`. Build it minimal, only what your first three queries need.

*Week 3: The codegen step.*

Generate TypeScript types from the ontology objects. This is the move that makes the ontology visible to your frontend. Whenever the backend ontology changes, the frontend types update. No more drift between FastAPI response schemas and React component prop types.

Add a `/api/ontology/schema` endpoint that returns the ontology as JSON. Your frontend can introspect it at runtime for things like form generation, validation, and display labels.

*End-of-phase check:* you should be able to demonstrate that adding a new property to Patient requires editing exactly one file, and the change propagates to backend serialisation, frontend types, search indexing, and FHIR export automatically. If it still requires touching five files, the ontology hasn't taken hold yet.

---

## Phase 2: Make actions first-class (weeks 4-6)

Goal: every mutation to your first three object types flows through a named, audited, declarative action. This is the phase that pays off in audit-readiness, ER capability, and clinical safety, and it's where the ontology starts feeling load-bearing.

*Week 4: Pick the first action and model it deeply.*

I'd start with `PromoteDocumentToPatientRecord` because it's your highest-stakes mutation and you already have most of the logic for it — you just haven't named it as a coherent unit.

Create `backend/ontology/actions/promote_document.py`:

```
class PromoteDocumentToPatientRecord(Action):
    document_id: UUID
    target_patient_id: UUID
    confirmed_by_user_id: UUID
    confirmation_evidence: PatientMatchConfirmation

    def preconditions(self):
        - document.validation_status == "validated"
        - target_patient exists and belongs to actor's practice
        - confirmation_evidence is recent and not reused

    def effects(self):
        - Create Diagnosis objects from extracted diagnoses
        - Create Medication objects from extracted medications
        - Link all to target_patient and to a Consultation
        - Mark document.promoted_at, document.promoted_to_patient_id
        - Write audit log entry with full context

    def reversal(self):
        - Soft-delete created Diagnosis/Medication objects
        - Unlink document, mark as unpromoted
        - Audit log entry for the reversal
```

Refactor your existing endpoint to route through this action. Same behaviour, same outcomes, but now it's a named thing with declared preconditions, declared effects, and an audit trail that captures *what action ran, with what parameters, by which user, against which objects*.

*Week 5: Build the ActionExecutor pattern.*

A single service that all actions route through. It enforces preconditions, runs the effects in a transaction, writes the audit log, and emits an event. Add a `dry_run=True` mode that runs preconditions and returns the planned effects without committing — this becomes enormously valuable later for any "preview before commit" UI.

Now refactor 2-3 more actions onto this pattern. `RejectDocument`, `CorrectExtractedField`, `MergePatients` if you've started ER work. Each refactor is small (the logic exists; you're renaming and structuring it) and each one makes the next one faster.

*Week 6: The audit log becomes the audit feature.*

Now that every mutation flows through actions, the audit log is comprehensive by construction. Build a simple "history" view on the patient record that shows every action that ever touched this patient, with timestamps, actors, and one-click access to the source documents that drove each change. This is a *feature* you can ship to customers — and it's free, because you got it as a side effect of the architectural work.

This is also the moment where the audit-ready-by-default story we discussed earlier becomes real. Practices using your platform now have an audit trail no paper-based practice can produce. You can start saying that out loud.

---

## Phase 3: The query layer (weeks 7-10)

Goal: clinicians and admin staff can ask natural-language questions across the ontology and get answers with sources, ranked, and actionable. This is where the platform stops being a digitiser and starts being intelligence infrastructure.

*Week 7: Structured query primitives.*

Build the helpers that let you compose queries in ontology terms. Something like:

```
query = (
    Patient
    .where(practice_id=current_practice)
    .has_diagnosis(icd10_starts_with="E11")
    .has_lab_result(loinc="4548-4", value__gt=8.0, age__lte="3 months")
    .order_by(last_consultation_date__desc)
)
```

This compiles down to SQL with the right joins, the right indices, and the right pgvector calls for any embedding-based filters. Start with the 5-10 query shapes that matter most for your morning briefing and pre-consultation brief work.

*Week 8: The natural-language layer.*

A service that takes a clinician's question, classifies it against known query templates, fills in parameters, runs the structured query, and returns results. Start narrow — the 20 most common question patterns, hand-mapped to query templates. Don't try to build a general NL2SQL system yet; that's a research project.

The pattern: clinician asks "diabetics with HbA1c over 8" → LLM extracts intent (`find_patients_with_chronic_condition_and_lab_threshold`) and parameters (`condition=diabetes`, `lab=HbA1c`, `threshold=8`, `direction=above`) → those flow into a pre-built structured query template → results return with provenance.

This is the architecture that scales. Each new question type either matches an existing template (cheap) or adds a new template (a few hours of work). Over time you accumulate a library of clinical query patterns that covers 95% of what doctors ask.

*Week 9: Provenance in every answer.*

Every result that comes back from a query is wrapped with its source. "Mrs Khumalo: HbA1c 8.9% (Lancet lab report, 8 March 2026, page 1)" with a one-click link to the source scan. This is what makes clinicians trust the platform. Build this into the query result format itself, not as a UI afterthought.

*Week 10: Standing queries and materialisation.*

Now the morning briefing and pre-consultation brief become buildable, because they're just *registered queries* that run on a schedule, write to a `briefing_items` table, and surface through a thin UI layer. The hard work was the ontology and query layer underneath; the briefing is the harvest.

---

## Phase 4: The proactive layer (weeks 11-14)

Goal: the platform doesn't just answer questions, it surfaces things the clinician didn't know to ask.

*Week 11: Open loops as ontology objects.*

Define `OpenLoop` as a first-class object type. It has an opening event (a recommendation, a referral, a recommended test), an expected closing event (a result, a letter, a documented decision), a deadline, an urgency, and a state machine. Refactor your existing "things to follow up" logic into this model.

*Week 12: The loop taxonomy.*

Build out 8-12 loop types specific to SA primary care: stress-test-recommended, specialist-referral-pending, abnormal-result-unacknowledged, chronic-script-expiring, pmb-preauth-expiring, immunisation-overdue, diabetic-foot-exam-due, retinal-screening-due, medication-reconciliation-needed. Each loop type has its own opening detector (what creates it from extracted documents) and its own closing detector (what marks it resolved).

*Week 13: The morning briefing surface.*

Build it for real now. The queries are registered, the loops are tracked, the actions are wired, the provenance is solid. This is the week the platform starts feeling like the screen the doctor checks every morning.

*Week 14: The pre-consultation brief.*

Same primitives, narrower scope. By now you have everything you need — diff against last visit (uses your audit log + actions), open loops (Phase 4 work), reason for visit (appointment ingestion), medications and allergies (existing data). The brief is a composition, not new infrastructure.

---

## Phase 5: Compound returns (month 5 onwards)

Past Phase 4 the work stops being sequential and starts being opportunistic. The ontology is in place, actions are flowing through it, queries traverse it, briefings materialise from it. Now every new feature is *additive* on this foundation rather than custom-built from scratch.

Things that become cheap once the spine is in:

ER and patient deduplication (it's just a `MergePatients` action with a `find_match_candidates` query against the Patient ontology).

FHIR export per profile (it's just additional serialisers on the ontology, not a separate pipeline).

Care-quality dashboards for practice owners (just aggregations over the audit log and loop history).

Provider-network insights for medical schemes (just anonymised rollups over the ontology — and now your B2B story has data to back it).

Multi-practice rollups (just queries that span practices in the same group).

Audit-readiness for AGSA, HPCSA, OHSC (just exports of the existing audit log filtered to a date range and scope).

Each of these used to be a 6-week project. After the ontology, most are a week.

---

## The three things that will try to kill this roadmap

I want to flag these explicitly because they're the predictable failure modes:

*The "let's just add this feature first" temptation.* A customer will ask for something during Phase 1 or 2, and there will be pressure to bolt it onto the existing structure rather than waiting for the ontology to support it cleanly. Sometimes that's the right call (customer signal > architectural purity) but be honest with yourself when it happens — every bolted-on feature is debt that the ontology will eventually have to absorb.

*The completeness trap.* You'll be tempted to define all 14 object types and 30 link types in Phase 1 instead of just three. Don't. The ontology is not valuable as a *complete* model; it's valuable as a *load-bearing* spine. Three object types deeply modelled and consistently consumed beats fourteen object types declared and ignored.

*The "we'll do actions later" shortcut.* The action layer is the boring part — it doesn't produce a screenshot for a customer demo. There will be pressure to skip Phase 2 and jump straight to Phase 3's query layer. Resist this. The action layer is what makes the audit trail real, the ER work tractable, the reversibility of mistakes possible, and the regulatory story credible. Skip it and you have a query layer over a model that nobody can trust.

---

## What I'd do tomorrow morning if this were my platform

Concretely, in order:

Open a Notion or markdown doc. Write the one-page ontology charter. What is the ontology *for* in your platform, in your words.

Open your codebase. List every domain object that exists implicitly. Map where each one's schema, mutations, and consumers live. This takes 2-3 hours and you'll learn things about your own codebase you didn't realise.

Pick your first three. I'd bet hard on Patient, Document, Consultation. Write down why.

Spend the rest of the day designing the Patient ontology object — every property, every PII tag, every FHIR mapping, every link to other objects. Don't write code yet. Just the model.

Tomorrow, start writing it as a real Pydantic class in a new `ontology/` package. Refactor exactly one endpoint to consume it. Ship that refactor by end of week one.

The ontology will feel slow to take hold for the first three weeks. Around week four something flips — adding a new feature stops requiring you to think about three different layers, and starts feeling like composing primitives. That's the moment you'll know it's working.

Want me to draft the actual Patient ontology object as a concrete starting artifact? I can write it out as a real Pydantic-style declaration with the properties, PII flags, FHIR mappings, and link metadata fleshed out, and you'd have a template to copy for Document and Consultation. That's probably the single most useful thing I can hand you to start tomorrow.

---

## Deferred / parked roadmap items (recorded 2026-05-18)

Explicitly **named-not-built**, parked by decision — to be built down the line, not now:

1. **Standalone Intelligence overlay on a third-party EHR — requires inbound FHIR/HL7 ingestion.**
   The ontology/query/proactive layer is a *consumer* of structured clinical data; it has no ingestion path of its own. Today the only built path into the structured store is our **digitisation** pipeline (upload → extract → approve → promote). To sell Intelligence as an overlay on a practice's *existing* (non-our) EHR, an inbound FHIR/HL7 import pipeline must be built. It does not exist. Deferred.

2. **Ontology data-ingestion gap — lab results, appointments/reason-for-visit, screening-due.**
   Several query templates and proactive open-loop kinds are `schema_only` / named-not-built because they need data types digitisation does not produce: lab results (LOINC), appointment/reason-for-visit ingestion, screening-due. The ontology infrastructure works on digitised clinical data (diagnoses, medications, vitals, demographics); these specific templates stay empty until their ingestion paths exist. Deferred (same bucket as item 1).

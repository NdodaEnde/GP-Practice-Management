"""
Query-template registration sentinel.

Importing this module fires register_template() for every template in
ontology/query/templates/. Mirrors app/actions/registered.py.

To add a query shape:
  1. Write ontology/query/templates/<shape>.py with a
     register_template(TemplateSpec(...)) call.
  2. Write its PL/pgSQL function in the next migration, ending the
     migration with NOTIFY pgrst, 'reload schema' (Phase-0 finding —
     without it the RPC is invisible to PostgREST until cache reload).
  3. Add one import line below.
"""

from ontology.query.templates import patients_with_diagnosis_prefix  # noqa: F401

# PR B — briefing / pre-consult set.
from ontology.query.templates import patients_not_seen_since  # noqa: F401
from ontology.query.templates import patient_active_medications  # noqa: F401
from ontology.query.templates import patient_recent_consultations  # noqa: F401
from ontology.query.templates import patients_with_abnormal_recent_vitals  # noqa: F401,E501
from ontology.query.templates import patient_open_documents  # noqa: F401
from ontology.query.templates import patients_with_lab_threshold  # noqa: F401

# PR G (option B) — one real derived cohort (immunisation-overdue, thin).
from ontology.query.templates import immunisations_overdue  # noqa: F401

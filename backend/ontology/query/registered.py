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

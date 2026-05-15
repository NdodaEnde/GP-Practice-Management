"""
Action registration sentinel module.

Importing this module fires the @register_action decorator side-effect
for every action class declared in the codebase, populating ACTIONS in
`registry.py`. This is the standard plugin-registration pattern.

To add a new action:
    1. Write the class in `backend/ontology/actions/<your_action>.py`
       with `@register_action @dataclass(eq=False)` decorators.
    2. Add one line below to import its module.

That's it. The registry is correctly populated; the executor can
hydrate actions back from audit rows via `get_action_class()`.

This file is imported from `app/actions/__init__.py` so the registration
happens at package import time.
"""

# Each line below triggers @register_action on the action class(es) in
# that module. The import is side-effect-only; we don't use the module
# names directly.

from ontology.actions import promote_document  # noqa: F401

# PR 3 — clinical-mutation actions.
from ontology.actions import reject_document        # noqa: F401
from ontology.actions import reprocess_document     # noqa: F401
from ontology.actions import void_prescription      # noqa: F401
from ontology.actions import edit_extraction_field  # noqa: F401
from ontology.actions import soft_delete_patient    # noqa: F401
from ontology.actions import reassign_document      # noqa: F401
from ontology.actions import merge_patient          # noqa: F401
# from ontology.actions import reassign_document     # noqa: F401
# from ontology.actions import merge_patient         # noqa: F401

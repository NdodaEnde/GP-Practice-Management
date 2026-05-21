"""
Document ontology enums.

These reflect the actual states and provenance categories that the SA GP /
digitisation platform deals with — not a generic document-management
taxonomy. If something doesn't appear in practice (e.g. a separate
"NEEDS_LEGAL_REVIEW" status), it doesn't belong here.
"""

from enum import Enum


class DocumentSource(str, Enum):
    """How the document arrived in the platform.

    Provenance matters for trust (an auto-uploaded scan-agent file has
    different review weight than a doctor's deliberate manual upload),
    for billing (some tiers meter manual vs. automated ingest separately),
    and for debugging (a parsing regression often correlates with a
    specific source path).
    """

    MANUAL_UPLOAD = "manual_upload"      # human dragged a file into the platform
    STORAGE_WATCHER = "storage_watcher"  # server-side watcher picked it up from Storage
    SCAN_AGENT = "scan_agent"            # client-side scan agent uploaded from a workstation
    BATCH_UPLOAD = "batch_upload"        # operator-initiated bulk import (e.g. backfill)
    API = "api"                          # programmatic POST from an integration partner


class DocumentStatus(str, Enum):
    """Lifecycle of a document through the parse → validate → promote pipeline.

    States are deliberately granular because each transition is where bugs,
    cost overruns (LandingAI credit burn), and audit questions arise. A
    coarser FSM hides where the platform is actually spending time.

    Terminal states: PROMOTED, REJECTED, ARCHIVED.
    """

    UPLOADED = "uploaded"                # file present, nothing run on it yet
    PARSING = "parsing"                  # extractor (LandingAI) is running now
    PARSED = "parsed"                    # extraction complete, awaiting validation
    PARSE_FAILED = "parse_failed"        # extractor returned an error or unusable output
    VALIDATING = "validating"            # a human is reviewing the extracted fields
    VALIDATED = "validated"              # human approved the fields; not yet promoted
    PROMOTED = "promoted"                # contents have been written into patient record
    REJECTED = "rejected"                # human determined the document is not useful
    ARCHIVED = "archived"                # retained for audit but excluded from queues

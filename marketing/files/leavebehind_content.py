#!/usr/bin/env python3
"""
Builds three Type-specific post-demo leave-behind documents (A, B, C).

Design principle: shared sections are defined ONCE here and rendered
verbatim-identical across all three outputs. Only the recap framing, the
recommended configuration, and the first-step pilot differ by type. This
keeps the ~60% shared content from diverging across three files when it
is later revised.

Each document is a standalone print-ready HTML (renders to PDF identically
to the brochure pipeline).
"""

# ----------------------------------------------------------------------
# TYPE-SPECIFIC CONTENT
# Only three things genuinely differ by practice type. Everything else
# is shared and identical.
# ----------------------------------------------------------------------

TYPES = {
    "A": {
        "code": "A",
        "label": "Practices with no digital system today",
        "one_line": "Nothing digital yet. A back room of paper. No view of the practice.",
        # RECAP — what this practice type saw in the demo, framed to their reality
        "recap_intro": (
            "You run on paper. In the demo, we took a stack of your own files "
            "&mdash; the disorganised ones, the handwritten ones &mdash; and "
            "showed you what comes out the other side: structured, searchable "
            "patient records, with the original scan one click away."
        ),
        "recap_points": [
            ("Your own files, read automatically",
             "Not a prepared sample. Your handwriting, your forms, your "
             "medical-aid stamps &mdash; extracted into structured fields "
             "while you watched."),
            ("A question you can&rsquo;t answer today, answered",
             "We asked the system a plain-English question across the records "
             "&mdash; the kind of question that today means an afternoon in "
             "the back room &mdash; and it returned the answer with the source "
             "page attached."),
            ("Nothing on your desk changed",
             "No new screen for you to learn during a consult. The work "
             "happens around you, not in front of you."),
        ],
        # RECOMMENDED CONFIGURATION
        "config_title": "What we&rsquo;d put in your practice",
        "config_intro": (
            "You have no digital system to protect or work around, which makes "
            "this the cleanest possible starting point. We&rsquo;d move your "
            "core workflow onto one platform from day one, and digitise the "
            "back room in parallel."
        ),
        "config_items": [
            ("The practice platform &mdash; Essential",
             "Registration, encounter, prescription, invoice &mdash; one "
             "system from day one. Patient registry, vitals with auto-BMI, "
             "allergy-interaction checks on prescriptions, billing with online "
             "payments. The whole core loop, not a patchwork."),
            ("Digitisation of the back room",
             "Your legacy archive becomes structured patient data, month by "
             "month, at a fixed monthly pace. By the time a 2014 patient walks "
             "back in, their history is already in the system."),
            ("The analytics view",
             "Once records are structured, the view of your practice you have "
             "never had &mdash; chronic-disease cohorts, who is overdue, where "
             "revenue is leaking &mdash; without you building a single "
             "spreadsheet."),
        ],
        "config_note": (
            "What we would <em>not</em> start you on: AI Scribe, telehealth, "
            "or the Clinical&nbsp;AI beta. Those are later conversations, if "
            "ever. The first job is getting your practice off paper without "
            "disrupting a single consult."
        ),
        # FIRST STEP
        "pilot_headline": "The smallest first step",
        "pilot_body": (
            "Not the whole archive. Not a year&rsquo;s commitment. One month, "
            "1,500 pages, the files you choose &mdash; ideally the messiest "
            "ones, so you are testing the hard case, not the easy one. Your "
            "staff validates as they would in production. At the end of the "
            "month you have a real, structured slice of your own archive and "
            "an honest sense of the day-to-day. Cancel any time, no setup fee, "
            "no lock-in."
        ),
    },

    "B": {
        "code": "B",
        "label": "Practices with an EHR, but a workflow stitched from disconnected tools",
        "one_line": "You have an EHR. But billing, video, dictation and the queue don&rsquo;t talk to each other.",
        "recap_intro": (
            "You already run an EHR &mdash; so this was never about replacing "
            "the system you trust as your record. In the demo, we showed two "
            "things: your legacy archive becoming structured data alongside "
            "that EHR, and what it looks like when the surrounding workflow "
            "stops being four tools stitched together by hand."
        ),
        "recap_points": [
            ("Your archive, structured &mdash; without touching your EHR",
             "We took your own legacy files and extracted them into structured "
             "records, exportable straight into the EHR you already run. Your "
             "system of record did not change."),
            ("The questions your EHR can&rsquo;t answer",
             "Most EHRs store data well and analyse it poorly. We asked the "
             "kind of cross-practice question your current system has no screen "
             "for, and got an answer with the source attached."),
            ("The stitching, gone",
             "We showed what the day looks like when billing, notes, video and "
             "the queue are one flow rather than four browser tabs and a "
             "WhatsApp."),
        ],
        "config_title": "What we&rsquo;d put in your practice",
        "config_intro": (
            "Your EHR stays. This is explicitly not a rip-and-replace &mdash; "
            "you paid for that system and it holds your record. What you do "
            "not have is a workflow that hangs together, and a view of your "
            "own data. We address those two without disturbing the first."
        ),
        "config_items": [
            ("The practice platform &mdash; Professional, as consolidation",
             "Not to replace your EHR as the record, but to end the "
             "tool-stitching: AI Scribe drafting your notes from the consult, "
             "telehealth and e-scripts, reception and queue and vitals on one "
             "flow. The patchwork becomes one system."),
            ("Digitisation of the back room",
             "Your legacy archive becomes structured data, exported back into "
             "the EHR you already run via FHIR or CSV. The archive stops being "
             "dead weight; your system of record stays exactly where it is."),
            ("The analytics view",
             "Chronic-disease cohorts, claims aging, no-show patterns, "
             "productivity &mdash; ingested from your existing EHR. The "
             "analysis layer your current system was never built to be."),
        ],
        "config_note": (
            "The honest framing: we are not telling you your EHR was the wrong "
            "choice. We are removing the four-tools-that-don&rsquo;t-talk tax "
            "you pay every evening, and giving you the view of your data the "
            "EHR was never designed to provide."
        ),
        "pilot_headline": "The smallest first step",
        "pilot_body": (
            "Start with digitisation only &mdash; the lowest-risk module and "
            "the one that touches your EHR least. One month, 1,500 pages of "
            "your choosing, exported in the format your current EHR ingests. "
            "You see the extraction quality on your own documents and confirm "
            "the export lands cleanly in the system you already run, before "
            "any conversation about the wider workflow. Cancel any time, no "
            "setup fee, no lock-in."
        ),
    },

    "C": {
        "code": "C",
        "label": "Practices with an EHR and a workflow that already works",
        "one_line": "Your system works. You have a back room of paper and no analytics. That is the whole gap.",
        "recap_intro": (
            "Your practice is already digital and your workflow already hangs "
            "together &mdash; so we are not going to pretend you need a new "
            "platform. The demo was deliberately narrow: your legacy archive "
            "becoming structured data, and the analytics view your current "
            "system does not give you. Those two things. Nothing else."
        ),
        "recap_points": [
            ("Your archive, structured, into the system you already run",
             "We took your own legacy files, extracted them into structured "
             "records, and showed the export landing in the format your EHR "
             "ingests. No change to your system of record."),
            ("The analysis your EHR was never built for",
             "We asked a natural-language question across the archive &mdash; "
             "the cross-practice view your current system stores the data for "
             "but cannot surface &mdash; and it answered with the source "
             "attached."),
            ("Nothing about your working setup disturbed",
             "No platform migration, no workflow change, no retraining. A "
             "layer on top of what already works."),
        ],
        "config_title": "What we&rsquo;d put in your practice",
        "config_intro": (
            "You do not need the practice platform and we are not going to "
            "sell it to you. Your gap is precisely two things: a back room "
            "that is not structured data, and no analytical view of the data "
            "you already hold. We address exactly those and nothing else."
        ),
        "config_items": [
            ("Digitisation of the back room",
             "Your legacy archive becomes structured patient data, exported "
             "into the EHR you already run via FHIR, CSV or JSON. Your system "
             "of record does not move."),
            ("The analytics view",
             "Chronic-disease cohorts, claims aging, no-show and productivity "
             "patterns, semantic search across the whole archive &mdash; "
             "ingested from your existing EHR via API or scheduled export. "
             "The layer your current system was never meant to be."),
            ("No platform change. Deliberately.",
             "We are not quoting you a platform tier. You did not ask for one "
             "and you do not need one. The recommendation is two modules, on "
             "top of what you already run."),
        ],
        "config_note": (
            "If anything in this document reads like a platform upsell, we "
            "have written it wrong &mdash; tell us. A Type&nbsp;C practice "
            "buys digitisation and analytics, or it buys nothing. We would "
            "rather sell you the right small thing than the wrong large one."
        ),
        "pilot_headline": "The smallest first step",
        "pilot_body": (
            "One month, 1,500 pages of your choosing, exported in the exact "
            "format your EHR ingests. The single thing you are testing is "
            "whether the extraction quality on <em>your</em> documents is good "
            "enough and whether the export lands cleanly in the system you "
            "already run. If both are true, we talk about the rest of the "
            "archive. If either is not, you have lost a month&rsquo;s "
            "subscription and nothing else. No setup fee, no lock-in."
        ),
    },
}


# ----------------------------------------------------------------------
# SHARED CONTENT — identical across all three documents.
# Edit here once; it changes in all three predictably.
# ----------------------------------------------------------------------

SHARED = {
    "operational_reality": {
        "title": "What this actually costs you in staff time",
        "intro": (
            "The honest answer to the question you are really asking &mdash; "
            "&ldquo;my reception is already drowning, what does this add to "
            "her day?&rdquo;"
        ),
        "rows": [
            ("Per document",
             "30&ndash;60 seconds. The system extracts; your staff reviews "
             "what it found, corrects anything wrong, and approves. They know "
             "your handwriting; the system handles most of it; they catch the "
             "rest."),
            ("Week one",
             "Scanning happens into the same folder your reception already "
             "scans into. The only new habit is the validation queue &mdash; "
             "a list of documents waiting for a 30-second check. That is the "
             "entire workflow change."),
            ("Month three",
             "The queue is a background habit, not an event. The structured "
             "archive is large enough that the search and analytics start "
             "answering real questions. Nothing about the consult has "
             "changed."),
            ("What does not change",
             "How you consult. What you write. Your existing system, if you "
             "have one. We are a layer that adds capability, not a system "
             "that takes work away from one that already works."),
        ],
    },

    "failure_modes": {
        "title": "What happens when it doesn&rsquo;t work perfectly",
        "intro": (
            "Demos show the happy path. This is the part that matters more: "
            "what the system does when a scan is bad, the handwriting is "
            "unreadable, or the extraction is unsure. We would rather you "
            "read this now than discover it later."
        ),
        "rows": [
            ("Low-confidence extraction",
             "Every extracted field carries a confidence score. Low-confidence "
             "fields are flagged for the validator, not silently accepted. The "
             "human sees exactly what the system was unsure about."),
            ("An unreadable document",
             "If a scan is too poor to extract, it does not get guessed at. It "
             "is held in the queue, flagged, and a person decides &mdash; "
             "rescan, enter by hand, or set aside. The system never invents "
             "data to fill a gap."),
            ("The wrong-patient safeguard",
             "Nothing enters a patient&rsquo;s record until a person confirms "
             "it is the right patient. The match is shown; the human says yes "
             "or no. Wrong-patient errors are caught at that gate &mdash; "
             "before they happen, not discovered months later."),
            ("Every action is logged",
             "Every approval, correction and reversal is recorded &mdash; who "
             "did it, when. If a medical aid audits the practice, or you need "
             "to show the basis of a record, the history is one query away."),
        ],
    },

    "why_us": {
        "title": "Why a South African practice chooses this",
        "points": [
            ("Built here, not bolted on",
             "Medical-aid schemes, HPCSA prescription rules, NAPPI codes, the "
             "SA edition of ICD-10, local payments &mdash; native to the "
             "system, not adapted to it after the fact."),
            ("Digitisation as a subscription, not a project",
             "The reason practices stay on paper is the six-figure project "
             "quote nobody signs. A predictable monthly page allowance "
             "instead &mdash; payable, cancellable, no capital sign-off."),
            ("It works with what you already have",
             "Export and ingest via FHIR, CSV or API. You do not rip out a "
             "system that works to get the parts you don&rsquo;t have."),
            ("Each practice&rsquo;s data is isolated",
             "Multi-tenant by design. What happens at one practice never "
             "crosses to another."),
        ],
    },

    "honest_limits": {
        "title": "What we are deliberately not promising you",
        "intro": (
            "The same discipline we apply to the product, applied to this "
            "document. These are real and they are not in scope of what you "
            "would be buying."
        ),
        "rows": [
            ("Final pricing",
             "Set per practice on doctor count, page volume and integration "
             "scope. The pilot price is fixed and stated; the full quote is a "
             "conversation, not a number on a leave-behind."),
            ("Clinical decision support",
             "Our clinical-AI work is an invite-only beta, not a commercial "
             "product, with no medical-device approval. It is a design-partner "
             "conversation if you raise it &mdash; it is deliberately not part "
             "of what this document offers you."),
            ("Roadmap items",
             "Medical-aid claims auto-submission, multi-site management and "
             "native EHR integrations are planned, not promised here. If it is "
             "not in the configuration above, treat it as not yet real."),
        ],
    },

    "contact": {
        "web": "medicdata.co.za",
        "email": "luzuko@medicdata.co.za",
        "phone": "+27 (0) 76 969 5462",
        "demo": "medicdata.co.za/demo",
    },
}

if __name__ == "__main__":
    import json
    print(f"Types defined: {list(TYPES.keys())}")
    print(f"Shared sections: {list(SHARED.keys())}")
    print("Content model OK")

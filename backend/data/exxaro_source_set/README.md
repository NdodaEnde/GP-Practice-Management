# Exxaro source set

Public PDFs ingested by the Mining gateway / Financial-Disclosure module
(spec §1, open question #1 in the plan).

Layout (matches `fd_documents.doc_type` enum):

    integrated/fy{2022,2023,2024,2025}/exxaro-ir-{year}.pdf
    sustainability/fy{2022,2023,2024,2025}/exxaro-esg-{year}.pdf
    investor/fy{2022,2023,2024,2025}/exxaro-afs-{year}.pdf  ← Annual Financial Statements

Each PDF is the **public, primary** version published on Exxaro's investor
relations portal (`investor.exxaro.com/integrated-reports{year}`). No
internal documents.

These files are **not committed** — they're public and large. Re-run
`backend/scripts/download_exxaro_reports.py` to fetch a fresh copy with
SHA-256 verification.

The `doc_id` used at ingest time matches the file basename without the
extension (e.g. `EXXARO-IR-2024`). The mapping happens in
`backend/scripts/ingest_exxaro_source_set.py`.

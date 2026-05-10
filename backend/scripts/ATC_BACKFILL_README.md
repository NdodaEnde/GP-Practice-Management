# ATC code backfill — runbook

Implements [TRACEABILITY.md](../../TRACEABILITY.md) item 6b.

## What this does

Populates `nappi_codes.atc_code` (+ `atc_class_desc`) on existing rows by
matching `generic_name` / `ingredients` against the WHO ATC index. ~95% of
rows are NULL today; this gets the easy ones automated and routes the
ambiguous ones to a CSV the user reviews.

## License caveat

The currently checked-in ATC CSV is **CC BY-NC-SA 4.0** (NonCommercial). It
is appropriate for development; **before commercial GA**, replace it with a
licensed source. Every row backfilled from this CSV is stamped
`atc_source = 'atcd-2026-04-25'` so the dev-data rows can be located and
rerun. See [`backend/data/atc/NOTICE.md`](../data/atc/NOTICE.md).

## Step-by-step

### 1. Run migration 006 (one time)

In the Supabase SQL editor, paste and run
[`backend/migrations/006_atc_backfill.sql`](../migrations/006_atc_backfill.sql).
Idempotent — safe to re-run. Adds:

- `atc_class_desc TEXT`
- `atc_match_method TEXT` (CHECK: `exact|fuzzy|manual|combo`)
- `atc_source TEXT`
- `atc_matched_at TIMESTAMPTZ`
- two partial indexes for class/method lookups

### 2. Export NAPPI rows from Supabase

In SQL editor, run and "Download as CSV":

```sql
SELECT nappi_code, brand_name, generic_name, ingredients
  FROM nappi_codes
 WHERE atc_code IS NULL OR atc_source = 'atcd-2026-04-25';
```

(The OR clause means re-runs replace prior dev-data rows automatically; on
the very first run, only the IS NULL clause matters.)

Save as `nappi_export.csv` somewhere local — examples below assume `/tmp/`.

### 3. Run the matcher

```bash
cd /Users/luzuko/GP-Practice-Management/backend
.venv/bin/python scripts/atc_backfill.py \
    --nappi-csv /tmp/nappi_export.csv \
    --out-dir /tmp/atc_run \
    --fuzzy-threshold 0.92
```

Output files in `/tmp/atc_run/`:

| File | Contents |
|---|---|
| `matched_exact.csv` | Single unambiguous level-5 match. Safe to apply. |
| `matched_review.csv` | Multi-candidate or fuzzy match. Reviewer eyeballs. |
| `unmatched.csv` | No ATC found. Mostly combos + odd brand names. |
| `006_atc_backfill_data.sql` | UPDATEs for `matched_exact` only. |

### 4. Review

- `matched_review.csv` has an `alternatives` column listing the other ATC
  codes the same name resolves to (e.g., diclofenac in M01 vs M02 vs S01 vs
  D11). Pick the right one based on the row's `dosage_form` /
  `route_of_administration` (eye drops → S01, gel → M02 / D11, tablet →
  M01).
- `unmatched.csv` is mostly combinations (`amoxicillin + clavulanic acid`).
  These need a manual mapping pass — the WHO combinations CSV covers
  branded multi-ingredient products (Pylera, Meteospasmyl, etc.) but NOT
  the generic prescribing-style "drugA + drugB" SA pharmacies use.

For rows reviewer accepts, edit `matched_exact.csv` to append them, then
re-run step 3 with `--nappi-csv` pointing at a curated subset (or hand-edit
the SQL). Either path is fine — the SQL is plain UPDATE statements keyed
by `nappi_code`.

### 5. Apply

Paste `006_atc_backfill_data.sql` into Supabase SQL editor and run.
Wrapped in a single transaction; failures roll back.

### 6. Verify

```sql
SELECT
    count(*) FILTER (WHERE atc_code IS NOT NULL)        AS with_atc,
    count(*) FILTER (WHERE atc_code IS NULL)            AS without_atc,
    count(*) FILTER (WHERE atc_match_method = 'exact')  AS exact,
    count(*) FILTER (WHERE atc_match_method = 'fuzzy')  AS fuzzy,
    count(*) FILTER (WHERE atc_match_method = 'manual') AS manual
  FROM nappi_codes;
```

## Tuning

- `--fuzzy-threshold 0.92` is the default. Raising to 0.95+ cuts false
  positives at the cost of more `unmatched`. Lowering to 0.85 catches more
  typos but bloats the review pile.
- `--atc-source` lets you stamp a different provenance tag if you switch to
  e.g. `bioportal-CCBY-2026` or `rxnorm-2026q2` later.

## Test

`scripts/_atc_test_sample.csv` is a 15-row synthetic NAPPI sample covering
the happy path + multi-candidate + combo + typo + bogus cases. Run it
against the matcher to sanity-check after any change.

# ATC source data — NOTICE

Source: <https://github.com/fabkury/atcd>
Version downloaded: `WHO ATC-DDD 2026-04-25` (and combinations file of the same date)
Licence: **Creative Commons Attribution-NonCommercial-ShareAlike 4.0**

## Cleanup obligation

This data is **not licenced for commercial production use**. It is loaded here
to develop and validate the matcher offline. Every NAPPI row backfilled from
this CSV is stamped `atc_source = 'atcd-2026-04-25'` so the affected rows can
be located and replaced with a properly licenced source before commercial GA.

To find affected rows later:

```sql
SELECT count(*) FROM nappi_codes WHERE atc_source = 'atcd-2026-04-25';
```

To clear them in preparation for re-running against a licenced source:

```sql
UPDATE nappi_codes
   SET atc_code = NULL,
       atc_class_desc = NULL,
       atc_match_method = NULL,
       atc_source = NULL,
       atc_matched_at = NULL
 WHERE atc_source = 'atcd-2026-04-25';
```

## Replacement candidates

- BioPortal ATC ontology (CC BY) — requires free API key.
- NLM RxNorm RXNCONSO (US public domain) — pull SAB='ATC' subset.
- WHO Collaborating Centre direct licence (commercial path).

#!/usr/bin/env bash
# ============================================================================
# migrate_dev_to_prod.sh
# ----------------------------------------------------------------------------
# Copies the SCHEMA (all table structure, indexes, functions, RLS) +
# REFERENCE DATA ONLY (ICD-10 / NAPPI / product catalog — NOT patient or
# demo data) from the DEV Supabase project into a fresh, EMPTY PROD project.
#
# This is the CORRECT bootstrap. (scripts/production_bootstrap.sql is
# discarded — the migrations folder is not a from-zero schema.)
#
# HOW TO RUN (one Terminal window, do not close it between steps):
#
#   1. Create the fresh PROD Supabase project (Pro plan). It is empty.
#   2. Get TWO "Session pooler" connection strings (Dashboard ->
#      Project Settings -> Database -> Connection string -> Session pooler,
#      port 5432). One from the DEV project, one from the new PROD project.
#      Substitute each project's database password into its string.
#   3. Run:
#
#        DEV="postgresql://postgres.sizujtbejnnrdqcymgle:DEVPASS@aws-0-REGION.pooler.supabase.com:5432/postgres" \
#        PROD="postgresql://postgres.NEWREF:PRODPASS@aws-0-REGION.pooler.supabase.com:5432/postgres" \
#        bash backend/scripts/migrate_dev_to_prod.sh
#
#   DEV = the OLD project (source, read-only). PROD = the NEW empty one
#   (target, written to). Don't swap them.
#
# It stops on the first real error (no silent half-apply). Safe to re-run
# only against a still-empty PROD.
# ============================================================================
set -euo pipefail

DEV="${DEV:-}"
PROD="${PROD:-}"

command -v pg_dump >/dev/null 2>&1 || { echo "ERROR: pg_dump not found. Install: brew install libpq && brew link --force libpq"; exit 1; }
command -v psql    >/dev/null 2>&1 || { echo "ERROR: psql not found. Install: brew install libpq && brew link --force libpq"; exit 1; }
[ -n "$DEV" ]  || { echo "ERROR: DEV connection string not set (the OLD project, source)."; exit 1; }
[ -n "$PROD" ] || { echo "ERROR: PROD connection string not set (the NEW empty project, target)."; exit 1; }

echo "DEV  (source, READ-ONLY) : ...@${DEV##*@}   (the OLD project)"
echo "PROD (target, WRITTEN)   : ...@${PROD##*@}   (the NEW empty project)"
echo
echo "This copies STRUCTURE + reference data only (NO patient/demo data),"
echo "DEV -> PROD. PROD must be a freshly created, empty project."
read -r -p "Continue? [y/N] " ok
[ "$ok" = "y" ] || [ "$ok" = "Y" ] || { echo "Aborted."; exit 1; }

WORK="$(mktemp -d)"
echo
echo "[1/5] Dumping schema (structure only) from DEV ..."
pg_dump -n public --schema-only --no-owner --no-privileges "$DEV" > "$WORK/schema.sql"
echo "      schema.sql: $(wc -l < "$WORK/schema.sql" | tr -d ' ') lines"

echo "[2/5] Dumping reference data only from DEV (icd10/nappi/products/...) ..."
pg_dump -n public --data-only --no-owner \
  --table=public.icd10_codes \
  --table=public.nappi_codes \
  --table=public.products \
  --table=public.capabilities \
  --table=public.product_capabilities \
  --table=public.pricing_bands \
  "$DEV" > "$WORK/refdata.sql"
echo "      refdata.sql: $(wc -l < "$WORK/refdata.sql" | tr -d ' ') lines"

echo "[3/5] Resetting PROD public schema to a clean slate + vector ..."
# Self-cleaning: every run starts PROD's public schema fresh, so a
# previous half-finished load never blocks a retry. PROD is a brand-new
# project with no real data — this only clears prior bootstrap attempts.
# `vector` is installed INTO public because the dev dump references the
# type as public.vector (Supabase's dashboard would put it in
# `extensions`, which would not resolve).
psql "$PROD" -v ON_ERROR_STOP=1 >/dev/null <<'SQL'
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL   ON SCHEMA public TO postgres, service_role;
DROP EXTENSION IF EXISTS vector;
CREATE EXTENSION vector WITH SCHEMA public;
SQL
# pg_dump emits schema-level statements that would collide with the
# public schema we just made — strip them; table/index/function
# creation (the real schema) is untouched.
grep -vE '^(CREATE SCHEMA public;|CREATE SCHEMA IF NOT EXISTS public;|COMMENT ON SCHEMA public |ALTER SCHEMA public OWNER )' \
  "$WORK/schema.sql" > "$WORK/schema.clean.sql"
echo "      sanitised: $(wc -l < "$WORK/schema.clean.sql" | tr -d ' ') lines"

echo "[4/5] Loading schema into PROD (atomic — rolls back fully on any error) ..."
psql "$PROD" -v ON_ERROR_STOP=1 --single-transaction -q -f "$WORK/schema.clean.sql" >/dev/null

echo "[5/5] Loading reference data into PROD (atomic) ..."
psql "$PROD" -v ON_ERROR_STOP=1 --single-transaction -q -f "$WORK/refdata.sql" >/dev/null

echo
echo "Verifying PROD (reference present, NO patient/demo data):"
psql "$PROD" -At -c "
  select 'icd10_codes  = '||count(*)||'  (expect ~41008)' from icd10_codes
  union all select 'nappi_codes  = '||count(*)||'  (expect ~1691)' from nappi_codes
  union all select 'products     = '||count(*)||'  (expect ~7)' from products
  union all select 'capabilities = '||count(*)||'  (expect ~35)' from capabilities
  union all select 'patients     = '||count(*)||'  (MUST be 0)' from patients
  union all select 'workspaces   = '||count(*)||'  (MUST be 0)' from workspaces
  union all select 'tenants      = '||count(*)||'  (MUST be 0)' from tenants;"
echo
echo "DONE. Dump files kept at: $WORK"
echo "If 'patients/workspaces/tenants' are NOT 0, STOP and tell your engineer —"
echo "no patient/demo data should ever be in PROD."

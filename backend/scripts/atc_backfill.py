"""
ATC code backfill matcher — TRACEABILITY item 6b.

Offline matcher: reads a NAPPI export (CSV) + the WHO ATC index CSV(s),
produces three review files (high-confidence matches, review-required fuzzy
matches, unmatched) plus an UPDATE-only SQL file that can be applied via the
Supabase SQL editor. No DB writes happen here.

Inputs
------
--nappi-csv          Path to NAPPI export. Required columns: nappi_code,
                     generic_name. Optional: ingredients, brand_name.
--atc-csv            Path to WHO ATC-DDD CSV. Default: backend/data/atc/
                     WHO_ATC-DDD_2026-04-25.csv
--combinations-csv   Path to WHO combinations CSV (used for combo drug
                     matching). Default: backend/data/atc/WHO_ATC-DDD-
                     combinations_2026-04-25.csv
--out-dir            Where to write the four output files.
--atc-source         Provenance tag stamped on every UPDATE row's
                     atc_source column (default: atcd-2026-04-25).
--fuzzy-threshold    Float in [0,1]; difflib ratio above this counts as a
                     review-required fuzzy match. Default 0.92.

Outputs
-------
matched_exact.csv          High-confidence: normalized exact or combo match.
                           Safe to apply without per-row review.
matched_review.csv         Fuzzy matches above threshold but below 1.0.
                           Reviewer should eyeball these before applying.
unmatched.csv              No ATC found for these NAPPI rows.
006_atc_backfill_data.sql  UPDATE statements for the rows in matched_exact
                           (plus any rows from matched_review the user opts
                           in to manually). Wrapped in a single transaction.

Idempotent: re-running against the same NAPPI export produces deterministic
output. Re-running the SQL is also idempotent (UPDATE-only, keyed by
nappi_code).
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Salts/forms commonly appended to drug names in pharmacy databases that are
# absent from WHO ATC INN names. Stripped during normalization.
SALT_SUFFIXES = (
    "hydrochloride", "hcl",
    "hydrobromide", "hbr",
    "sulphate", "sulfate", "sulpha", "sulfa",
    "phosphate", "diphosphate",
    "citrate", "dihydrate", "monohydrate", "trihydrate",
    "fumarate", "maleate", "succinate", "tartrate",
    "mesylate", "mesilate", "methanesulfonate", "tosylate",
    "besylate", "besilate", "edisylate",
    "sodium", "potassium", "calcium", "magnesium", "zinc",
    "lysine", "lysinate", "arginine",
    "acetate", "propionate", "valerate", "decanoate",
    "stearate", "palmitate", "lactate", "gluconate",
    "tartrate", "bitartrate",
)

# Tokens between two ingredients in a combination (case-insensitive). Order
# matters — longer separators first so they're tried before single chars.
COMBO_SEPARATORS = (
    " plus ", " with ", " and ", " + ", "+",
    " / ", "/", " - ", "; ", ";", ",",
)

DEFAULT_FUZZY_THRESHOLD = 0.92

# Match-method vocabulary — must align with migration 006's CHECK constraint.
METHOD_EXACT = "exact"
METHOD_FUZZY = "fuzzy"
METHOD_COMBO = "combo"

# SA pharma vendor / generic-house prefixes that wrap an INN. Stripped left
# (and right) before retrying an exact match. e.g. "Accord-carboplatin" or
# "Carboplatin cipla" → "carboplatin".
VENDOR_PREFIXES = (
    "accord", "adco", "amka", "aspen", "auro", "austell", "be tabs",
    "betabs", "biotech", "cipla", "dr reddy", "dr reddys", "dynamic",
    "fresenius", "lupin", "macleods", "mylan", "natrocare", "nivagen",
    "pharma dynamics", "pharma natura", "pharmacare", "ranbaxy", "sandoz",
    "sanofi", "sun", "teva", "torrent", "unichem", "winthrop", "zydus",
)

# Non-drug noise words that should NOT be considered as candidate substance
# tokens during token search. Conservative — when in doubt include it.
TOKEN_STOPWORDS = frozenset({
    "tablet", "tablets", "capsule", "capsules", "tab", "tabs", "cap", "caps",
    "vial", "vials", "ampoule", "ampoules", "amp", "syringe", "syringes",
    "bottle", "bottles", "sachet", "sachets", "pack", "blister",
    "infusion", "injection", "inj", "inf", "solution", "sol", "suspension",
    "susp", "syrup", "drops", "spray", "cream", "gel", "ointment", "patch",
    "powder", "lotion", "lozenge", "lozenges", "suppository",
    "concentrate", "prefilled", "ready", "mixed", "active", "extra",
    "release", "modified", "controlled", "sustained", "depot", "long",
    "test", "strip", "strips", "monitor", "device", "diagnostic", "kit",
    "with", "and", "the", "for", "plus", "extra", "forte", "junior",
    "adult", "paediatric", "ped", "kids", "infant", "drug", "medicine",
    # Generic chemistry / ATC-name connector words. Common as part of
    # multi-word ATC names ("ascorbic acid", "and beta-lactamase inhibitor",
    # "fixed combinations") — exclude from the substance-token index so
    # they don't blow up multi-candidate alternatives.
    "acid", "salt", "salts", "ester", "esters", "free", "base",
    "fixed", "combinations", "combination", "compound", "preparations",
    "preparation", "inhibitor", "inhibitors", "antagonist", "antagonists",
    "agonist", "agonists", "agent", "agents", "substance", "substances",
    "extract", "extracts", "complex", "complexes", "vaccine", "vaccines",
})


def strip_vendor_prefix(name: str) -> str:
    """Try to remove a leading or trailing SA pharma vendor name."""
    if not name:
        return name
    s = name.strip()
    low = s.lower()
    # Leading: "Accord-carboplatin", "Adco amoxicillin", "Cipla atorvastatin"
    for v in VENDOR_PREFIXES:
        for sep in ("-", " ", ":"):
            tag = v + sep
            if low.startswith(tag):
                return s[len(tag):].strip()
    # Trailing: "Abiraterone cipla", "Lenalidomide drl"
    for v in VENDOR_PREFIXES:
        for sep in ("-", " "):
            tag = sep + v
            if low.endswith(tag):
                return s[: -len(tag)].strip()
    return s


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

_PUNCT_RE = re.compile(r"[^a-z0-9\s]+")
_WS_RE = re.compile(r"\s+")


def normalize(name: str) -> str:
    """Lowercase, strip salt suffixes, collapse whitespace/punct."""
    if not name:
        return ""
    s = name.lower().strip()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    # Strip trailing salt tokens repeatedly (drugs can have multiple, e.g.
    # "atorvastatin calcium trihydrate" → "atorvastatin").
    changed = True
    while changed:
        changed = False
        for salt in SALT_SUFFIXES:
            if s.endswith(" " + salt):
                s = s[: -(len(salt) + 1)].strip()
                changed = True
    return s


def split_combo(name: str) -> list[str]:
    """Return the substance tokens implied by a combination drug name.

    "amoxicillin + clavulanic acid" → ["amoxicillin", "clavulanic acid"]
    "co-amoxiclav"                  → ["co-amoxiclav"] (no split)
    """
    if not name:
        return []
    lower = " " + name.lower() + " "
    for sep in COMBO_SEPARATORS:
        if sep in lower:
            parts = [p.strip() for p in lower.split(sep) if p.strip()]
            if len(parts) >= 2:
                return parts
    return [name]


# ---------------------------------------------------------------------------
# ATC index loading
# ---------------------------------------------------------------------------

@dataclass
class ATCEntry:
    code: str
    name: str
    level: int            # 1..5
    parent_codes: list[str] = field(default_factory=list)


def atc_level(code: str) -> int:
    """1: A | 2: A01 | 3: A01A | 4: A01AB | 5: A01AB01"""
    n = len(code)
    return {1: 1, 3: 2, 4: 3, 5: 4, 7: 5}.get(n, 0)


def atc_parents(code: str) -> list[str]:
    """All ancestor codes (broadest first)."""
    cuts = (1, 3, 4, 5)
    return [code[:c] for c in cuts if c < len(code)]


def build_token_index(by_code: dict[str, ATCEntry]) -> dict[str, list[ATCEntry]]:
    """Tokenize each level-5 ATC name; map non-stopword tokens (≥6 chars)
    back to the ATC entries containing them. Lets the matcher catch inputs
    where the bare-token version of the substance is given but ATC stores it
    under a multi-word name (e.g. input "Tenofovir" → ATC has "tenofovir
    disoproxil" J05AF07 and "tenofovir alafenamide" J05AF13)."""
    by_token: dict[str, list[ATCEntry]] = {}
    for entry in by_code.values():
        if entry.level != 5:
            continue
        atc_norm = normalize(entry.name)
        for tok in atc_norm.split():
            if len(tok) < 6 or tok in TOKEN_STOPWORDS:
                continue
            lst = by_token.setdefault(tok, [])
            if entry not in lst:
                lst.append(entry)
    return by_token


def load_atc(path: Path) -> tuple[dict[str, ATCEntry], dict[str, list[ATCEntry]]]:
    """Returns (by_code, by_normalized_name).

    The source CSV has one row per (atc_code, route_of_administration, DDD)
    combination, so a single substance can repeat. We dedupe by atc_code so
    by_name's lists never contain the same code twice — that's important for
    multi-candidate detection (otherwise diclofenac would appear 5x because
    M01AB05 has 5 routes and we'd misclassify a clean exact match as
    "ambiguous, manual review").

    by_name remains a list to capture genuine cross-code clashes (e.g.,
    "acetylsalicylic acid" → A01AD05 + B01AC06 + N02BA01 in different
    anatomical groups — distinct ATC codes).
    """
    by_code: dict[str, ATCEntry] = {}
    by_name: dict[str, list[ATCEntry]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            code = (row.get("atc_code") or "").strip()
            name = (row.get("atc_name") or "").strip()
            if not code or not name:
                continue
            if code in by_code:
                continue  # already seen this code under another route
            lvl = atc_level(code)
            if lvl == 0:
                continue
            entry = ATCEntry(code=code, name=name, level=lvl,
                             parent_codes=atc_parents(code))
            by_code[code] = entry
            key = normalize(name)
            if key:
                by_name.setdefault(key, []).append(entry)
    return by_code, by_name


@dataclass
class ATCCombo:
    code: str
    ingredient_set: frozenset[str]   # normalized ingredient names
    raw_ingredients: str
    brand_name: str


def load_combinations(path: Path) -> list[ATCCombo]:
    out: list[ATCCombo] = []
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            code = (row.get("atc_code") or "").strip()
            ingredients = (row.get("ingredients") or "").strip()
            brand = (row.get("brand_name") or "").strip()
            if not code or not ingredients:
                continue
            # Ingredients column uses '/' as primary separator and includes
            # dosages — strip the dose info, keep the substance names.
            tokens: list[str] = []
            for raw in ingredients.split("/"):
                # Strip trailing dosage like "0.125 g" or "500 mg".
                cleaned = re.sub(
                    r"\s+\d[\d.,]*\s*(mg|g|ml|mcg|µg|iu|units?)\s*/?\s*\w*$",
                    "",
                    raw.strip(),
                    flags=re.I,
                )
                norm = normalize(cleaned)
                if norm:
                    tokens.append(norm)
            if len(tokens) < 2:
                continue
            out.append(ATCCombo(
                code=code,
                ingredient_set=frozenset(tokens),
                raw_ingredients=ingredients,
                brand_name=brand,
            ))
    return out


# ---------------------------------------------------------------------------
# NAPPI loading
# ---------------------------------------------------------------------------

NAPPI_COL_MAP = {
    "nappi_code":  ("nappi_code", "NAPPI Code", "NAPPI", "Code"),
    "generic_name":("generic_name", "Generic Name", "Generic", "Active Ingredient"),
    "brand_name":  ("brand_name", "Brand Name", "Brand", "Trade Name"),
    "ingredients": ("ingredients", "Ingredients", "Active Ingredients", "Composition"),
}


def _pick_col(row: dict[str, str], candidates: tuple[str, ...]) -> str:
    for c in candidates:
        v = row.get(c)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


@dataclass
class NappiRow:
    nappi_code: str
    generic_name: str
    brand_name: str
    ingredients: str


def load_nappi(path: Path) -> list[NappiRow]:
    out: list[NappiRow] = []
    with path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        for row in rdr:
            code = _pick_col(row, NAPPI_COL_MAP["nappi_code"])
            if not code:
                continue
            out.append(NappiRow(
                nappi_code=code,
                generic_name=_pick_col(row, NAPPI_COL_MAP["generic_name"]),
                brand_name=_pick_col(row, NAPPI_COL_MAP["brand_name"]),
                ingredients=_pick_col(row, NAPPI_COL_MAP["ingredients"]),
            ))
    return out


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

@dataclass
class MatchResult:
    nappi_code: str
    method: str           # exact | fuzzy | combo
    atc_code: str
    atc_name: str         # ATC-side substance / combo name
    confidence: float     # 1.0 for exact + combo, ratio for fuzzy
    source_field: str     # which NAPPI field produced the match
    source_value: str     # the value that matched
    alternatives: str = ""  # "code1:name1|code2:name2" — populated when the
                            # name matched >1 level-5 ATC entry. When set,
                            # the row goes to matched_review even if the
                            # primary match was nominally "exact".


def _try_exact(name: str, by_name: dict[str, list[ATCEntry]],
               source_field: str) -> MatchResult | None:
    """Return an exact match. If the same normalized name resolves to more
    than one level-5 ATC code (e.g. diclofenac → D11AX18 topical AND
    M01AB05 systemic AND M02AA15 topical M02 AND S01BC03 ophthalmic), we
    return the first as `atc_code` but stash the rest in `alternatives`
    and the caller will route the row to matched_review for manual pick.
    """
    key = normalize(name)
    if not key:
        return None
    candidates = by_name.get(key)
    if not candidates:
        return None
    level5 = [c for c in candidates if c.level == 5]
    if not level5:
        return None
    chosen = level5[0]
    alts = ""
    if len(level5) > 1:
        alts = "|".join(f"{e.code}:{e.name}" for e in level5[1:])
    return MatchResult(
        nappi_code="",
        method=METHOD_EXACT,
        atc_code=chosen.code,
        atc_name=chosen.name,
        confidence=1.0,
        source_field=source_field,
        source_value=name,
        alternatives=alts,
    )


def _try_combo(name: str, combos: list[ATCCombo],
               source_field: str) -> MatchResult | None:
    parts = split_combo(name)
    if len(parts) < 2:
        return None
    norm_parts = frozenset(normalize(p) for p in parts if normalize(p))
    if len(norm_parts) < 2:
        return None
    # Best match: exact set equality first; fall back to subset/superset with
    # >=2 overlap.
    best: tuple[float, ATCCombo] | None = None
    for combo in combos:
        if combo.ingredient_set == norm_parts:
            return MatchResult(
                nappi_code="",
                method=METHOD_COMBO,
                atc_code=combo.code,
                atc_name=combo.raw_ingredients,
                confidence=1.0,
                source_field=source_field,
                source_value=name,
            )
        overlap = len(combo.ingredient_set & norm_parts)
        if overlap >= 2:
            jaccard = overlap / len(combo.ingredient_set | norm_parts)
            if best is None or jaccard > best[0]:
                best = (jaccard, combo)
    if best and best[0] >= 0.6:
        return MatchResult(
            nappi_code="",
            method=METHOD_COMBO,
            atc_code=best[1].code,
            atc_name=best[1].raw_ingredients,
            confidence=best[0],
            source_field=source_field,
            source_value=name,
        )
    return None


def _try_fuzzy(name: str, by_name: dict[str, list[ATCEntry]],
               threshold: float, source_field: str) -> MatchResult | None:
    key = normalize(name)
    if not key:
        return None
    # Only fuzzy-match against level-5 substance names — fuzzy matching
    # against higher tier names would produce noise.
    best: tuple[float, ATCEntry] | None = None
    for atc_name_norm, entries in by_name.items():
        for entry in entries:
            if entry.level != 5:
                continue
            ratio = SequenceMatcher(None, key, atc_name_norm).ratio()
            if best is None or ratio > best[0]:
                best = (ratio, entry)
    if best is None:
        return None
    ratio, entry = best
    if ratio < threshold:
        return None
    return MatchResult(
        nappi_code="",
        method=METHOD_FUZZY,
        atc_code=entry.code,
        atc_name=entry.name,
        confidence=ratio,
        source_field=source_field,
        source_value=name,
    )


def _try_vendor_stripped(name: str, by_name: dict[str, list[ATCEntry]],
                         source_field: str) -> MatchResult | None:
    """Strip a leading/trailing SA vendor prefix and retry exact match.
    Result is reported with method=exact (the underlying match IS exact —
    we just had to peel a wrapper off first)."""
    stripped = strip_vendor_prefix(name)
    if stripped == name or not stripped:
        return None
    res = _try_exact(stripped, by_name, source_field)
    if res is not None:
        res.source_value = name  # keep the original NAPPI value visible
    return res


def _try_combo_first_ingredient(name: str, by_name: dict[str, list[ATCEntry]],
                                source_field: str) -> MatchResult | None:
    """For inputs like "Amoxicillin + Clavulanic Acid": match the first
    ingredient. Caller routes this to matched_review (low confidence) — the
    code only covers ONE of the substances, not the combination."""
    parts = split_combo(name)
    if len(parts) < 2:
        return None
    first = parts[0].strip()
    if not first:
        return None
    res = _try_exact(first, by_name, source_field)
    if res is None:
        return None
    res.method = METHOD_COMBO
    res.confidence = 0.5  # partial — only first ingredient matched
    res.source_value = name
    res.alternatives = (
        f"PARTIAL: only matched first of {len(parts)} ingredients "
        f"({first}). Other ingredients: " + ", ".join(parts[1:])
    )
    return res


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _try_token_search(name: str, by_name: dict[str, list[ATCEntry]],
                      by_token: dict[str, list[ATCEntry]],
                      source_field: str) -> MatchResult | None:
    """Tokenize the input; for each non-stopword token (≥6 chars), look it
    up against (a) full normalized ATC names and (b) ATC name tokens. If
    exactly ONE distinct ATC level-5 entry hits, return it; if multiple,
    return the first with the rest in `alternatives`. Confidence 0.7 so the
    row always goes to matched_review.

    Catches:
      - "Accord epirubicin 10 vial 5ml"    → epirubicin (single hit)
      - "Tenofovir"                        → tenofovir disoproxil + alafenamide
                                              (multi via token index → review)
    """
    if not name:
        return None
    tokens = [t for t in _TOKEN_RE.findall(name.lower())
              if len(t) >= 6 and t not in TOKEN_STOPWORDS]
    hits: list[ATCEntry] = []
    for tok in tokens:
        # (a) Full-name lookup — single-word ATC names like "amoxicillin".
        for c in by_name.get(tok, []):
            if c.level == 5:
                hits.append(c)
        # (b) Token index — multi-word ATC names like "tenofovir disoproxil".
        for c in by_token.get(tok, []):
            hits.append(c)
    # Dedupe by code, preserving order.
    seen: set[str] = set()
    unique_hits: list[ATCEntry] = []
    for h in hits:
        if h.code in seen:
            continue
        seen.add(h.code)
        unique_hits.append(h)
    if not unique_hits:
        return None
    chosen = unique_hits[0]
    alts = ""
    if len(unique_hits) > 1:
        alts = "TOKEN_MATCH (multi): " + "|".join(
            f"{e.code}:{e.name}" for e in unique_hits
        )
    else:
        alts = f"TOKEN_MATCH: {chosen.name}"
    return MatchResult(
        nappi_code="",
        method=METHOD_FUZZY,
        atc_code=chosen.code,
        atc_name=chosen.name,
        confidence=0.7,
        source_field=source_field,
        source_value=name,
        alternatives=alts,
    )


def match_row(row: NappiRow, by_name: dict[str, list[ATCEntry]],
              by_token: dict[str, list[ATCEntry]],
              combos: list[ATCCombo],
              fuzzy_threshold: float) -> MatchResult | None:
    """Pass order:
        1. exact normalized match
        2. vendor-prefix stripped exact match
        3. CSV-driven combination match (Pylera-style branded combos)
        4. first-ingredient fallback for "drugA + drugB" patterns (review)
        5. token search — token in name hits an INN, including multi-word
           ATC names via the reverse token index (review)
        6. fuzzy edit-distance match above threshold (review)

    Each pass tries generic_name first, then ingredients. First hit wins.
    """
    passes = (
        ("exact",       lambda v, f: _try_exact(v, by_name, f)),
        ("vendor",      lambda v, f: _try_vendor_stripped(v, by_name, f)),
        ("combo_csv",   lambda v, f: _try_combo(v, combos, f)),
        ("combo_first", lambda v, f: _try_combo_first_ingredient(v, by_name, f)),
        ("token",       lambda v, f: _try_token_search(v, by_name, by_token, f)),
        ("fuzzy",       lambda v, f: _try_fuzzy(v, by_name, fuzzy_threshold, f)),
    )
    for _label, fn in passes:
        for field_name, value in (("generic_name", row.generic_name),
                                  ("ingredients", row.ingredients)):
            if not value:
                continue
            res = fn(value, field_name)
            if res is not None:
                res.nappi_code = row.nappi_code
                return res
    return None


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


def write_outputs(
    out_dir: Path,
    matched_exact: list[MatchResult],
    matched_review: list[MatchResult],
    unmatched: list[NappiRow],
    by_code: dict[str, ATCEntry],
    atc_source_tag: str,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    def class_desc(atc_code: str, fallback: str) -> str:
        # For non-combination rows we know the level-5 entry is in by_code.
        entry = by_code.get(atc_code)
        return entry.name if entry else fallback

    def write_csv(path: Path, rows: list[MatchResult]) -> None:
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow([
                "nappi_code", "method", "atc_code", "atc_class_desc",
                "confidence", "source_field", "source_value", "alternatives",
            ])
            for r in rows:
                w.writerow([
                    r.nappi_code, r.method, r.atc_code,
                    class_desc(r.atc_code, r.atc_name),
                    f"{r.confidence:.4f}", r.source_field, r.source_value,
                    r.alternatives,
                ])

    write_csv(out_dir / "matched_exact.csv", matched_exact)
    write_csv(out_dir / "matched_review.csv", matched_review)

    with (out_dir / "unmatched.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["nappi_code", "generic_name", "brand_name", "ingredients"])
        for r in unmatched:
            w.writerow([r.nappi_code, r.generic_name, r.brand_name, r.ingredients])

    # SQL: UPDATEs for high-confidence matches only. Reviewer can opt-in
    # specific review rows by hand or by re-running with a curated CSV.
    sql_path = out_dir / "006_atc_backfill_data.sql"
    now_iso = datetime.now(tz=timezone.utc).isoformat(timespec="seconds")
    with sql_path.open("w", encoding="utf-8") as f:
        f.write(
            f"-- Generated by atc_backfill.py at {now_iso}\n"
            f"-- Source tag: {atc_source_tag}\n"
            f"-- Run AFTER migration 006_atc_backfill.sql.\n"
            f"-- Updates {len(matched_exact)} nappi_codes rows.\n"
            f"-- Idempotent: re-running with the same data is safe.\n\n"
            f"BEGIN;\n\n"
        )
        for r in matched_exact:
            desc = _sql_escape(class_desc(r.atc_code, r.atc_name))
            f.write(
                "UPDATE nappi_codes SET "
                f"atc_code = '{_sql_escape(r.atc_code)}', "
                f"atc_class_desc = '{desc}', "
                f"atc_match_method = '{r.method}', "
                f"atc_source = '{_sql_escape(atc_source_tag)}', "
                "atc_matched_at = NOW(), "
                "updated_at = NOW() "
                f"WHERE nappi_code = '{_sql_escape(r.nappi_code)}';\n"
            )
        f.write("\nCOMMIT;\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

DEFAULT_ATC_DIR = Path(__file__).resolve().parent.parent / "data" / "atc"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--nappi-csv", required=True, type=Path)
    p.add_argument("--atc-csv", type=Path,
                   default=DEFAULT_ATC_DIR / "WHO_ATC-DDD_2026-04-25.csv")
    p.add_argument("--combinations-csv", type=Path,
                   default=DEFAULT_ATC_DIR / "WHO_ATC-DDD-combinations_2026-04-25.csv")
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--atc-source", default="atcd-2026-04-25")
    p.add_argument("--fuzzy-threshold", type=float,
                   default=DEFAULT_FUZZY_THRESHOLD)
    args = p.parse_args(argv)

    if not args.atc_csv.exists():
        print(f"ATC CSV not found: {args.atc_csv}", file=sys.stderr)
        return 2
    if not args.nappi_csv.exists():
        print(f"NAPPI CSV not found: {args.nappi_csv}", file=sys.stderr)
        return 2

    print(f"Loading ATC index from {args.atc_csv} ...")
    by_code, by_name = load_atc(args.atc_csv)
    by_token = build_token_index(by_code)
    print(f"  {len(by_code)} ATC entries loaded "
          f"({sum(1 for e in by_code.values() if e.level == 5)} substance-level, "
          f"{len(by_token)} indexed tokens)")

    print(f"Loading combinations from {args.combinations_csv} ...")
    combos = load_combinations(args.combinations_csv)
    print(f"  {len(combos)} combination entries loaded")

    print(f"Loading NAPPI export from {args.nappi_csv} ...")
    nappi_rows = load_nappi(args.nappi_csv)
    print(f"  {len(nappi_rows)} NAPPI rows loaded")

    matched_exact: list[MatchResult] = []
    matched_review: list[MatchResult] = []
    unmatched: list[NappiRow] = []

    for i, row in enumerate(nappi_rows, 1):
        if i % 500 == 0:
            print(f"  matched {i}/{len(nappi_rows)} ...")
        res = match_row(row, by_name, by_token, combos, args.fuzzy_threshold)
        if res is None:
            unmatched.append(row)
        elif (res.method == METHOD_FUZZY
              or res.alternatives
              or res.confidence < 1.0):
            # Multi-candidate, partial combo, or any sub-1.0 confidence
            # match → reviewer picks. Only a fully unambiguous 1.0 match
            # auto-lands in matched_exact.
            matched_review.append(res)
        else:
            matched_exact.append(res)

    print(f"\nResults:")
    print(f"  exact/combo (high confidence): {len(matched_exact)}")
    print(f"  fuzzy (review required):       {len(matched_review)}")
    print(f"  unmatched:                     {len(unmatched)}")

    write_outputs(args.out_dir, matched_exact, matched_review, unmatched,
                  by_code, args.atc_source)

    print(f"\nWrote outputs to {args.out_dir}")
    print(f"  matched_exact.csv          ({len(matched_exact)} rows)")
    print(f"  matched_review.csv         ({len(matched_review)} rows — eyeball these)")
    print(f"  unmatched.csv              ({len(unmatched)} rows)")
    print(f"  006_atc_backfill_data.sql  (UPDATE statements for matched_exact)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

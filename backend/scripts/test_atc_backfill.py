"""
Unit tests for atc_backfill.py — proves the matcher logic is correct in
isolation, independent of whether the SQL has been applied yet.

Run from the backend root:

    .venv/bin/python -m unittest scripts.test_atc_backfill -v

or directly:

    .venv/bin/python scripts/test_atc_backfill.py

No external dependencies — stdlib unittest only.
"""

from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

# Make the backend root importable so `scripts.atc_backfill` resolves.
HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND))

from scripts import atc_backfill as atc  # noqa: E402


ATC_DEFAULT = BACKEND / "data" / "atc" / "WHO_ATC-DDD_2026-04-25.csv"
COMBOS_DEFAULT = BACKEND / "data" / "atc" / "WHO_ATC-DDD-combinations_2026-04-25.csv"


# ---------------------------------------------------------------------------
# Pure functions — fast, no I/O
# ---------------------------------------------------------------------------

class TestNormalize(unittest.TestCase):

    def test_lowercases_and_strips(self):
        self.assertEqual(atc.normalize("  AmoxiCillin  "), "amoxicillin")

    def test_strips_single_salt_suffix(self):
        self.assertEqual(atc.normalize("amoxicillin trihydrate"), "amoxicillin")
        self.assertEqual(atc.normalize("amlodipine besylate"), "amlodipine")
        self.assertEqual(atc.normalize("ranitidine hcl"), "ranitidine")

    def test_strips_chained_salts(self):
        # "atorvastatin calcium trihydrate" → "atorvastatin" (two passes).
        self.assertEqual(
            atc.normalize("atorvastatin calcium trihydrate"),
            "atorvastatin",
        )

    def test_collapses_punctuation_and_whitespace(self):
        self.assertEqual(atc.normalize("co-amoxiclav  /  500"),
                         "co amoxiclav 500")

    def test_empty_input(self):
        self.assertEqual(atc.normalize(""), "")
        self.assertEqual(atc.normalize(None), "")  # type: ignore[arg-type]


class TestSplitCombo(unittest.TestCase):

    def test_no_separator_returns_single(self):
        self.assertEqual(atc.split_combo("amoxicillin"), ["amoxicillin"])

    def test_plus_separator(self):
        parts = atc.split_combo("amoxicillin + clavulanic acid")
        self.assertEqual(len(parts), 2)
        self.assertIn("amoxicillin", [p.lower() for p in parts])
        self.assertIn("clavulanic acid", [p.lower() for p in parts])

    def test_slash_separator(self):
        parts = atc.split_combo("ibuprofen / paracetamol")
        self.assertEqual(len(parts), 2)

    def test_three_ingredient_combo(self):
        parts = atc.split_combo("Paracetamol + Aspirin + Caffeine")
        self.assertEqual(len(parts), 3)


class TestStripVendorPrefix(unittest.TestCase):

    def test_leading_dash_prefix(self):
        self.assertEqual(atc.strip_vendor_prefix("Adco-Dol"), "Dol")
        self.assertEqual(atc.strip_vendor_prefix("Accord-carboplatin"),
                         "carboplatin")

    def test_leading_space_prefix(self):
        self.assertEqual(atc.strip_vendor_prefix("Cipla atorvastatin"),
                         "atorvastatin")

    def test_trailing_vendor(self):
        self.assertEqual(atc.strip_vendor_prefix("Bicalutamide accord"),
                         "Bicalutamide")
        self.assertEqual(atc.strip_vendor_prefix("Lenalidomide cipla"),
                         "Lenalidomide")

    def test_no_vendor_returns_unchanged(self):
        self.assertEqual(atc.strip_vendor_prefix("paracetamol"), "paracetamol")

    def test_empty_input(self):
        self.assertEqual(atc.strip_vendor_prefix(""), "")


class TestAtcLevel(unittest.TestCase):

    def test_each_level(self):
        self.assertEqual(atc.atc_level("A"),       1)
        self.assertEqual(atc.atc_level("A01"),     2)
        self.assertEqual(atc.atc_level("A01A"),    3)
        self.assertEqual(atc.atc_level("A01AB"),   4)
        self.assertEqual(atc.atc_level("A01AB01"), 5)
        self.assertEqual(atc.atc_level("nonsense"), 0)

    def test_parents(self):
        # C09AA05 (enalapril) parents.
        self.assertEqual(
            atc.atc_parents("C09AA05"),
            ["C", "C09", "C09A", "C09AA"],
        )


# ---------------------------------------------------------------------------
# Integration tests against the real ATC index. Skipped if the data isn't
# present (so this file still runs in a clean checkout).
# ---------------------------------------------------------------------------

@unittest.skipUnless(ATC_DEFAULT.exists(),
                     f"ATC index CSV missing at {ATC_DEFAULT}")
class TestMatcherIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.by_code, cls.by_name = atc.load_atc(ATC_DEFAULT)
        cls.by_token = atc.build_token_index(cls.by_code)
        cls.combos = (atc.load_combinations(COMBOS_DEFAULT)
                      if COMBOS_DEFAULT.exists() else [])

    # -- Level-5 universe sanity check ------------------------------------

    def test_level5_count_in_expected_range(self):
        # The 2026-04-25 release has ~5,678 substance-level entries. Allow
        # ±200 wiggle room for future updates without breaking this test.
        n = sum(1 for e in self.by_code.values() if e.level == 5)
        self.assertGreater(n, 5400)
        self.assertLess(n, 6000)

    def test_no_duplicate_codes_in_index(self):
        # load_atc dedupes by atc_code; verify by_name lists never contain
        # the same code twice for one key.
        for key, entries in self.by_name.items():
            codes = [e.code for e in entries]
            self.assertEqual(len(codes), len(set(codes)),
                             f"dup codes for normalized name {key}: {codes}")

    # -- Spot-check known canonical mappings ------------------------------

    def _exact_code_for(self, generic: str) -> str | None:
        res = atc._try_exact(generic, self.by_name, "test")
        return res.atc_code if res else None

    def test_known_single_code_substances(self):
        # Each of these has exactly one level-5 ATC entry — the matcher
        # should always pick it deterministically.
        expected = {
            "amoxicillin":     "J01CA04",
            "atorvastatin":    "C10AA05",
            "metformin":       "A10BA02",
            "amlodipine":      "C08CA01",
            "losartan":        "C09CA01",
            "warfarin":        "B01AA03",
            "clopidogrel":     "B01AC04",
            "gabapentin":      "N02BF01",
            "lamotrigine":     "N03AX09",
            "clarithromycin":  "J01FA09",
            "ticagrelor":      "B01AC24",
            "bisoprolol":      "C07AB07",
        }
        for generic, code in expected.items():
            with self.subTest(generic=generic):
                self.assertEqual(self._exact_code_for(generic), code)

    def test_known_multi_code_substances_route_to_alternatives(self):
        # Diclofenac is in 4 anatomical groups; ibuprofen in 4-5. Both
        # should produce a primary match + an alternatives list.
        for generic in ("diclofenac", "ibuprofen", "acetylsalicylic acid"):
            with self.subTest(generic=generic):
                res = atc._try_exact(generic, self.by_name, "test")
                self.assertIsNotNone(res)
                self.assertNotEqual(res.alternatives, "",
                    f"{generic} should have alternatives populated")

    def test_salt_form_strip_finds_substance(self):
        # NAPPI typically stores "amoxicillin trihydrate"; ATC has bare
        # "amoxicillin". Strip-and-match must work.
        self.assertEqual(self._exact_code_for("amoxicillin trihydrate"),
                         "J01CA04")
        self.assertEqual(self._exact_code_for("ranitidine hcl"),
                         "A02BA02")
        self.assertEqual(self._exact_code_for("atorvastatin calcium"),
                         "C10AA05")

    # -- Vendor-prefix pass -----------------------------------------------

    def test_vendor_strip_recovers_match(self):
        res = atc._try_vendor_stripped("Accord-carboplatin",
                                       self.by_name, "test")
        self.assertIsNotNone(res)
        self.assertEqual(res.atc_code, "L01XA02")
        # Original value should be preserved in the result.
        self.assertEqual(res.source_value, "Accord-carboplatin")

    def test_vendor_strip_skips_unprefixed(self):
        # "amoxicillin" alone has no vendor wrapper to strip; should return None
        # so the caller falls through to other passes.
        self.assertIsNone(
            atc._try_vendor_stripped("amoxicillin", self.by_name, "test"))

    # -- Combo passes -----------------------------------------------------

    def test_combo_first_ingredient_match(self):
        res = atc._try_combo_first_ingredient(
            "Amoxicillin + Clavulanic Acid", self.by_name, "test")
        self.assertIsNotNone(res)
        self.assertEqual(res.method, atc.METHOD_COMBO)
        self.assertEqual(res.atc_code, "J01CA04")
        self.assertEqual(res.confidence, 0.5)
        self.assertIn("PARTIAL", res.alternatives)

    def test_combo_first_ingredient_skips_single(self):
        # Not a combo — should return None so other passes run.
        self.assertIsNone(atc._try_combo_first_ingredient(
            "amoxicillin", self.by_name, "test"))

    # -- Token search -----------------------------------------------------

    def test_token_search_finds_embedded_inn(self):
        res = atc._try_token_search(
            "Accord epirubicin 10 vial 5ml",
            self.by_name, self.by_token, "test")
        self.assertIsNotNone(res)
        self.assertEqual(res.atc_code, "L01DB03")  # epirubicin

    def test_token_search_via_reverse_index(self):
        # Bare "Tenofovir" — ATC has only "tenofovir disoproxil" (J05AF07)
        # and "tenofovir alafenamide" (J05AF13) at level 5. Reverse token
        # index must surface both as candidates.
        res = atc._try_token_search(
            "Tenofovir", self.by_name, self.by_token, "test")
        self.assertIsNotNone(res)
        self.assertTrue(res.atc_code.startswith("J05AF"))
        # When multiple, alternatives must list the others.
        self.assertIn("J05AF", res.alternatives)


# ---------------------------------------------------------------------------
# End-to-end: run the script's match_row over the bundled test sample CSV
# and assert the bucket counts match what we shipped.
# ---------------------------------------------------------------------------

@unittest.skipUnless(ATC_DEFAULT.exists(),
                     f"ATC index CSV missing at {ATC_DEFAULT}")
class TestEndToEndOnSample(unittest.TestCase):

    SAMPLE = HERE / "_atc_test_sample.csv"

    def test_sample_bucket_counts(self):
        self.assertTrue(self.SAMPLE.exists(),
                        f"test sample missing at {self.SAMPLE}")
        with tempfile.TemporaryDirectory() as tmp:
            argv = [
                "--nappi-csv", str(self.SAMPLE),
                "--atc-csv",   str(ATC_DEFAULT),
                "--combinations-csv", str(COMBOS_DEFAULT),
                "--out-dir",   tmp,
                "--fuzzy-threshold", "0.92",
            ]
            rc = atc.main(argv)
            self.assertEqual(rc, 0)

            # Parse the output CSVs and verify the buckets are what the
            # README documents (9 exact / 5 review / 1 unmatched). If the
            # matcher regresses these will tip immediately.
            def count(path: Path) -> int:
                with path.open() as f:
                    return sum(1 for _ in csv.DictReader(f))

            tmp_p = Path(tmp)
            self.assertEqual(count(tmp_p / "matched_exact.csv"),  9)
            self.assertEqual(count(tmp_p / "matched_review.csv"), 5)
            self.assertEqual(count(tmp_p / "unmatched.csv"),      1)


if __name__ == "__main__":
    unittest.main(verbosity=2)

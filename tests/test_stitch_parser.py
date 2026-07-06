import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count
from loopdreams_qa.stitch_parser import tokenize_round


class TestStitchInChain1Space(unittest.TestCase):
    def test_stitch_in_next_ch1_space_recognized(self):
        # Real phrasing found on a real sample (Jul 2, third throw-blanket
        # batch): moss/linen stitch's repeat unit written as "sc in next
        # ch-1 sp" (the chain-1 space itself as the stitch's target noun)
        # plus a separate "skip next st", instead of the earlier-seen
        # "skip the ch-1 space, sc in next sc" ordering. Neither half of
        # this new ordering matched any prior clause shape, which
        # regressed a previously-clean moss sample to an "unrecognized
        # clause" warning.
        clauses = tokenize_round(
            "Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * across"
        )
        types = [c.clause_type for c in clauses]
        self.assertEqual(types, ["positional_single", "chain", "positional_single", "skip", "repeat_close"])
        stitch_clause = clauses[2]
        self.assertEqual(stitch_clause.stitch, "sc")
        self.assertEqual(stitch_clause.consumes, 1)
        self.assertEqual(stitch_clause.produces, 1)
        skip_clause = clauses[3]
        self.assertEqual(skip_clause.consumes, 1)
        self.assertEqual(skip_clause.produces, 0)

    def test_skip_next_st_recognized_not_just_skip_first(self):
        # _RE_SKIP_POSITIONAL previously only matched "skip (the) first
        # st" -- "skip next st"/"skip last st" fell through to unknown.
        for word in ("first", "next", "last"):
            clauses = tokenize_round(f"skip {word} st")
            self.assertEqual(len(clauses), 1)
            self.assertEqual(clauses[0].clause_type, "skip")
            self.assertEqual(clauses[0].consumes, 1)
            self.assertEqual(clauses[0].produces, 0)

    def test_moss_style_row_with_new_phrasing_verifies_end_to_end(self):
        # Confirms the fix doesn't just tokenize correctly in isolation --
        # the full stitch-count check resolves this new phrasing cleanly
        # using the existing moss/linen "chains count inside the repeat
        # unit" convention, exactly as it did for the older phrasing.
        raw = (
            "Test Blanket\n"
            "MATERIALS\n"
            "Gauge: 18 sc x 20 rows = 4 in [10 cm]\n"
            "Terminology: US\n"
            "Yarn: Test yarn\n"
            "Hook: 4.0 mm\n"
            "ABBREVIATIONS\n"
            "ch = chain, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 22, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (21 sts)\n"
            "Row 2: Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * across. Ch 1, turn. (21 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        issues = stitch_count.check(pattern)
        row2_issues = [i for i in issues if i.location == "Row 2"]
        self.assertEqual(row2_issues, [])


class TestFoundationIntoChainParenthetical(unittest.TestCase):
    def test_inline_skip_clarification_recognized(self):
        # Real phrasing found on a real sample (waffle, Jul 6 batch):
        # "Dc in 3rd ch from hook (skipped 2-ch does not count as st) and
        # in each ch across." -- LoopDreams applying the exact corrected
        # Waffle Stitch convention from checks/known_constructions.py, but
        # with a new parenthetical clarification inserted between the
        # ordinal clause and "and in each ch across" that the previous
        # regex didn't allow for, which fell through to unrecognized and
        # produced a false "non-stitch row" warning on an otherwise
        # correct, already-fixed row.
        clauses = tokenize_round(
            "Dc in 3rd ch from hook (skipped 2-ch does not count as st) and in each ch across"
        )
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "foundation_into_chain")
        self.assertEqual(c.stitch, "dc")
        self.assertEqual(c.explicit_count, 3)

    def test_plain_shape_without_parenthetical_still_works(self):
        clauses = tokenize_round("Sc in 2nd ch from hook and in each ch across")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "foundation_into_chain")
        self.assertEqual(clauses[0].explicit_count, 2)


class TestCornerClause(unittest.TestCase):
    def test_simple_stitch_corner_produces_count(self):
        # A plain stitch in a corner (every real sample seen so far, always
        # sc) has a fixed ratio, so the count-per-corner math is genuinely
        # knowable: "3 sc in corner" produces exactly 3 stitches.
        clauses = tokenize_round("3 sc in corner")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "corner")
        self.assertEqual(c.explicit_count, 3)
        self.assertFalse(c.is_compound)
        self.assertEqual(c.produces, 3)
        self.assertIsNone(c.unverifiable_reason)

    def test_compound_stitch_corner_is_unverifiable_not_guessed(self):
        # Real bug (never triggered by any real sample, every corner seen
        # so far is plain sc): a compound stitch in a corner used to
        # silently fall back to `(prod or 1) * count`, guessing 1 produced
        # stitch per repeat instead of leaving it unverifiable -- the only
        # place in the codebase that guessed instead of reporting "can't
        # verify" for a compound stitch. Must now leave produces unset and
        # carry a specific unverifiable_reason, exactly like every other
        # compound-stitch clause shape (each_st_across/around, etc.).
        clauses = tokenize_round("3 bo in corner", custom_compound=frozenset({"bo"}))
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "corner")
        self.assertEqual(c.explicit_count, 3)
        self.assertTrue(c.is_compound)
        self.assertIsNone(c.produces)
        self.assertIn("bo", c.unverifiable_reason)


if __name__ == "__main__":
    unittest.main()

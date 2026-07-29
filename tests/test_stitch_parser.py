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
        for word in ("next", "last"):
            clauses = tokenize_round(f"skip {word} st")
            self.assertEqual(len(clauses), 1)
            self.assertEqual(clauses[0].clause_type, "skip")
            self.assertEqual(clauses[0].consumes, 1)
            self.assertEqual(clauses[0].produces, 0)
        # "skip first st" is the one position word that gets a different
        # produces value -- see TestSkipFirstStAsRowOpener below for why.
        clauses = tokenize_round("skip first st")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "skip")
        self.assertEqual(clauses[0].consumes, 1)
        self.assertEqual(clauses[0].produces, 1)

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


class TestSkipFirstStAsRowOpener(unittest.TestCase):
    def test_bare_skip_first_st_opening_a_row_produces_one(self):
        # Real sample (Waffle Tote Bag, post-loopdreams#318 wording fix,
        # Jul 26 batch): that PR dropped the row-opening "Ch 2 (counts as
        # dc)" restatement after real tester feedback showed it read as
        # two separate turning chains -- the chain is already made by the
        # PREVIOUS row's own trailing "Ch 2, turn.", so nothing in THIS
        # row's text needs to say so again. Before this fix, the checker
        # read the row's now-bare "skip first st" as a genuine, unbalanced
        # decrease (consumes=1, produces=0) and flagged every waffle row
        # as a stitch-count mismatch.
        clauses = tokenize_round(
            "Skip first st, *fpdc around next st, dc in next 2 sts; "
            "rep from * to last 2 sts, fpdc around next st, dc in top of ch. Ch 2, turn."
        )
        self.assertEqual(clauses[0].clause_type, "skip")
        self.assertEqual(clauses[0].consumes, 1)
        self.assertEqual(clauses[0].produces, 1)

    def test_leading_counted_chain_still_balances_the_old_way(self):
        # The older "Ch 2 (counts as dc), skip first st, ..." phrasing
        # still works exactly as before -- the skip clause here is index
        # 1, not 0, so the new row-opener adjustment never fires; the
        # counted_chain clause (produces=1) is what balances it, same as
        # always.
        clauses = tokenize_round(
            "Ch 2 (counts as dc), skip first st, *fpdc around next st, dc in next 2 sts; "
            "rep from * to last 2 sts, fpdc around next st, dc in top of ch. Ch 2, turn."
        )
        self.assertEqual(clauses[0].clause_type, "counted_chain")
        self.assertEqual(clauses[0].produces, 1)
        self.assertEqual(clauses[1].clause_type, "skip")
        self.assertEqual(clauses[1].consumes, 1)
        self.assertEqual(clauses[1].produces, 0)

    def test_skip_first_st_mid_row_not_touched(self):
        # Scoping check: "skip first st" only gets the row-opener
        # adjustment at clause index 0. A (synthetic) row where it shows up
        # later must be left as a genuine decrease -- never seen in a real
        # LoopDreams sample, but the fix must not silently reinterpret one
        # if it existed.
        clauses = tokenize_round("Sc in next st, skip first st, sc in next st")
        skip_clause = next(c for c in clauses if c.clause_type == "skip")
        self.assertEqual(skip_clause.consumes, 1)
        self.assertEqual(skip_clause.produces, 0)

    def test_waffle_tote_bag_row_verifies_end_to_end(self):
        # Confirms the fix doesn't just tokenize correctly in isolation --
        # the full stitch-count check resolves the new waffle phrasing
        # cleanly, matching the real deployed generator's output (dry-run
        # against Tote Bag/waffle, 14x16in/24in handles, Jul 26 QA check).
        raw = (
            "Waffle Tote Bag\n"
            "MATERIALS\n"
            "Gauge: 5 sts x 2.5 rows = 1 in\n"
            "Terminology: US\n"
            "Yarn: Test yarn\n"
            "Hook: 4.0 mm\n"
            "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, fpdc = front post double crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation: Ch 71.\n"
            "Row 1: Dc in 3rd ch from hook (skipped 2-ch does not count as st) and in each ch across. Ch 2, turn. (69 sts)\n"
            "Row 2: Skip first st, *fpdc around next st, dc in next 2 sts; rep from * to last 2 sts, fpdc around next st, dc in top of ch. Ch 2, turn. (69 sts)\n"
            "Row 3: Skip first st, *dc in next st, fpdc around next 2 sts; rep from * to last 2 sts, dc in next st, dc in top of ch. Fasten off. (69 sts)\n"
        )
        pattern = parse(raw)
        issues = stitch_count.check(pattern)
        stitch_count_errors = [i for i in issues if i.category == "stitch_count"]
        self.assertEqual(stitch_count_errors, [])


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
        # "zz" is an arbitrary stand-in custom-compound token here, not tied
        # to any real abbreviation -- "bo" itself no longer works as this
        # placeholder as of the Tote Bag bobble fix (Jul 29 batch), which
        # gave "bo" a real, fixed, always-known (1, 1) ratio in
        # abbreviations.STITCH_MATH (see there for why), so it would no
        # longer take the compound/unverifiable path this test exercises.
        clauses = tokenize_round("3 zz in corner", custom_compound=frozenset({"zz"}))
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "corner")
        self.assertEqual(c.explicit_count, 3)
        self.assertTrue(c.is_compound)
        self.assertIsNone(c.produces)
        self.assertIn("zz", c.unverifiable_reason)


class TestMittensClauseShapes(unittest.TestCase):
    """New clause shapes found on a real sample (mittens, Jul 7 batch) --
    the first continuous-spiral/amigurumi-style construction this project
    has QA'd, with a thumb gusset and drawstring cinch closures."""

    def test_back_loop_only_each_st_around(self):
        clauses = tokenize_round("Sc in the back loop only of each st around")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "each_st_around")
        self.assertEqual(c.stitch, "sc")
        self.assertEqual(c.consumes, 1)
        self.assertEqual(c.produces, 1)

    def test_each_remaining_st_around(self):
        clauses = tokenize_round("sc in each remaining st around")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "each_st_around")

    def test_bare_sc2tog_recognized_with_fixed_ratio(self):
        clauses = tokenize_round("*sc2tog")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "literal_count")
        self.assertEqual(c.stitch, "sc2tog")
        self.assertEqual(c.consumes, 2)
        self.assertEqual(c.produces, 1)

    def test_bare_unrecognized_token_not_forced(self):
        # A bare token with no known fixed ratio (unlike sc2tog) has nothing
        # to anchor consumes/produces to -- must fall through to unknown
        # rather than guessing.
        clauses = tokenize_round("bloop")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "unknown")

    def test_loop_variant_stitches_recognized_with_fixed_1to1_ratio(self):
        # Real samples (LoopDreams generator, real production patterns): bl
        # sc/fl sc/hhdc/wc st are each a single insertion-point variant of an
        # existing base stitch (back/front loop only, front-loop-pull-through,
        # or the post below), not a compound/decorative stitch with a
        # pattern-defined ratio -- every instance still consumes exactly 1
        # previous-row stitch and produces exactly 1 current-row stitch.
        # Previously entirely absent from this tool's known tokens, so every
        # row using one came back as a mass of "unrecognized clause" findings.
        for phrase, stitch in [
            ("32 bl sc in next 32 sts", "bl sc"),
            ("32 fl sc in next 32 sts", "fl sc"),
            ("32 hhdc in next 32 sts", "hhdc"),
            ("32 wc st in next 32 sts", "wc st"),
        ]:
            clauses = tokenize_round(phrase)
            self.assertEqual(len(clauses), 1, phrase)
            c = clauses[0]
            self.assertEqual(c.clause_type, "literal_count", phrase)
            self.assertEqual(c.stitch, stitch, phrase)
            self.assertEqual(c.consumes, 32, phrase)
            self.assertEqual(c.produces, 32, phrase)

    def test_loop_variant_stitches_recognized_at_start_of_row(self):
        # Real row shape: "Hhdc in 3rd ch from hook and in each ch across."
        # (Title-cased at the start of a sentence) -- confirms case-
        # insensitive lookup, not just the mid-sentence lowercase form above.
        for phrase in [
            "Hhdc in 3rd ch from hook and in each ch across",
            "Wc st in 2nd ch from hook and in each ch across",
            "Bl sc in 2nd ch from hook and in each ch across",
        ]:
            clauses = tokenize_round(phrase)
            self.assertEqual([c for c in clauses if c.clause_type == "unknown"], [], phrase)

    def test_multi_into_each_next(self):
        clauses = tokenize_round("2 sc in each of next 2 sts")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "literal_count")
        self.assertEqual(c.stitch, "sc")
        self.assertEqual(c.consumes, 2)
        self.assertEqual(c.produces, 4)

    def test_each_of_position_extended_to_next(self):
        clauses = tokenize_round("sc in each of next 12 sts")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "literal_count")
        self.assertEqual(c.consumes, 12)
        self.assertEqual(c.produces, 12)

    def test_held_aside(self):
        clauses = tokenize_round("Place the next 10 sts on a holder or scrap yarn (thumb gusset)")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "held_aside")
        self.assertEqual(c.explicit_count, 10)
        self.assertEqual(c.consumes, 10)
        self.assertEqual(c.produces, 0)

    def test_bridge_chain(self):
        clauses = tokenize_round("Ch 2 to bridge the gap")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "bridge_chain")
        self.assertEqual(c.explicit_count, 2)

    def test_each_st_to_marker_unverifiable(self):
        clauses = tokenize_round("Sc in each st to the marked gusset sts")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "each_st_to_marker")
        self.assertIsNone(c.consumes)
        self.assertIsNotNone(c.unverifiable_reason)

    def test_held_gusset_resume(self):
        clauses = tokenize_round("Sc in each of the 10 held gusset sts")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "held_gusset_resume")
        self.assertEqual(c.consumes, 10)
        self.assertEqual(c.produces, 10)

    def test_evenly_across_bridge(self):
        clauses = tokenize_round("then sc 2 sts evenly across the bridge chain")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "literal_count")
        self.assertEqual(c.consumes, 0)
        self.assertEqual(c.produces, 2)

    def test_marker_and_colour_change_notes(self):
        for text in [
            "Place a marker in next 4 sts (gusset sts)",
            "Place a stitch marker — work in a continuous spiral from here",
            "changing to Colour 2 — Moss in the last st",
        ]:
            clauses = tokenize_round(text)
            self.assertEqual(len(clauses), 1, text)
            self.assertEqual(clauses[0].clause_type, "note", text)
            self.assertEqual(clauses[0].consumes, 0, text)

    def test_drawstring_closure_recognized_not_unknown(self):
        clauses = tokenize_round(
            "Fasten off, leaving a long tail. Thread the tail through the front loop of each "
            "remaining stitch, pull tight to close the fingertip opening, and weave in the end"
        )
        types = [c.clause_type for c in clauses]
        self.assertNotIn("unknown", types)
        self.assertIn("fasten_off", types)
        self.assertTrue(all(t in ("fasten_off", "closure") for t in types))

    def test_plain_weave_in_ends_recognized_not_unknown(self):
        # Real, by far the most common closing phrasing (LoopDreams
        # generator, every non-amigurumi construction): "Fasten off, weave
        # in ends." -- plural, no "and"/"the" at all, distinct from the
        # drawstring-cinch single-tail form above. Previously only the
        # singular "weave in the end" matched, so this fell through as an
        # unrecognized clause on essentially every pattern's last row.
        clauses = tokenize_round("Fasten off, weave in ends")
        types = [c.clause_type for c in clauses]
        self.assertNotIn("unknown", types)
        self.assertIn("fasten_off", types)


if __name__ == "__main__":
    unittest.main()

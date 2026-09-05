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


class TestSkipFirstChainsFoundationClause(unittest.TestCase):
    def test_singular_chain_form_sc(self):
        # Real, current, widely-used generator output (loopdreams generate-
        # pattern/builders.ts's skipChainsClause() helper, used across most
        # flat-row builders): "Skip the first 1 chain from the hook (it
        # doesn't count as a stitch). Sc in the next chain and in each ch
        # across." A loopdreams batch-test run against production (Aug 1
        # 2026) flagged this exact shape as an "unrecognized clause" on Row
        # 1 of nearly the whole flat-panel matrix (Scarf, Sweater, Tote Bag,
        # Throw Blanket, Dishcloth, Cardigan, square Coaster).
        clauses = tokenize_round(
            "Skip the first 1 chain from the hook (it doesn't count as a stitch). "
            "Sc in the next chain and in each ch across"
        )
        self.assertEqual(len(clauses), 2)
        skip_clause, stitch_clause = clauses
        self.assertEqual(skip_clause.clause_type, "skip_first_chains_from_hook")
        self.assertEqual(skip_clause.explicit_count, 1)
        self.assertEqual(skip_clause.consumes, 0)
        self.assertEqual(skip_clause.produces, 0)
        self.assertEqual(stitch_clause.clause_type, "foundation_into_chain")
        self.assertEqual(stitch_clause.stitch, "sc")
        self.assertEqual(stitch_clause.explicit_count, 2)  # skip 1 -> starts in the 2nd ch from hook

    def test_plural_chains_form_dc(self):
        clauses = tokenize_round(
            "Skip the first 3 chains from the hook (they don't count as a stitch). "
            "Dc in the next chain and in each ch across"
        )
        self.assertEqual(len(clauses), 2)
        skip_clause, stitch_clause = clauses
        self.assertEqual(skip_clause.clause_type, "skip_first_chains_from_hook")
        self.assertEqual(skip_clause.explicit_count, 3)
        self.assertEqual(stitch_clause.clause_type, "foundation_into_chain")
        self.assertEqual(stitch_clause.stitch, "dc")
        self.assertEqual(stitch_clause.explicit_count, 4)  # skip 3 -> starts in the 4th ch from hook

    def test_hdc_variant(self):
        clauses = tokenize_round(
            "Skip the first 2 chains from the hook (they don't count as a stitch). "
            "Hdc in the next chain and in each ch across"
        )
        self.assertEqual(len(clauses), 2)
        stitch_clause = clauses[1]
        self.assertEqual(stitch_clause.clause_type, "foundation_into_chain")
        self.assertEqual(stitch_clause.stitch, "hdc")
        self.assertEqual(stitch_clause.explicit_count, 3)  # skip 2 -> starts in the 3rd ch from hook

    def test_unpaired_next_chain_clause_left_unverifiable_not_misread(self):
        # Scoping check: without the preceding skip clause, the starting
        # position genuinely isn't stated, so this must NOT be silently
        # treated as some default ordinal -- it should fall through to an
        # unverifiable, not-"unknown", not-a-guessed-foundation clause.
        clauses = tokenize_round("Sc in the next chain and in each ch across")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "foundation_stitch_in_next_chain")
        self.assertIsNone(c.consumes)
        self.assertIsNone(c.produces)
        self.assertIsNotNone(c.unverifiable_reason)

    def test_split_foundation_row_verifies_end_to_end(self):
        # Confirms the fix doesn't just tokenize correctly in isolation --
        # the full stitch-count check resolves the split "skip the first N
        # chains .../<stitch> in the next chain..." shape exactly as it
        # already resolves the single-clause ordinal phrasing.
        raw = (
            "Test Scarf\n"
            "MATERIALS\n"
            "Gauge: 14 sc x 16 rows = 4 in [10 cm]\n"
            "Terminology: US\n"
            "Yarn: Test yarn\n"
            "Hook: 5.0 mm\n"
            "ABBREVIATIONS\n"
            "ch = chain, sc = single crochet\n"
            "PATTERN STEPS\n"
            "Foundation: Ch 22, turn.\n"
            "Row 1: Skip the first 1 chain from the hook (it doesn't count as a stitch). "
            "Sc in the next chain and in each ch across. Ch 1, turn. (21 sts)\n"
            "Row 2: Sc in each st across. Ch 1, turn. (21 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (21 sts)\n"
        )
        pattern = parse(raw)
        issues = stitch_count.check(pattern)
        row1_issues = [i for i in issues if i.location == "Row 1"]
        self.assertEqual(row1_issues, [])


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


class TestBareMoreTimesFragment(unittest.TestCase):
    # LoopDreams' timesWord() helper (generate-pattern/builders.ts, Aug 23)
    # states every compound stitch's repeat count explicitly, e.g. "rep from
    # * to last shell, 1 more time, sc in centre dc of last shell..." (Shell)
    # or "rep from * to the last st, 5 more times, sc in last st." (Sedge).
    # When the tail immediately after "rep from *" is itself a positional
    # landmark ("to last shell", "to the last st"), the comma-separated "N
    # more time(s)" that follows lands as its OWN clause -- there's no "rep
    # from *" left in it for _RE_REP_FROM to match, so it fell straight
    # through every pattern to "unknown", downgrading otherwise-clean rows to
    # REVIEW (real batch-test finding against production, Aug 23: Square
    # Coaster sedge and shell). Note this is a DIFFERENT shape than "rep from
    # * 2 more times" with no positional landmark in between -- that whole
    # thing already matches _RE_REP_FROM in one piece and was never broken.

    def test_bare_more_times_fragment_recognized_as_repeat_close_not_unknown(self):
        for text, n in (("1 more time", 1), ("2 more times", 2), ("38 more times", 38)):
            clauses = tokenize_round(text)
            self.assertEqual(len(clauses), 1, text)
            self.assertEqual(clauses[0].clause_type, "repeat_close", text)
            self.assertEqual(clauses[0].explicit_count, n, text)

    def test_more_times_fragment_after_positional_landmark_end_to_end(self):
        # The real shape this actually appears in: split across a comma from
        # a "rep from * to last <landmark>" closer. Confirms _zone_sum treats
        # it as the same no-op _RE_REP_FROM's own closer already is (see
        # checks/stitch_count.py), not as an unrecognized-clause warning.
        clauses = tokenize_round("rep from * to last shell, 1 more time")
        types = [c.clause_type for c in clauses]
        self.assertEqual(types, ["repeat_close", "repeat_close"])
        self.assertNotIn("unknown", types)


class TestSedgeStitchClauses(unittest.TestCase):
    # Real construction (Sedge Stitch, loopdreams commit "Fix Sedge Stitch
    # construction", Aug 2026 -- a real tester's hands-on attempt caught the
    # old construction as wrong against a real published tutorial): every
    # row opens with a 2-st (hdc, dc) cluster sharing ONE chain/stitch,
    # repeats "skip 2, (sc, hdc, dc) in next" 3-st clusters, and closes with
    # a single sc in the last chain/stitch. None of these clause shapes had
    # ever been taught to this tool before -- same category as bl sc/fl sc/
    # hhdc/wc st in abbreviations.py, caught missing on a real sample.

    def test_simple_positional_accepts_spelled_out_chain(self):
        # _NOUN previously only matched the abbreviated "ch"/"chs", not the
        # spelled-out word LoopDreams' generator actually uses in prose
        # (generate-pattern's builders.ts skipChainsClause() convention,
        # used across every compound-stitch builder) -- "Hdc in the next
        # chain" fell through as an unrecognized clause.
        clauses = tokenize_round("Hdc in the next chain")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "positional_single")
        self.assertEqual(c.stitch, "hdc")
        self.assertEqual(c.consumes, 1)
        self.assertEqual(c.produces, 1)

    def test_simple_positional_last_chain(self):
        clauses = tokenize_round("sc in last chain")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "positional_single")
        self.assertEqual(c.consumes, 1)
        self.assertEqual(c.produces, 1)

    def test_heterogeneous_paren_cluster_chain_wording(self):
        # "(sc, hdc, dc) in next chain" -- a parenthesized list of THREE
        # DIFFERENT stitch abbreviations all worked into one spot. Already
        # matched by _RE_PAREN_CLUSTER's existing shape once _NOUN accepts
        # "chain" -- no new clause-matching code needed for this shape
        # itself, only the noun widening. The trailing "(sedge made)"
        # descriptive annotation is stripped by tokenize_round's existing
        # fallback before this matches, same as "(shell made)" elsewhere.
        clauses = tokenize_round("(sc, hdc, dc) in next chain (sedge made)")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "cluster_same_spot")
        self.assertEqual(c.stitch, "(sc, hdc, dc)")
        self.assertEqual(c.consumes, 1)
        self.assertEqual(c.produces, 3)
        self.assertIsNone(c.unverifiable_reason)

    def test_heterogeneous_paren_cluster_st_wording(self):
        # Same shape, later-row "st" wording -- already worked before this
        # fix (_NOUN always included "st"), kept here as a same-shape
        # sibling of the chain-wording test above, and as coverage for the
        # exact clause text every row after the first actually uses.
        clauses = tokenize_round("(sc, hdc, dc) in next st (sedge made)")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "cluster_same_spot")
        self.assertEqual(c.consumes, 1)
        self.assertEqual(c.produces, 3)

    def test_same_spot_after_real_stitch_pickup_not_doubled(self):
        # "Hdc in the next chain, dc in the same chain" -- TWO DIFFERENT
        # stitches sharing the ONE slot the first clause already claimed,
        # not the turning-chain-increase idiom same_st was originally
        # verified against (see TestCoasterSameStClause in
        # test_shawl_coaster_dishcloth.py). The second clause must add NO
        # further consumption and produce only its own plain stitch.
        clauses = tokenize_round("Hdc in the next chain, dc in the same chain")
        self.assertEqual(len(clauses), 2)
        opener, same = clauses
        self.assertEqual(opener.consumes, 1)
        self.assertEqual(opener.produces, 1)
        self.assertEqual(same.clause_type, "positional_single")
        self.assertEqual(same.consumes, 0)
        self.assertEqual(same.produces, 1)

    def test_same_spot_after_real_stitch_pickup_st_wording(self):
        # Same disambiguation, later-row "st" wording -- "dc in same st"
        # must NOT keep its turning-chain-increase doubling here, since it
        # follows a real single-stitch pickup ("Hdc in first st"), not a
        # bare/counted turning chain.
        clauses = tokenize_round("Hdc in first st, dc in same st")
        self.assertEqual(len(clauses), 2)
        opener, same = clauses
        self.assertEqual(opener.consumes, 1)
        self.assertEqual(opener.produces, 1)
        self.assertEqual(same.consumes, 0)
        self.assertEqual(same.produces, 1)

    def test_same_st_after_counted_chain_still_doubles(self):
        # Regression guard: the ORIGINAL coaster idiom ("Ch 3 (counts as
        # first dc), dc in same st" -- a turning-chain increase) must keep
        # its existing, hand-verified doubled produces. The preceding
        # clause here is "counted_chain", not "positional_single", so the
        # new same-spot reinterpretation must not fire.
        clauses = tokenize_round("Ch 3 (counts as first dc), dc in same st")
        self.assertEqual(len(clauses), 2)
        same = clauses[1]
        self.assertEqual(same.clause_type, "positional_single")
        self.assertEqual(same.consumes, 1)
        self.assertEqual(same.produces, 2)

    def test_same_st_in_isolation_still_doubles(self):
        # Regression guard, same real sample as test_shawl_coaster_
        # dishcloth.py's TestCoasterSameStClause: with no preceding clause
        # at all (index 0), the original doubled default must be preserved.
        clauses = tokenize_round("dc in same st")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].consumes, 1)
        self.assertEqual(clauses[0].produces, 2)

    def test_skip_first_chain_consumes_when_unpaired(self):
        # "Skip the first 1 chain from the hook (...)" is followed here by
        # "Hdc in the next chain" -- NOT the "<stitch> in the next chain
        # and in each ch across" shape it normally pairs with (see
        # patterns.skip_first_chains_from_hook's own comment) -- so no
        # merge into a single foundation_into_chain clause happens, and
        # this clause stays standalone. Left at consumes=0 only when PAIRED
        # (see TestSkipFirstChainsFoundationClause -- the dedicated
        # foundation check never reads it there); unpaired, it must
        # contribute its real skipped-chain count so the row's generic
        # zone-sum math doesn't silently under-count the foundation chain.
        clauses = tokenize_round(
            "Skip the first 1 chain from the hook (it doesn't count as a stitch). "
            "Hdc in the next chain, dc in the same chain"
        )
        skip_clause = clauses[0]
        self.assertEqual(skip_clause.clause_type, "skip_first_chains_from_hook")
        self.assertEqual(skip_clause.consumes, 1)
        self.assertEqual(skip_clause.produces, 0)

    def test_sedge_foundation_row_verifies_end_to_end(self):
        # Confirms the fix doesn't just tokenize correctly in isolation --
        # the full stitch-count check resolves Sedge Stitch's corrected
        # Row 1 cleanly: skip 1 (consumes 1) + 2-st opener (consumes 1,
        # produces 2) + 6x[skip 2 (consumes 2) + 3-st cluster (consumes 1,
        # produces 3)] + 1-st closer (consumes 1, produces 1) = 21 chains
        # consumed, 21 sts produced -- exactly matching a 21-chain
        # foundation and a declared count of 21, with zero unrecognized
        # clauses. Real sample verified via loopdreams_qa/from_pattern_json
        # against generate-pattern's actual dry_run output shape.
        raw = (
            "Test Sedge Swatch\n"
            "MATERIALS\n"
            "Gauge: 16 sc x 16 rows = 4 in [10 cm]\n"
            "Terminology: US\n"
            "Yarn: Test yarn\n"
            "Hook: 5.0 mm\n"
            "ABBREVIATIONS\n"
            "ch = chain, sc = single crochet, hdc = half double crochet, dc = double crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 21, turn.\n"
            "Row 1: Skip the first 1 chain from the hook (it doesn't count as a stitch). "
            "Hdc in the next chain, dc in the same chain. *skip 2 chains, (sc, hdc, dc) in next chain "
            "(sedge made); rep from * to the last chain, 5 more times, sc in last chain. Ch 1, turn. (21 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        issues = stitch_count.check(pattern)
        row1_issues = [i for i in issues if i.location == "Row 1"]
        self.assertEqual(row1_issues, [])

    def test_sedge_second_row_now_verifies_cleanly_opener_gap_fixed(self):
        # This test used to document a genuine, then-unresolved 1-stitch
        # construction gap: every row after the first used "Hdc in first
        # st, dc in SAME st" (consumes 1 real previous-row stitch, produces
        # 2), with no equivalent to Row 1's offsetting leading "skip the
        # first 1 chain" clause, so it structurally produced one more
        # stitch than it consumed. Fixed upstream (loopdreams repo, "Fix
        # Sedge Stitch row 2+ opener: two stitches, not one shared spot",
        # Aug 23) -- the opener now reads "dc in NEXT st" (2 real previous-
        # row stitches consumed, 2 produced), which balances on its own
        # without needing Row 1's foundation-chain skip to compensate: 2
        # (opener) + 6x3 (clusters) + 1 (closer) = 21, matching both the
        # previous row's count and this row's own declared total. Row 2
        # also now states its repeat count explicitly ("5 more times",
        # LoopDreams' timesWord() helper) -- confirms that phrasing doesn't
        # regress this row back to unverifiable (see TestBareMoreTimesFragment
        # above; this is the exact real shape that fix targets).
        raw = (
            "Test Sedge Swatch\n"
            "MATERIALS\n"
            "Gauge: 16 sc x 16 rows = 4 in [10 cm]\n"
            "Terminology: US\n"
            "Yarn: Test yarn\n"
            "Hook: 5.0 mm\n"
            "ABBREVIATIONS\n"
            "ch = chain, sc = single crochet, hdc = half double crochet, dc = double crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 21, turn.\n"
            "Row 1: Skip the first 1 chain from the hook (it doesn't count as a stitch). "
            "Hdc in the next chain, dc in the same chain. *skip 2 chains, (sc, hdc, dc) in next chain "
            "(sedge made); rep from * to the last chain, 5 more times, sc in last chain. Ch 1, turn. (21 sts)\n"
            "Row 2: Hdc in first st, dc in next st. *skip 2 sts, (sc, hdc, dc) in next st (sedge made); "
            "rep from * to the last st, 5 more times, sc in last st. Ch 1, turn. (21 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        issues = stitch_count.check(pattern)
        row2_issues = [i for i in issues if i.location == "Row 2"]
        self.assertEqual(row2_issues, [])

    def test_shell_centre_dc_still_unverifiable_not_swept_into_paren_cluster(self):
        # Scoping guard for the _NOUN widening and the same-spot
        # reinterpretation above: Shell Stitch's "sc in the centre dc of
        # next shell" (real text, loopdreams builders.ts
        # buildShellStitchRows) must keep coming back unverifiable
        # (REVIEW-tier), not newly PASS or FAIL. It names a position INSIDE
        # a multi-stitch group by a landmark word ("centre dc"), not a
        # parenthesized list of stitches or a plain "next/last st" --
        # patterns.centre_dc is a wholly separate regex from both
        # _RE_PAREN_CLUSTER and simple_positional, so it must be unaffected
        # by widening _NOUN to accept "chain" for those.
        clauses = tokenize_round("sc in the centre dc of next shell")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "positional_single")
        self.assertIsNone(c.consumes)
        self.assertIsNotNone(c.unverifiable_reason)

    def test_shell_half_shell_opener_turning_chain_credit_recognized(self):
        # Real text, loopdreams builders.ts buildHalfShellRowText, PR #436
        # (Aug 29 2026): "2 dc in first sc (turning ch-3 counts as first
        # dc; half shell made)" -- the generator moved the half-shell row's
        # standard "ch-3 counts as first dc" turning-chain credit from a
        # separate leading counted_chain clause (the shape counts_as_chain
        # already handles) into a TRAILING parenthetical on the row's
        # opening stitch clause instead, because a separate leading clause
        # here breaks TURNING_CHAIN_ERROR's row-opener recognition
        # (validate-pattern/rules.ts expects a row to open directly on a
        # stitch count/abbreviation). _strip_trailing_annotation refuses to
        # strip this parenthetical (it contains "counts as", real math, by
        # design), so the clause fell all the way through to "unknown"
        # until this shape was taught directly. Same consumes as
        # cluster_same_spot's plain "2 dc in first sc" (one previous-row
        # anchor); produces is the 2 explicit dc plus 1 bonus stitch
        # credited from the turning chain -- 3, not 2.
        clauses = tokenize_round("2 dc in first sc (turning ch-3 counts as first dc; half shell made)")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "cluster_same_spot")
        self.assertEqual(c.stitch, "dc")
        self.assertEqual(c.consumes, 1)
        self.assertEqual(c.produces, 3)
        self.assertIsNone(c.unverifiable_reason)

    def test_shell_half_shell_opener_turning_chain_credit_last_anchor(self):
        # Same shape, "last" instead of "first" -- real closing-edge anchor
        # word elsewhere in this codebase's _POS grammar (not actually
        # emitted by buildHalfShellRowText today, which only ever opens a
        # row this way, but the underlying anchor noun/position grammar is
        # shared with every other positional clause shape in this module,
        # so it must not be accidentally scoped to "first" alone).
        clauses = tokenize_round("2 dc in last sc (turning ch-3 counts as first dc; half shell made)")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "cluster_same_spot")
        self.assertEqual(c.consumes, 1)
        self.assertEqual(c.produces, 3)
        self.assertIsNone(c.unverifiable_reason)

    def test_shell_row_still_reports_review_not_pass_or_fail(self):
        # End-to-end guard, real CURRENT text (loopdreams builders.ts
        # buildHalfShellRowText, refreshed Aug 29 2026 -- see PR history
        # below): the half-shell/centre-dc row must still come back as an
        # unverifiable warning (REVIEW), exactly as before this whole fix --
        # not a new false PASS (which would mean the centre-dc clause got
        # silently swallowed by some other pattern) and not a new false
        # FAIL either. Also confirms the turning-chain-credit fix doesn't
        # turn this into TWO issues (the real centre-dc one plus a spurious
        # unrecognized-clause one) -- exactly one, same as always.
        #
        # Refreshed from the Aug 23 version of this test for PR #436 (Aug 29
        # 2026), which changed the row's OPENING edge only: "3 dc in first
        # sc (half shell made)" (that version's fix for a real tester-found
        # 2dc/4dc edge asymmetry) is now "2 dc in first sc (turning ch-3
        # counts as first dc; half shell made)" -- fixing a DIFFERENT real
        # bug (TURNING_CHAIN_ERROR) the 3dc wording introduced: restating
        # the previous row's own physical turning chain as 3 MORE dc reads
        # as 4 total legs at that edge against the closing edge's real,
        # chain-less 3 -- the same width mismatch the Aug 23 fix chased, just
        # moved to the opposite edge. Explicitly crediting the chain (2
        # explicit dc + 1 borrowed from the chain = 3, matching the closing
        # edge's 3) fixes the width without re-losing TURNING_CHAIN_ERROR
        # recognition, which is why the credit is a trailing parenthetical
        # on the opening stitch clause rather than a separate leading
        # counted_chain clause. The closing edge ("3 dc in last sc (half
        # shell made)") and the repeat structure are unchanged from Aug 23.
        raw = (
            "Test Shell Swatch\n"
            "MATERIALS\n"
            "Gauge: 16 sc x 16 rows = 4 in [10 cm]\n"
            "Terminology: US\n"
            "Yarn: Test yarn\n"
            "Hook: 5.0 mm\n"
            "ABBREVIATIONS\n"
            "ch = chain, sc = single crochet, dc = double crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 20, turn.\n"
            "Row 1: Skip the first 1 chain from the hook (it doesn't count as a stitch). "
            "Sc in the next chain and in each ch across. Ch 1, turn. (19 sts)\n"
            "Row 2: Sc in first st, *skip 2 sts, 5 dc in next st (shell made), skip 2 sts, "
            "sc in next st; rep from * 2 more times. Ch 3, turn. (19 sts)\n"
            "Row 3: 2 dc in first sc (turning ch-3 counts as first dc; half shell made), "
            "*sc in centre dc of next shell, "
            "5 dc in next sc; rep from * to last shell, 1 more time, sc in centre dc of last shell, "
            "3 dc in last sc (half shell made). Fasten off, weave in ends. (19 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        issues = stitch_count.check(pattern)
        row3_issues = [i for i in issues if i.location == "Row 3"]
        self.assertEqual(len(row3_issues), 1)
        self.assertEqual(row3_issues[0].severity, "warning")
        self.assertIn("centre dc", row3_issues[0].message)


if __name__ == "__main__":
    unittest.main()


class TestTurningChainCountsAsStitch(unittest.TestCase):
    """loopdreams switched every turning chain of 2 or more (hdc/hhdc/dc/tr) to
    the counts-as-a-stitch convention: the chain IS the row's first stitch, the
    stitch at its base is skipped, and the row's last stitch goes into the top
    of the previous row's chain. The foundation is written one chain shorter to
    match, because the chain is now one of the stitches rather than an extra.

    Every assertion here is one stitch away from its opposite, which is the
    whole difficulty: get any of it wrong and a pattern silently gains or loses
    a stitch on every row.
    """

    def test_counting_skip_chains_clause_adds_the_chain_as_a_stitch(self):
        # "Skip the first 2 chains ... (they count as this row's first stitch)"
        # against the older "(they don't count as a stitch)" -- one chain of a
        # difference in the row's total, so the two are told apart rather than
        # matched by one loose regex.
        clauses = tokenize_round(
            "Skip the first 2 chains from the hook (they count as this row's first stitch). "
            "Hhdc in the next chain and in each ch across. Ch 2, turn."
        )
        folded = [c for c in clauses if c.clause_type == "foundation_into_chain"]
        self.assertEqual(len(folded), 1)
        self.assertTrue(folded[0].chain_counts_as_stitch)

    def test_non_counting_skip_chains_clause_is_unchanged(self):
        clauses = tokenize_round(
            "Skip the first 1 chain from the hook (it doesn't count as a stitch). "
            "Sc in the next chain and in each ch across. Ch 1, turn."
        )
        folded = [c for c in clauses if c.clause_type == "foundation_into_chain"]
        self.assertEqual(len(folded), 1)
        self.assertFalse(folded[0].chain_counts_as_stitch)

    def test_foundation_row_is_one_wider_than_the_chains_it_works_into(self):
        # Ch 33 skipping 2 leaves 31 chains to work into, and the skipped pair
        # is the 32nd stitch. The older convention would make this 31.
        text = (
            "Pattern\nMATERIALS\nGauge: 13 sts x 11 rows = 4 in\nTerminology: US\n"
            "PATTERN STEPS\nFoundation: Ch 33.\n"
            "Row 1: Skip the first 2 chains from the hook (they count as this row's first "
            "stitch). Hhdc in the next chain and in each ch across. Ch 2, turn. (32 sts)\n"
        )
        errors = [i for i in stitch_count.check(parse(text)) if i.severity == "error"]
        self.assertEqual(errors, [], f"unexpected: {[i.message for i in errors]}")

    def test_multiple_worked_into_the_turning_chain(self):
        # "2 dc in top of ch" -- a shaped row's far-edge increase. One chain-top
        # consumed, two stitches produced.
        (clause,) = [c for c in tokenize_round("2 dc in top of ch") if c.stitch == "dc"]
        self.assertEqual(clause.consumes, 1)
        self.assertEqual(clause.produces, 2)

    def test_shaped_row_still_gets_the_turning_chain_credit(self):
        # A shaped row WORKS its first stitch (that is the near-edge increase)
        # instead of skipping it, so the "skip first st" opener that normally
        # carries the credit is absent. The chain is still standing in for the
        # row's first stitch, detected here by the far edge instead.
        clauses = tokenize_round("Dc in first st, dc in each of next 9 sts, 2 dc in top of ch. Ch 3, turn.")
        credits = [c for c in clauses if c.clause_type == "counted_chain"]
        self.assertEqual(len(credits), 1, "shaped row lost its turning-chain credit")
        self.assertEqual(sum(c.produces for c in clauses if c.produces), 1 + 1 + 9 + 2)

    def test_the_chain_is_never_credited_twice(self):
        # A waffle row has BOTH tells -- it opens with "skip first st" AND
        # closes into the chain -- and must still be credited exactly once.
        clauses = tokenize_round(
            "Skip first st, *fpdc around next st, dc in next 2 sts; rep from * to last 2 sts, "
            "6 more times, fpdc around next st, dc in top of ch. Ch 2, turn."
        )
        self.assertEqual([c.clause_type for c in clauses if c.clause_type == "counted_chain"], [],
                         "credited a synthetic chain on top of the skip-opener credit")
        self.assertEqual(clauses[0].produces, 1)

    def test_explicit_leading_chain_is_never_credited_twice_either(self):
        # The older phrasing states the chain outright; that counted_chain
        # already carries the credit, so no synthetic one is added.
        clauses = tokenize_round(
            "Ch 3 (counts as dc), dc in each of next 9 sts, 2 dc in top of ch. Ch 3, turn."
        )
        self.assertEqual(len([c for c in clauses if c.clause_type == "counted_chain"]), 1)


class TestMotifRoundsWorkedIntoSpaces(unittest.TestCase):
    """LoopDreams' Granny Square / Granny Square Blanket, Sep 2026 batch --
    the first motif constructions ever put through this tool. See
    ARCHITECTURE.md, "Rounds worked into spaces"."""

    def test_space_is_a_stitch_target(self):
        # "sp"/"space" was missing from _NOUN entirely, so every clause of
        # every round of both templates failed to match any shape at all.
        for text, produces in [("3 dc in next sp", 3), ("Dc in next sp", 1)]:
            clauses = tokenize_round(text)
            self.assertEqual(len(clauses), 1, text)
            self.assertEqual(clauses[0].produces, produces, text)
            self.assertEqual(clauses[0].consumes, 1, text)

    def test_a_space_can_be_qualified_by_its_corner_or_chain(self):
        # A space is routinely named by which corner or which chain made it,
        # unlike a plain stitch, which never is.
        for text in ("3 hdc in next corner sp", "Dc in next ch-2 corner sp", "Sc in next ch-1 sp"):
            clauses = tokenize_round(text)
            self.assertEqual(len(clauses), 1, text)
            self.assertNotEqual(clauses[0].clause_type, "unknown", text)

    def test_group_worked_into_one_shared_spot(self):
        # The four-corner increase every square motif is built from. The
        # ch 2 makes the corner space and produces nothing; the six dc do.
        clauses = tokenize_round("[3 dc, ch 2, 3 dc] in next corner sp")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "cluster_same_spot")
        self.assertEqual(clauses[0].produces, 6)
        self.assertEqual(clauses[0].consumes, 1)
        # Not an abbreviation -- completeness.py reads `stitch` as one, and
        # reported "[3 dc, ch 2, 3 dc]" as an undefined abbreviation when
        # this clause set it.
        self.assertIsNone(clauses[0].stitch)

    def test_group_into_the_same_spot_claims_no_new_slot(self):
        clauses = tokenize_round("[1 dc, ch 2, 2 dc] in the same sp (corner made)")
        self.assertEqual(clauses[0].produces, 3)
        self.assertEqual(clauses[0].consumes, 0)

    def test_an_unknown_member_makes_the_whole_group_unverifiable(self):
        # Never an undercount: a Cluster with no stated construction has no
        # ratio, so the group cannot be scored at all.
        clauses = tokenize_round("[Cluster, ch 1, Cluster] in next ch-1 sp")
        self.assertIsNone(clauses[0].produces)
        self.assertIsNotNone(clauses[0].unverifiable_reason)

    def test_the_letters_only_paren_shape_still_wins(self):
        # _RE_PAREN_CLUSTER is the narrower shape and names its members in
        # `stitch`, which callers rely on -- the general group shape must not
        # shadow it (it did, and broke the sedge fixture).
        clauses = tokenize_round("(sc, hdc, dc) in next chain (sedge made)")
        self.assertEqual(clauses[0].stitch, "(sc, hdc, dc)")

    def test_travel_slip_stitch_is_a_no_op(self):
        for text in ("Sl st to corner sp", "Sl st in next ch-2 corner sp", "Sl st in next ch-1 sp"):
            clauses = tokenize_round(text)
            self.assertEqual(clauses[0].consumes, 0, text)
            self.assertEqual(clauses[0].produces, 0, text)

    def test_colour_specific_fasten_off_is_not_a_finishing_fasten_off(self):
        # completeness.py reads a fasten_off clause on the last body row as
        # proof the piece tells the maker how to finish; a mid-pattern colour
        # break is not that.
        clauses = tokenize_round("Fasten off Colour 1")
        self.assertEqual(clauses[0].clause_type, "note")
        self.assertNotEqual(clauses[0].clause_type, "fasten_off")

    def test_multi_part_count_restatement_is_a_no_op(self):
        for text in ("(24 dc, 4 ch-2 corner sps, 4 ch-1 sps)", "(16 Clusters, 16 ch-1 sps)", "(12 dc)"):
            clauses = tokenize_round(text)
            self.assertEqual(clauses[0].clause_type, "note", text)

    def test_a_round_can_name_the_stitch_it_works_back_over(self):
        # "in each remaining sc around" -- the target noun was a hardcoded
        # literal "st".
        clauses = tokenize_round("2 dc in each remaining sc around")
        self.assertEqual(clauses[0].clause_type, "each_st_around")

    def test_n_stitches_in_the_same_spot_stay_unverifiable(self):
        # Deliberately NOT scored consumes=0: doing that made both of the
        # square's corner rounds parse fully and then fail with confident
        # stitch-count mismatches against counts that are correct. See
        # ARCHITECTURE.md, "Where this deliberately stops short".
        clauses = tokenize_round("2 dc in the same sp")
        self.assertEqual(clauses[0].produces, 2)
        self.assertIsNone(clauses[0].consumes)
        self.assertIsNotNone(clauses[0].unverifiable_reason)

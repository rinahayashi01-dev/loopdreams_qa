import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count, completeness
from loopdreams_qa.stitch_parser import tokenize_round

MATERIALS_BLOCK = """MATERIALS
Gauge: 16 sc x 8 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 5.0 mm
"""


def _pattern(pattern_steps: str, abbr_line: str = "ch = chain, sc = single crochet, hdc = half double crochet, "
             "dc = double crochet, sl st = slip stitch, rep = repeat"):
    raw = (
        "Test Pattern\n"
        + MATERIALS_BLOCK
        + "ABBREVIATIONS\n"
        + abbr_line + "\n"
        "PATTERN STEPS\n"
        + pattern_steps
    )
    return parse(raw)


class TestLiteralNextMultiplier(unittest.TestCase):
    # Real sample (dishcloth, Jul 8 batch): "45 DC in next 45 sts" -- a
    # redundant restatement of the same number (N == M), which is 1 dc per
    # stitch, same as the bare "dc in next 45 sts" form. Previously
    # unconditionally treated ANY leading count as a multiplier ("N per
    # EACH of M sts"), which would have wrongly produced 45x the stitches.
    def test_bare_form_is_one_per_stitch(self):
        clauses = tokenize_round("dc in next 3 sts")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].consumes, 3)
        self.assertEqual(clauses[0].produces, 3)
        self.assertIsNone(clauses[0].unverifiable_reason)

    def test_matching_leading_count_is_redundant_restatement(self):
        clauses = tokenize_round("3 dc in next 3 sts")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].consumes, 3)
        self.assertEqual(clauses[0].produces, 3)
        self.assertIsNone(clauses[0].unverifiable_reason)

    def test_mismatched_leading_count_left_unverifiable_not_guessed(self):
        # No real sample has ever exercised "N dc in next M sts" with
        # N != M -- must not silently guess a multiplier interpretation.
        clauses = tokenize_round("2 dc in next 3 sts")
        self.assertEqual(len(clauses), 1)
        self.assertIsNone(clauses[0].produces)
        self.assertIsNotNone(clauses[0].unverifiable_reason)
        self.assertIn("no confirmed real-sample precedent", clauses[0].unverifiable_reason)


class TestCoasterSameStClause(unittest.TestCase):
    # Real sample (coaster, Jul 8 batch): "dc in same st" as the second half
    # of a round-opening increase ("Ch 3, dc in same st, ..."). consumes=1,
    # produces=2*ratio -- hand-verified against the real file's rounds 1-2
    # (12->24, 24->36), since the preceding "Ch 3" is bare/uncounted here.
    def test_same_st_consumes_one_produces_double(self):
        clauses = tokenize_round("dc in same st")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].consumes, 1)
        self.assertEqual(clauses[0].produces, 2)

    def test_same_st_row_verifies_against_declared_count(self):
        pattern = _pattern(
            "Foundation chain:Magic ring. Ch 3 (counts as first dc), 11 dc in ring, sl st to top of ch 3 to "
            "join. (12 dc)\n"
            "Row 1: Ch 3, dc in same st, 2 dc in each remaining st around, sl st to top of ch 3 to join. "
            "(24 dc) (24 sts)\n"
        )
        issues = stitch_count.check(pattern)
        row1_issues = [i for i in issues if i.location == "Row 1"]
        self.assertEqual(row1_issues, [])


class TestCoasterJoinClause(unittest.TestCase):
    def test_sl_st_to_top_of_ch_join_is_noop(self):
        clauses = tokenize_round("sl st to top of ch 3 to join")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "join")

    def test_sl_st_to_first_st_join_is_noop(self):
        # sc-variant coaster (same batch): no counted turning chain to join
        # back to, so rounds close with "sl st to first sc to join" instead.
        clauses = tokenize_round("sl st to first sc to join")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "join")

    def test_sl_st_to_first_two_word_abbreviation_join_is_noop(self):
        # wc st (Waistcoat Stitch) variant, real sample: loopdreams' "Batch-
        # test regression matrix" CI job, run 33269385156, Aug 2026 -- the
        # first run after loopdreams_qa's deep cross-check was actually
        # wired into that job (see loopdreams PR #437/#438). Same shape as
        # the single-word sc case above, but the anchor stitch itself is
        # two words -- confirms the fix doesn't just special-case "wc st"
        # but genuinely spans multi-word abbreviations.
        clauses = tokenize_round("sl st to first wc st to join")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "join")


class TestCoasterTrailingCountRestatement(unittest.TestCase):
    # A round's declared count restated as its own bare parenthetical, real
    # sample (same CI run as above): loopdreams' buildCoasterRows emits
    # "...sl st to first wc st to join. (8 wc st)" for a wc st coaster's
    # round 1 -- tokenize_round's top-level split then sees "(8 wc st)" as
    # its own clause. For single-word abbreviations (dc/sc/...) this
    # restatement never reaches tokenize_round at all -- pattern_parser.py's
    # row_re strips it as noise first -- but "wc st" isn't in that stripping
    # regex's hardcoded single-word list, so it sails through unstripped and
    # needs its own no-op recognizer here (see _Patterns.trailing_count_
    # restatement's own comment).
    def test_bare_count_in_stitch_word_is_noop(self):
        clauses = tokenize_round("(8 wc st)")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "note")

    def test_bare_count_in_single_word_stitch_is_noop(self):
        clauses = tokenize_round("(24 dc)")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "note")

    def test_wc_st_coaster_round_verifies_against_declared_count(self):
        # Mirrors the real text from_pattern_json.py's _with_trailing_count
        # actually produces for a wc st coaster row 1 (the trailing "(8 wc
        # st)" doesn't match _TRAILING_COUNT_RE's "sts?" requirement, so a
        # second, correctly-shaped "(8 sts)" gets appended alongside it).
        pattern = _pattern(
            "Row 1: Magic ring. 8 wc st in ring, sl st to first wc st to join. (8 wc st). (8 sts)\n",
            abbr_line="ch = chain, wc st = waistcoat stitch, sl st = slip stitch, rep = repeat",
        )
        issues = stitch_count.check(pattern)
        row1_issues = [i for i in issues if i.location == "Row 1"]
        self.assertEqual(row1_issues, [])


class TestCoasterEachStAroundMultiplier(unittest.TestCase):
    # Real sample (coaster, Jul 8 batch): "2 dc in each remaining st
    # around" -- each_st_around previously had no leading-multiplier slot
    # at all.
    def test_multiplier_applied_to_produces(self):
        clauses = tokenize_round("2 dc in each remaining st around")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].consumes, 1)
        self.assertEqual(clauses[0].produces, 2)

    def test_no_multiplier_still_one_per_stitch(self):
        clauses = tokenize_round("dc in each remaining st around")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].consumes, 1)
        self.assertEqual(clauses[0].produces, 1)


class TestCoasterMagicRingWithTurningChain(unittest.TestCase):
    def test_counted_turning_chain_counts_as_one_stitch(self):
        pattern = _pattern(
            "Foundation chain:Magic ring. Ch 3 (counts as first dc), 11 dc in ring, sl st to top of ch 3 to "
            "join. (12 dc)\n"
            "Row 1: Ch 3, dc in same st, dc in each remaining st around, sl st to top of ch 3 to join. (24 dc) "
            "(24 sts)\n"
        )
        self.assertEqual(pattern.foundation_chain, 12)
        self.assertTrue(pattern.foundation_is_magic_ring)


class TestDishclothColourPrefixedFoundation(unittest.TestCase):
    # Real sample (dishcloth, Jul 8 batch): a leading colour clause before
    # "Ch N" in the foundation line -- previously only bare "Ch N" matched.
    def test_foundation_with_leading_colour_clause(self):
        pattern = _pattern(
            "Foundation chain:With Colour 1 — Honey, Ch 48, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (47 sts)\n"
        )
        self.assertEqual(pattern.foundation_chain, 48)


class TestDishclothNumberedCommaColourJoin(unittest.TestCase):
    # Real sample (dishcloth, Jul 8 batch): "With Colour 2 — Moss, 45 DC in
    # next 45 sts." -- a numbered (not lettered) colour identifier with a
    # comma separator (not colon) before the row body.
    def test_row_with_numbered_comma_colour_prefix_parses(self):
        pattern = _pattern(
            "Foundation chain:Ch 46, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (45 sts)\n"
            "Row 2: With Colour 2 — Moss, 45 DC in next 45 sts. Ch 1, turn. (45 sts)\n"
        )
        row2 = next(r for r in pattern.rows if r.row_start == 2)
        stitch_clauses = [c for c in row2.clauses if c.clause_type == "literal_count"]
        self.assertEqual(len(stitch_clauses), 1)
        self.assertEqual(stitch_clauses[0].consumes, 45)
        self.assertEqual(stitch_clauses[0].produces, 45)


class TestBareColourIdentifierNoName(unittest.TestCase):
    # Real sample (LoopDreams generator, colourwork rows): the generator's
    # stored pattern text states the colour identifier alone, with no
    # "-- Name" suffix at all ("With Colour 1, Ch 33, turn.") -- the name is
    # a frontend-only display enrichment (hex -> colour name), never part of
    # the actual pattern text this tool receives. Previously every one of
    # these was left as an "unrecognized clause" since the name half of the
    # colour clause was mandatory whenever the clause matched at all.
    def test_foundation_with_bare_colour_identifier(self):
        pattern = _pattern(
            "Foundation chain:With Colour 1, Ch 33, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (32 sts)\n"
        )
        self.assertEqual(pattern.foundation_chain, 33)

    def test_row_with_bare_colour_identifier_parses(self):
        pattern = _pattern(
            "Foundation chain:Ch 33, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (32 sts)\n"
            "Row 2: With Colour 2, 32 sc in next 32 sts. Ch 1, turn. (32 sts)\n"
        )
        row2 = next(r for r in pattern.rows if r.row_start == 2)
        self.assertIsNone(row2.color)
        self.assertEqual([c for c in row2.clauses if c.clause_type == "unknown"], [])
        stitch_clauses = [c for c in row2.clauses if c.clause_type == "literal_count"]
        self.assertEqual(len(stitch_clauses), 1)
        self.assertEqual(stitch_clauses[0].consumes, 32)
        self.assertEqual(stitch_clauses[0].produces, 32)

    def test_repeat_reference_with_bare_colour_identifier_parses(self):
        pattern = _pattern(
            "Foundation chain:Ch 33, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (32 sts)\n"
            "Row 2: With Colour 2, 32 sc in next 32 sts. Ch 1, turn. (32 sts)\n"
            "Row 3: With Colour 1, Repeat Row 1.\n"
        )
        row3 = next(r for r in pattern.rows if r.row_start == 3)
        self.assertEqual(row3.referenced_rows, [1])

    def test_inline_colour_change_with_bare_identifier_not_unrecognized(self):
        clauses = tokenize_round("sc in each st around, changing to Colour 2 in the last st")
        self.assertEqual([c for c in clauses if c.clause_type == "unknown"], [])


class TestBareWhiteDesignator(unittest.TestCase):
    # Real sample (LoopDreams generator, picture-grid colourwork Scarf):
    # margin/blank cells that aren't part of the design's own chosen
    # palette are labelled literally "With White," -- no "Colour" word at
    # all -- distinct from both the numbered "With Colour N," form and its
    # bare-identifier variant above (see generate-pattern's colourwork.ts:
    # colourLabel() returns "White" directly for BLANK_COLOUR, never
    # "Colour N"). Every one of these was previously left as an
    # "unrecognized clause" since the colour clause always required the
    # literal word "Colour" to match at all.
    def test_foundation_with_white_designator(self):
        pattern = _pattern(
            "Foundation chain:With White, Ch 33, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (32 sts)\n"
        )
        self.assertEqual(pattern.foundation_chain, 33)

    def test_row_with_white_designator_parses(self):
        pattern = _pattern(
            "Foundation chain:Ch 33, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (32 sts)\n"
            "Row 2: With White, 32 sc in next 32 sts. Ch 1, turn. (32 sts)\n"
        )
        row2 = next(r for r in pattern.rows if r.row_start == 2)
        self.assertEqual([c for c in row2.clauses if c.clause_type == "unknown"], [])
        stitch_clauses = [c for c in row2.clauses if c.clause_type == "literal_count"]
        self.assertEqual(len(stitch_clauses), 1)
        self.assertEqual(stitch_clauses[0].consumes, 32)
        self.assertEqual(stitch_clauses[0].produces, 32)

    def test_repeat_reference_with_white_designator_parses(self):
        pattern = _pattern(
            "Foundation chain:Ch 33, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (32 sts)\n"
            "Row 2: With White, 32 sc in next 32 sts. Ch 1, turn. (32 sts)\n"
            "Row 3: With White, Repeat Row 1.\n"
        )
        row3 = next(r for r in pattern.rows if r.row_start == 3)
        self.assertEqual(row3.referenced_rows, [1])

    def test_inline_white_change_not_unrecognized(self):
        clauses = tokenize_round("sc in each st around, changing to White in the last st")
        self.assertEqual([c for c in clauses if c.clause_type == "unknown"], [])


class TestDuplicateCountAnnotationStripping(unittest.TestCase):
    # Mittens (Jul 7) only needed to strip a single trailing "(N sc)".
    # Shawl (Jul 8) added a same-unit duplicate "(N sts) (N sts)"; coaster
    # (Jul 8) added a different-unit duplicate "(N dc) (N sts)". Both must
    # now be stripped regardless of how many trailing annotations pile up.
    def test_same_unit_duplicate_stripped(self):
        pattern = _pattern(
            "Foundation chain:Ch 4, turn.\n"
            "Row 1: 2 sc in first st, sc in next st, 2 sc in last st, ch 1, turn. (5 sts) (5 sts)\n"
        )
        row1 = next(r for r in pattern.rows if r.row_start == 1)
        self.assertEqual(row1.declared_count, 5)

    def test_different_unit_duplicate_stripped(self):
        pattern = _pattern(
            "Foundation chain:Magic ring. Ch 3 (counts as first dc), 11 dc in ring, sl st to top of ch 3 to "
            "join. (12 dc)\n"
            "Row 1: Ch 3, dc in same st, 2 dc in each remaining st around, sl st to top of ch 3 to join. "
            "(24 dc) (24 sts)\n"
        )
        row1 = next(r for r in pattern.rows if r.row_start == 1)
        self.assertEqual(row1.declared_count, 24)


class TestShawlFoundationChainSkipAmbiguity(unittest.TestCase):
    # Real sample (shawl, Jul 8 batch): Row 1 works directly off the
    # foundation chain via a flat increase sequence ("2 SC in first st, SC
    # in next st, 2 SC in last st") with no ordinal clause explaining why
    # it only consumes 3 of the 4 foundation chains. Must be an honest
    # WARNING (ambiguous convention), not a confident ERROR.
    def test_flat_sequence_foundation_shortfall_is_warning_not_error(self):
        pattern = _pattern(
            "Foundation chain:Ch 4, turn.\n"
            "Row 1: 2 sc in first st, sc in next st, 2 sc in last st, ch 1, turn. (5 sts) (5 sts)\n"
        )
        issues = stitch_count.check(pattern)
        row1_issues = [i for i in issues if i.location == "Row 1"]
        self.assertEqual(len(row1_issues), 1)
        self.assertEqual(row1_issues[0].severity, "warning")
        self.assertIn("Cannot verify", row1_issues[0].message)

        completeness_issues = completeness.check(pattern)
        row1_completeness = [i for i in completeness_issues if i.location == "Row 1"]
        self.assertEqual(len(row1_completeness), 1)
        self.assertEqual(row1_completeness[0].severity, "warning")

    def test_flat_sequence_matching_foundation_count_has_no_ambiguity_warning(self):
        # consumes 3 (== the 3-ch foundation, no shortfall) and produces
        # 2+1+2=5, matching the declared count -- no ambiguity to flag.
        pattern = _pattern(
            "Foundation chain:Ch 3, turn.\n"
            "Row 1: 2 sc in first st, sc in next st, 2 sc in last st, ch 1, turn. (5 sts) (5 sts)\n"
        )
        issues = stitch_count.check(pattern)
        row1_issues = [i for i in issues if i.location == "Row 1"]
        self.assertEqual(row1_issues, [])


class TestShawlBorderFastenOffRecognition(unittest.TestCase):
    # Real sample (shawl, Jul 8 batch): "Border: Fasten off. With RS
    # facing, join yarn at any corner..." -- the border's own leading
    # "Fasten off." wasn't recognized as satisfying the body-needs-a-
    # fasten-off completeness check.
    def test_border_leading_fasten_off_satisfies_check(self):
        raw = (
            "Test Shawl\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation chain:Ch 4, turn.\n"
            "Row 1: 2 sc in first st, sc in next st, 2 sc in last st, ch 1, turn. (5 sts) (5 sts)\n"
            "Finishing\n"
            "Border: Fasten off. With RS facing, join yarn at any corner, sc evenly around. Fasten off. "
            "(20 sts)\n"
        )
        pattern = parse(raw)
        issues = completeness.check(pattern)
        fasten_off_issues = [i for i in issues if "fasten off" in i.message.lower()]
        self.assertEqual(fasten_off_issues, [])


class TestMossSedgeCompoundTokens(unittest.TestCase):
    # Real sample (shawl, Jul 8 batch): "MOSS"/"SEDGE" used directly as
    # literal stitch TOKENS in row text for the first time (every prior
    # sample spelled out the underlying construction instead). Two bugs
    # found and fixed here:
    #   1. stitch_parser.py's _BASE_STITCH_WORDS had its own disconnected
    #      hardcoded compound-word list, so adding to
    #      abbreviations.COMPOUND_STITCH_WORDS alone did nothing.
    #   2. The compound-ratio solver (_sum_known/_zone_sum) didn't weight
    #      occurrences by a clause's own multiplier, producing contradictory
    #      "solved" ratios across rows with different multipliers.
    def test_moss_token_recognized_as_compound_not_unknown_clause(self):
        clauses = tokenize_round("2 moss in first st")
        self.assertEqual(len(clauses), 1)
        self.assertNotEqual(clauses[0].clause_type, "unknown")
        self.assertTrue(clauses[0].is_compound)
        self.assertEqual(clauses[0].stitch, "moss")

    def test_moss_ratio_solves_consistently_across_rows_with_different_multipliers(self):
        # Mirrors the real shawl moss sample's growth shape: each row has
        # a "2 MOSS in first st" and "2 MOSS in last st" (multiplier 2)
        # plus a "MOSS in each of next N sts" (multiplier N) in between.
        # If the solver doesn't weight by multiplier, these rows produce
        # contradictory implied ratios; with the fix, all resolve to 1.
        pattern = _pattern(
            "Foundation chain:Ch 4, turn.\n"
            "Row 1: 2 moss in first st, moss in next st, 2 moss in last st, ch 1, turn. (5 sts) (5 sts)\n"
            "Row 2: 2 moss in first st, moss in each of next 3 sts, 2 moss in last st, ch 1, turn. (7 sts) "
            "(7 sts)\n"
            "Row 3: 2 moss in first st, moss in each of next 5 sts, 2 moss in last st, ch 1, turn. (9 sts) "
            "(9 sts)\n",
            abbr_line="ch = chain, moss = moss stitch, rep = repeat",
        )
        issues = stitch_count.check(pattern)
        error_issues = [i for i in issues if i.severity == "error"]
        self.assertEqual(error_issues, [])

    def test_moss_wrong_declared_count_still_caught_after_solving(self):
        # A wrong declared count on one row breaks the algebraic solve
        # itself (the rows' own numbers no longer agree on a single ratio)
        # -- surfaced as a "contradictory answers" error rather than a
        # per-row mismatch, since there's no longer a single solved ratio
        # to check the row against. Either way, the bad row must not pass
        # silently.
        pattern = _pattern(
            "Foundation chain:Ch 4, turn.\n"
            "Row 1: 2 moss in first st, moss in next st, 2 moss in last st, ch 1, turn. (5 sts) (5 sts)\n"
            "Row 2: 2 moss in first st, moss in each of next 3 sts, 2 moss in last st, ch 1, turn. (7 sts) "
            "(7 sts)\n"
            "Row 3: 2 moss in first st, moss in each of next 5 sts, 2 moss in last st, ch 1, turn. (99 sts) "
            "(99 sts)\n",
            abbr_line="ch = chain, moss = moss stitch, rep = repeat",
        )
        issues = stitch_count.check(pattern)
        error_issues = [i for i in issues if i.severity == "error"]
        self.assertEqual(len(error_issues), 1)
        self.assertIn("contradictory", error_issues[0].message)


if __name__ == "__main__":
    unittest.main()

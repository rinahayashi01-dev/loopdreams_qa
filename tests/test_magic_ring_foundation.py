import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count
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


class TestMagicRingNoOpClauses(unittest.TestCase):
    # Real phrasing (loopdreams generate-pattern/builders.ts, Jul 29 batch):
    # every magic-ring construction (Amigurumi Ball/Cone/Limb, Coaster,
    # Mittens) opens its first round with a bare "Magic ring" clause -- 0
    # stitches exist yet, the real count comes from the following "N
    # <stitch> in ring" clause.
    def test_magic_ring_is_a_noop(self):
        clauses = tokenize_round("Magic ring")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "note")
        self.assertEqual(clauses[0].consumes, 0)
        self.assertEqual(clauses[0].produces, 0)

    # Real phrasing (Amigurumi Ball/Cone/Limb, Mittens, Amigurumi Egg):
    # states the continuous-spiral convention -- no stitch-count effect.
    def test_do_not_join_or_turn_is_a_noop(self):
        clauses = tokenize_round("do not join or turn")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "note")
        self.assertEqual(clauses[0].consumes, 0)
        self.assertEqual(clauses[0].produces, 0)


class TestRingLiteralClause(unittest.TestCase):
    # "N <stitch> in ring" -- the ring itself has no independently-stated
    # count; the N given here directly is both the "consumed" ring size and
    # (via the stitch's own ratio) the produced stitch count.
    def test_sc_in_ring_one_to_one(self):
        clauses = tokenize_round("6 sc in ring")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "literal_count")
        self.assertEqual(c.stitch, "sc")
        self.assertEqual(c.consumes, 6)
        self.assertEqual(c.produces, 6)
        self.assertIsNone(c.unverifiable_reason)

    def test_dc_in_ring(self):
        clauses = tokenize_round("11 dc in ring")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.consumes, 11)
        self.assertEqual(c.produces, 11)


class TestCountsAsFirstChain(unittest.TestCase):
    # Real phrasing found on a real sample (Coaster HDC/DC round 1,
    # loopdreams builders.ts buildCoasterRows, Jul 29 batch): "Ch 3 (counts
    # as first dc)" -- the word "first" between "as" and the stitch word
    # was never accepted; only the "first"-less "Ch 3 (counts as dc)" form
    # (used elsewhere, e.g. motif corner rounds) matched before this fix.
    def test_counts_as_first_stitch_recognized(self):
        clauses = tokenize_round("Ch 3 (counts as first dc)")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "counted_chain")
        self.assertEqual(c.stitch, "dc")
        self.assertEqual(c.produces, 1)

    def test_counts_as_without_first_still_works(self):
        # Backward compat: the older/other real phrasing with no "first".
        clauses = tokenize_round("Ch 3 (counts as dc)")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "counted_chain")

    def test_standalone_counted_chain_not_bumped(self):
        # The consumes=1 bump (see TestMagicRingCountedChainBump below)
        # only applies right after a "Magic ring" clause -- everywhere else
        # this clause sits atop a real previous round and correctly
        # consumes nothing of its own.
        clauses = tokenize_round("Ch 3 (counts as first dc), dc in same st")
        self.assertEqual(clauses[0].clause_type, "counted_chain")
        self.assertEqual(clauses[0].consumes, 0)


class TestMagicRingCountedChainBump(unittest.TestCase):
    # The Coaster HDC/DC joined-round shape: "Magic ring." immediately
    # followed by a counted chain has no real previous round to consume
    # from -- pattern_parser.py's own magic-ring foundation detection folds
    # the counted chain's implicit stitch into the ring's total size
    # (foundation_chain = N + 1), so the counted_chain clause here must
    # claim one of the ring's own slots (consumes=1) for the row's total
    # consumed count to ever reach that N + 1.
    def test_counted_chain_after_magic_ring_consumes_one(self):
        clauses = tokenize_round(
            "Magic ring. Ch 3 (counts as first dc), 11 dc in ring, sl st to top of ch 3 to join"
        )
        counted_chain = next(c for c in clauses if c.clause_type == "counted_chain")
        self.assertEqual(counted_chain.consumes, 1)
        self.assertEqual(counted_chain.produces, 1)


class TestOvalEggFoundationClauses(unittest.TestCase):
    # Real phrasing (Amigurumi Egg / Basic Oval round 1, loopdreams
    # builders.ts buildOvalRoundRows, Jul 29 batch): a two-sided
    # foundation-chain start, worked down one side then back up the other.
    def test_ordinal_and_next_chs(self):
        clauses = tokenize_round("Sc in 2nd ch from hook and each of next 2 chs")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "literal_count")
        self.assertEqual(c.stitch, "sc")
        self.assertEqual(c.consumes, 0)
        self.assertEqual(c.produces, 3)  # 1 (the ordinal st) + 2 (next 2 chs)

    def test_each_of_next_chs(self):
        clauses = tokenize_round("sc in each of next 3 chs")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "literal_count")
        self.assertEqual(c.consumes, 0)
        self.assertEqual(c.produces, 3)

    def test_opposite_side_marker_is_noop(self):
        clauses = tokenize_round("working on the opposite side of the foundation chain")
        self.assertEqual(len(clauses), 1)
        self.assertEqual(clauses[0].clause_type, "note")
        self.assertEqual(clauses[0].consumes, 0)
        self.assertEqual(clauses[0].produces, 0)

    # Current, real generator text (buildOvalRoundRows, confirmed against a
    # loopdreams batch-test run against production, Aug 1 2026): the ordinal
    # "2nd ch from hook" form above is no longer what this builder actually
    # emits -- it now pairs skipChainsClause(1) (see the split-foundation-
    # clause fix's own TestSkipFirstChainsFoundationClause) with "Sc in the
    # next chain and each of next N chs" instead. Neither previously
    # existing shape matched this, so it fell through to "unrecognized
    # clause" and broke Row 1's stitch-count verification entirely.
    def test_next_chain_and_next_chs(self):
        clauses = tokenize_round("Sc in the next chain and each of next 2 chs")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "literal_count")
        self.assertEqual(c.stitch, "sc")
        self.assertEqual(c.consumes, 0)
        self.assertEqual(c.produces, 3)  # 1 (the "next chain" itself) + 2 (next 2 chs)

    def test_full_egg_row_1_with_skip_clause_verifies_end_to_end(self):
        raw = (
            "Row 1: Ch 5. Skip the first 1 chain from the hook (it doesn't count as a stitch). "
            "Sc in the next chain and each of next 2 chs, 3 sc in last ch, "
            "working on the opposite side of the foundation chain: sc in each of next 3 chs, 3 sc in next ch. "
            "Place a stitch marker in the first st — work in a continuous spiral from here on, "
            "do not join or turn. (12 sts)\n"
            "Row 2: 2 sc in next st, sc in each of next 2 sts, sc in each of next 3 sts, "
            "2 sc in next st, sc in each of next 2 sts, sc in each of next 3 sts. (14 sts)\n"
        )
        pattern = _pattern(raw)
        self.assertEqual(len(pattern.rows), 2)
        issues = stitch_count.check(pattern)
        self.assertEqual([i for i in issues if i.severity == "error"], [])


# Every full-pattern test below writes each row's trailing declared count as
# "(N sts)" -- pattern_parser.py's row_re only ever recognizes a row at all
# via a trailing "(~?N sts?)" annotation (never the stitch abbreviation the
# real generator embeds inline, e.g. "(12 dc)"); the real batch-test.ts ->
# from_pattern_json.py pipeline always appends this exact normalized
# duplicate itself when the raw instructions don't already end in one (see
# from_pattern_json.py's _with_trailing_count) -- so "(N sts)" here is
# what real Row text actually looks like by the time this tool ever sees
# it, not a simplification.


class TestAmigurumiBallFullPattern(unittest.TestCase):
    # Real construction (Amigurumi Ball/Cylinder, loopdreams builders.ts
    # buildShapedRoundRows): magic ring opening round, then an increase
    # round.
    def _raw(self):
        return (
            "Row 1: Magic ring. 6 sc in ring. Place a stitch marker in the first st — work in a continuous "
            "spiral from here on, do not join or turn. (6 sts)\n"
            "Row 2: 2 sc in each st around. (12 sts)\n"
        )

    def test_full_row_verifies_clean(self):
        pattern = _pattern(self._raw())
        self.assertEqual(len(pattern.rows), 2)  # guards against the rows silently failing to parse at all
        issues = stitch_count.check(pattern)
        errors = [i for i in issues if i.severity == "error"]
        self.assertEqual(errors, [])

    def test_wrong_declared_count_on_opening_round_still_caught(self):
        raw = self._raw().replace(
            "do not join or turn. (6 sts)", "do not join or turn. (99 sts)"
        )
        pattern = _pattern(raw)
        issues = stitch_count.check(pattern)
        row1_errors = [i for i in issues if i.location == "Row 1" and i.severity == "error"]
        self.assertEqual(len(row1_errors), 1)


class TestAmigurumiStuffingAndTailClauses(unittest.TestCase):
    # Real construction (Amigurumi Ball/Limb, loopdreams generate-pattern's
    # shaped-round builders) and Amigurumi Cone (buildContinuousShapedRoundRows).
    # A loopdreams batch-test run against production (Aug 1 2026) flagged
    # these as "unrecognized clause" REVIEWs -- a single unrecognized clause
    # on a row breaks stitch-count verification for the WHOLE row, not just
    # itself, so this was masking otherwise-clean rows.
    def test_stuff_the_piece_firmly_prefix_on_decrease_round_verifies_clean(self):
        raw = (
            "Row 1: Magic ring. 6 sc in ring. Place a stitch marker in the first st — work in a continuous "
            "spiral from here on, do not join or turn. (6 sts)\n"
            "Row 2: Stuff the piece firmly as you go. *Sc2tog; rep from * around. (3 sts)\n"
        )
        pattern = _pattern(raw)
        self.assertEqual(len(pattern.rows), 2)
        issues = stitch_count.check(pattern)
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_finish_stuffing_firmly_prefix_on_closing_row_verifies_clean(self):
        # Real closing shape (Amigurumi Ball/Limb): a drawstring-cinch
        # closure (see TestGussetAndClosureRows' own mittens precedent for
        # the un-prefixed form), here prefixed with its own stuffing
        # reminder.
        raw = (
            "Row 1: Magic ring. 6 sc in ring. Place a stitch marker in the first st — work in a continuous "
            "spiral from here on, do not join or turn. (6 sts)\n"
            "Row 2: Finish stuffing firmly. Fasten off, leaving a long tail. Thread the tail through the front "
            "loop of each remaining stitch, pull tight to close the opening, and weave in the end. (6 sts)\n"
        )
        pattern = _pattern(raw)
        self.assertEqual(len(pattern.rows), 2)
        issues = stitch_count.check(pattern)
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_leaving_a_long_tail_for_seaming_verifies_clean(self):
        # Real Amigurumi Cone closing shape -- left open (no drawstring
        # closure, meant to be stuffed and attached to a body), so its tail
        # states a different purpose than the ball/limb form above.
        raw = (
            "Row 1: Magic ring. 6 sc in ring. Place a stitch marker in the first st — work in a continuous "
            "spiral from here on, do not join or turn. (6 sts)\n"
            "Row 2: 2 sc in each st around. (12 sts)\n"
            "Row 3: Fasten off, leaving a long tail for seaming. (12 sts)\n"
        )
        pattern = _pattern(raw)
        self.assertEqual(len(pattern.rows), 3)
        issues = stitch_count.check(pattern)
        self.assertEqual([i for i in issues if i.severity == "error"], [])


class TestCoasterMagicRingFullPattern(unittest.TestCase):
    # Real construction (Coaster, loopdreams builders.ts buildCoasterRows).
    # Covers all three turning-chain conventions the builder produces: SC
    # (no counted chain), HDC and DC (counted chain, "(counts as first X)").
    def test_sc_variant_verifies_clean(self):
        raw = (
            "Row 1: Magic ring. 8 sc in ring, sl st to first sc to join. (8 sts)\n"
            "Row 2: 2 sc in each st around, sl st to first sc to join. (16 sts)\n"
        )
        pattern = _pattern(raw)
        self.assertEqual(len(pattern.rows), 2)
        issues = stitch_count.check(pattern)
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_hdc_variant_verifies_clean(self):
        raw = "Row 1: Magic ring. Ch 2 (counts as first hdc), 9 hdc in ring, sl st to top of ch 2 to join. (10 sts)\n"
        pattern = _pattern(raw)
        self.assertEqual(len(pattern.rows), 1)
        issues = stitch_count.check(pattern)
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_dc_variant_verifies_clean_across_multiple_rounds(self):
        raw = (
            "Row 1: Magic ring. Ch 3 (counts as first dc), 11 dc in ring, sl st to top of ch 3 to join. (12 sts)\n"
            "Row 2: Ch 3, dc in same st, 2 dc in each remaining st around, sl st to top of ch 3 to join. (24 sts)\n"
            "Row 3: Ch 3, dc in each st around, sl st to top of ch 3 to join. Fasten off, weave in ends. (24 sts)\n"
        )
        pattern = _pattern(raw)
        self.assertEqual(len(pattern.rows), 3)
        issues = stitch_count.check(pattern)
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_wrong_declared_count_on_dc_ring_round_still_caught(self):
        raw = "Row 1: Magic ring. Ch 3 (counts as first dc), 11 dc in ring, sl st to top of ch 3 to join. (99 sts)\n"
        pattern = _pattern(raw)
        issues = stitch_count.check(pattern)
        row1_errors = [i for i in issues if i.location == "Row 1" and i.severity == "error"]
        self.assertEqual(len(row1_errors), 1)


class TestMittenMagicRingFullPattern(unittest.TestCase):
    def test_cuff_start_verifies_clean(self):
        raw = (
            "Row 1: Magic ring. 38 sc in ring. Place a stitch marker in the first st — work in a continuous "
            "spiral from here on, do not join or turn. (38 sts)\n"
            "Row 2: Sc in the back loop only of each st around. (38 sts)\n"
        )
        pattern = _pattern(raw)
        self.assertEqual(len(pattern.rows), 2)
        issues = stitch_count.check(pattern)
        self.assertEqual([i for i in issues if i.severity == "error"], [])


class TestAmigurumiEggFullPattern(unittest.TestCase):
    # Real construction (Amigurumi Egg / Basic Oval, loopdreams builders.ts
    # buildOvalRoundRows) -- foundation CHAIN, not a magic ring, but shares
    # the same "do not join or turn" continuous-spiral closing clause.
    def test_two_sided_foundation_verifies_clean(self):
        raw = (
            "Row 1: Ch 5. Sc in 2nd ch from hook and each of next 2 chs, 3 sc in last ch, working on the "
            "opposite side of the foundation chain: sc in each of next 3 chs, 3 sc in next ch. Place a stitch "
            "marker in the first st — work in a continuous spiral from here on, do not join or turn. (12 sts)\n"
            "Row 2: sc in each st around. (12 sts)\n"
        )
        pattern = _pattern(raw)
        self.assertEqual(len(pattern.rows), 2)
        issues = stitch_count.check(pattern)
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_wrong_declared_count_on_foundation_round_still_caught(self):
        raw = (
            "Row 1: Ch 5. Sc in 2nd ch from hook and each of next 2 chs, 3 sc in last ch, working on the "
            "opposite side of the foundation chain: sc in each of next 3 chs, 3 sc in next ch. Place a stitch "
            "marker in the first st — work in a continuous spiral from here on, do not join or turn. (99 sts)\n"
        )
        pattern = _pattern(raw)
        issues = stitch_count.check(pattern)
        row1_errors = [i for i in issues if i.location == "Row 1" and i.severity == "error"]
        self.assertEqual(len(row1_errors), 1)


if __name__ == "__main__":
    unittest.main()

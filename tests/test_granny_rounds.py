"""Phase 3 of the row-to-row model: the motif rounds (SCOPE_ROW_TO_ROW.md).

Three separate things stopped a Granny Square's rounds being checked, and
they had to go together — fixing any one on its own turned a warning into a
confident mismatch against a correct pattern, which happened twice while
building this and is the failure mode the whole tool exists to avoid.

Row texts are verbatim generator output.
"""
import unittest

from loopdreams_qa.stitch_parser import tokenize_round
from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count

MATERIALS = """MATERIALS
Gauge: 16 dc x 8 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 5.0 mm
ABBREVIATIONS
ch = chain, dc = double crochet, sl st = slip stitch, sc = single crochet, hdc = half double crochet, rep = repeat
"""

# Verbatim, from the deployed generator.
RING_ROUND   = ("Ch 3 (counts as first dc), 2 dc in ring, ch 2, [3 dc, ch 2] 3 times in ring, "
                "sl st to top of ch 3 to join. (12 dc, 4 ch-2 corner sps)")
CORNER_ROUND = ("Sl st to corner sp. Ch 3 (counts as first dc), 2 dc in the same sp, ch 2, "
                "3 dc in the same sp (corner made), *ch 1, [3 dc, ch 2, 3 dc] in next corner sp; "
                "rep from * 2 more times, ch 1, sl st to top of ch 3 to join. "
                "(24 dc, 4 ch-2 corner sps, 4 ch-1 sps)")


# The real pipeline states each round's count as a trailing "(N sts)" --
# from_pattern_json appends it from the generator's own stitch_count, because
# a prose tally like "(12 dc, 4 ch-2 corner sps)" is not one number. Mirrored
# here: without it there is no declared count to check against and every
# mutation below would pass for the wrong reason.
def _rounds(*body):
    rows = "\n".join(f"Row {i + 2}: {text} ({count} sts)" for i, (text, count) in enumerate(body))
    raw = ("Test Granny\n" + MATERIALS + "PATTERN STEPS\n"
           "Row 1: Ch 5, join with sl st to form ring. (12 sts)\n" + rows + "\n")
    return [i for i in stitch_count.check(parse(raw)) if i.location.startswith("Row")]


class BracketOfMixedStitchesTest(unittest.TestCase):
    """"[3 dc, ch 2] 3 times in ring" — the members name no target of their
    own, because the bracket names it once for all of them."""

    def test_the_members_resolve(self):
        clauses = tokenize_round("[3 dc, ch 2] 3 times in ring")
        self.assertEqual(len(clauses), 1)
        subs = clauses[0].sub_clauses
        self.assertEqual([c.clause_type for c in subs], ["literal_count", "chain"])
        self.assertEqual(subs[0].produces, 3, "the bare '3 dc' should take the bracket's own target")

    def test_a_member_that_names_its_own_target_is_untouched(self):
        subs = tokenize_round("[3 dc in next sp, ch 1] 2 times")[0].sub_clauses
        self.assertEqual(subs[0].clause_type, "cluster_same_spot")
        self.assertEqual(subs[0].consumes, 1)

    def test_a_chain_never_picks_up_the_target(self):
        subs = tokenize_round("[3 dc, ch 2] 3 times in ring")[0].sub_clauses
        self.assertEqual(subs[1].clause_type, "chain")
        self.assertEqual(subs[1].produces, 0)


class RingRoundTest(unittest.TestCase):
    """A round worked into the ring consumes the ring, not counted stitches."""

    def test_the_round_verifies(self):
        self.assertEqual(_rounds((RING_ROUND, 12)), [])

    def test_a_wrong_declared_count_is_caught(self):
        issues = _rounds((RING_ROUND, 14))
        self.assertTrue(issues, "the round produces 12, not the 14 declared")
        self.assertEqual(issues[0].severity, "error")

    def test_a_dropped_stitch_inside_the_bracket_is_caught(self):
        issues = _rounds((RING_ROUND.replace("[3 dc, ch 2] 3 times", "[2 dc, ch 2] 3 times"), 12))
        self.assertTrue(issues, "a 2-dc bracket produces 9, not the 12 declared")
        self.assertEqual(issues[0].severity, "error")


class SharedSpotRoundTest(unittest.TestCase):
    """A motif round worked into the previous round's SPACES.

    Its consumption is a count of spaces; the number it would be checked
    against is a count of stitches (Round 2 declares 12 dc, Round 3 works 4
    corner spaces). Not comparable, so not compared — but what the round
    produces is still checked against what it declares, and the repetition
    count is read from the text since there is nothing to solve it from.
    """

    def test_the_round_verifies(self):
        self.assertEqual(_rounds((RING_ROUND, 12), (CORNER_ROUND, 24)), [])

    def test_a_wrong_declared_count_is_caught(self):
        issues = _rounds((RING_ROUND, 12), (CORNER_ROUND, 26))
        self.assertTrue(issues, "the round produces 24, not the 26 declared")
        self.assertEqual(issues[0].severity, "error")

    def test_a_wrong_stated_repeat_count_is_caught(self):
        # The stated count is READ here rather than solved, so it has to be
        # the produced total that catches this.
        issues = _rounds((RING_ROUND, 12),
                         (CORNER_ROUND.replace("rep from * 2 more times", "rep from * 3 more times"), 24))
        self.assertTrue(issues, "a fourth repeat produces 30, not the 24 declared")
        self.assertEqual(issues[0].severity, "error")


class PartialRepeatTest(unittest.TestCase):
    """"then * to ** once" — a square's fourth side, worked without the
    corner that closes the other three."""

    def test_it_is_recognised(self):
        clauses = tokenize_round("rep from * 2 more times, then * to ** once")
        self.assertEqual([c.clause_type for c in clauses], ["repeat_close", "repeat_partial"])
        self.assertEqual(clauses[1].explicit_count, 1)

    SIDE = ("Join Colour 1 with sl st in next ch-1 sp. Ch 3 (counts as dc), "
            "[1 dc, ch 2, 2 dc] in the same sp (corner made). "
            "*1 dc in each of next 2 sts, 1 hdc in each of next 2 sts, 1 sc in each of next 3 sts, "
            "1 hdc in each of next 2 sts, 1 dc in each of next 2 sts,** "
            "[2 dc, ch 2, 2 dc] in next st (corner made); rep from * 2 more times, then * to ** once. "
            "Join with sl st to top of ch 3. (60 sts, 4 ch-2 corner sps)")

    def test_the_round_verifies(self):
        # 4 + 3x15 + 11 = 60, the declared count.
        self.assertEqual(_rounds((self.SIDE, 60)), [])

    def test_removing_the_partial_is_caught(self):
        issues = _rounds((self.SIDE.replace(", then * to ** once", ""), 60))
        self.assertTrue(issues, "without the fourth side the round produces 49, not 60")
        self.assertEqual(issues[0].severity, "error")

    def test_working_the_partial_twice_is_caught(self):
        issues = _rounds((self.SIDE.replace("then * to ** once", "then * to ** twice"), 60))
        self.assertTrue(issues, "a second partial produces 71, not 60")
        self.assertEqual(issues[0].severity, "error")


class NotOverreachedTest(unittest.TestCase):
    """The shared-spot gate turns OFF a real check, so it must not catch rows
    that never needed it. Both near-misses below were found by measuring."""

    def test_a_moss_row_still_has_its_consumption_checked(self):
        # Moss works into ch-1 spaces on every row and its counts ARE
        # comparable. Gating on "works into a space" caught it and broke four
        # of its tests; the gate is on a group worked into a SHARED spot.
        raw = ("Test Moss\n" + MATERIALS.replace("16 dc x 8 rows", "16 sc x 16 rows") + "PATTERN STEPS\n"
               "Foundation:Ch 22, turn.\n"
               "Row 1: Skip the first 1 chain from the hook (it doesn't count as a stitch). "
               "Sc in the next chain and in each ch across. Ch 1, turn. (21 sts)\n"
               "Row 2: Sc in first st, *ch 1, skip 1 st, sc in next st; rep from * 9 more times. "
               "Ch 1, turn. (25 sts)\n")
        issues = [i for i in stitch_count.check(parse(raw)) if i.location == "Row 2"]
        self.assertTrue(issues, "a 21-stitch moss row declaring 25 must still be reported")


if __name__ == "__main__":
    unittest.main()

import unittest

from loopdreams_qa.checks import colourwork_orientation as co
from loopdreams_qa.models import Pattern


A, B = "#C9A227", "#4F7942"
# Asymmetric on BOTH axes, so neither a vertical flip nor a per-row mirror can
# hide behind the other -- which is precisely how loopdreams #474 went unseen.
F = ["BBBBBBBB", "BAAAAAAA", "BAAAAAAA", "BBBBAAAA", "BAAAAAAA", "BAAAAAAA", "BAAAAAAA", "AAAAAAAA"]
DESIGN = [[A if c == "A" else B for c in row] for row in F]


def _pattern(rows, grid=DESIGN, palette=(A, B)):
    p = Pattern()
    p.design_grid = grid
    p.design_palette = list(palette)
    p.design_rows = rows
    return p


# Real output from the generator (buildGenericFlatColourRows, dc, the 4x4 design
# above resampled to 8 sts x 6 rows), copied verbatim rather than reconstructed.
# A hand-written imitation would only prove this check agrees with my idea of
# the generator; the point is that it agrees with the generator.
FAITHFUL_ROWS = [
    {"row_number": 1, "stitch_count": 8, "instructions": "With Colour 2, Ch 10, turn."},
    {"row_number": 2, "stitch_count": 8, "instructions": "Skip the first 3 chains from the hook (they count as this row's first stitch). With Colour 2, dc in the next chain, changing to Colour 1 in the last st; 6 dc in next 6 chs. Ch 3, turn."},
    {"row_number": 3, "stitch_count": 8, "instructions": "With Colour 1, skip first st, 3 dc in next 3 sts, changing to Colour 2 in the last st; 3 dc in next 3 sts, dc in top of ch. Ch 3, turn."},
    {"row_number": 4, "stitch_count": 8, "instructions": "With Colour 2, skip first st, 3 dc in next 3 sts, changing to Colour 1 in the last st; 3 dc in next 3 sts, dc in top of ch. Ch 3, turn."},
    {"row_number": 5, "stitch_count": 8, "instructions": "With Colour 1, skip first st, 5 dc in next 5 sts, changing to Colour 2 in the last st; 1 dc in next 1 st, dc in top of ch. Ch 3, turn."},
    {"row_number": 6, "stitch_count": 8, "instructions": "Skip first st, dc in each st across, dc in top of ch. Ch 3, turn."},
    {"row_number": 7, "stitch_count": 8, "instructions": "Skip first st, dc in each st across, dc in top of ch. Fasten off, weave in ends."},
]
SMALL_DESIGN = [[A if c == "A" else B for c in row] for row in ["BBBB", "BAAA", "BBAA", "BAAA"]]


class TestOrientation(unittest.TestCase):
    def test_no_grid_is_not_this_check_s_business(self):
        p = Pattern()
        self.assertEqual(co.check(p), [])

    def test_single_colour_grid_is_ignored(self):
        p = _pattern([], grid=[[A, A], [A, A]])
        self.assertEqual(co.check(p), [])

    def test_a_dropped_design_is_an_error_not_a_shrug(self):
        # loopdreams #477: a design was requested and the plain builder ran
        # anyway. Valid rows, correct counts, no colour anywhere.
        rows = [{"row_number": n, "stitch_count": 8,
                 "instructions": "Skip first st, dc in each st across, dc in top of ch. Ch 3, turn."}
                for n in range(1, 6)]
        issues = co.check(_pattern(rows))
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")
        self.assertIn("never name a colour", issues[0].message)

    def test_working_order_is_bottom_up_and_alternately_mirrored(self):
        # The two halves of #474, asserted directly on the helper.
        grid = [["a", "b"], ["c", "d"], ["e", "f"]]
        self.assertEqual(co.to_working_order(grid), [["e", "f"], ["d", "c"], ["a", "b"]])

    def test_real_generator_output_passes(self):
        self.assertEqual(co.check(_pattern(FAITHFUL_ROWS, grid=SMALL_DESIGN)), [])

    def test_the_same_output_against_a_different_design_is_caught(self):
        # The instructions are unchanged and internally valid; only the design
        # they claim to make is different. Nothing but this check can tell.
        flipped = list(reversed(SMALL_DESIGN))
        issues = co.check(_pattern(FAITHFUL_ROWS, grid=flipped))
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")
        self.assertIn("do not make the chosen design", issues[0].message)

    def test_mirroring_every_other_row_is_caught(self):
        mirrored = [list(reversed(r)) for r in SMALL_DESIGN]
        issues = co.check(_pattern(FAITHFUL_ROWS, grid=mirrored))
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "error")


class TestCoverageWording(unittest.TestCase):
    """A partial check must not read as a pass. Saying "the design checks out on
    the 0 of 45 rows this can read" is true and misleading at once — it reports
    having verified nothing as though it were agreement."""

    def _issue(self, read_rows, unread_count):
        actual = [["Colour 1"] for _ in range(read_rows)] + [None] * unread_count
        unread = [(i + 1, "a reason") for i in range(unread_count)]
        return co._coverage(actual, unread)[0]

    def test_nothing_read_does_not_claim_the_design_checks_out(self):
        msg = self._issue(0, 12).message
        self.assertIn("Could not check this design", msg)
        self.assertNotIn("checks out", msg)
        self.assertIn("nothing here confirms it either", msg)

    def test_some_read_claims_only_what_was_compared(self):
        msg = self._issue(48, 48).message
        self.assertIn("checks out on the 48 row(s) this could read", msg)
        self.assertIn("48 colourwork row(s) could not be read", msg)

    def test_nothing_unread_is_silent(self):
        self.assertEqual(co._coverage([["Colour 1"]] * 5, []), [])

import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count


MATERIALS = """MATERIALS
Gauge: 16 sc x 16 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 5.5 mm
"""


def _issues(*body_rows, declared=21):
    """Rows 3+ of a 21-stitch moss piece, checked. Row 1 is the foundation and
    row 2 the plain setup pass, exactly as the generator writes them."""
    rows = "\n".join(
        f"Row {i + 2}: {text} ({declared} sts)" for i, text in enumerate(body_rows)
    )
    raw = (
        "Test Coaster\n" + MATERIALS
        + "ABBREVIATIONS\nch = chain, sc = single crochet, rep = repeat\n"
        "PATTERN STEPS\n"
        "Foundation:Ch 22, turn.\n"
        "Row 1: Skip the first 1 chain from the hook (it doesn't count as a stitch). "
        "Sc in the next chain and in each ch across. Ch 1, turn. (21 sts)\n"
        + rows + "\n"
        "Finishing\nBorder: Fasten off. (21 sts)\n"
    )
    return [i for i in stitch_count.check(parse(raw)) if i.location.startswith("Row")]


class MossChainConventionTest(unittest.TestCase):
    """Moss and linen count their ch-1 spaces toward the row total.

    The alternate convention that allows for it used to be applied to the
    REPEATED UNIT only. That holds while every ch-1 stays inside the bracket,
    and breaks the moment a colour change unrolls the first repeat into the
    clauses before it -- which is what a coloured moss row does whenever the
    design's first run is short. Real output from buildMossStitchColourRows at
    a 5 in square coaster, where a correct 21-stitch row read as 20 and every
    body row after it failed.
    """

    # Verbatim generator output, not reconstructed.
    UNROLLED = ("With Colour 2, Sc in first st, ch 1, sc in next ch-1 sp, skip next st, "
                "changing to Colour 1 in the last st; *ch 1, sc in next ch-1 sp, skip next st; "
                "rep from * 8 more times. Ch 1, turn.")
    TRAILING = ("With Colour 1, Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; "
                "rep from * 8 more times, changing to Colour 2 in the last st; "
                "ch 1, sc in next ch-1 sp, skip next st. Ch 1, turn.")
    PLAIN = "Sc in first st, *ch 1, skip 1 st, sc in next st; rep from * 9 more times. Ch 1, turn."

    def test_a_row_whose_first_repeat_is_unrolled_verifies(self):
        # 1 sc + (ch 1 + sc) + 9 x (ch 1 + sc) = 21 counted stitches.
        self.assertEqual(_issues(self.UNROLLED), [])

    def test_a_row_whose_last_repeat_is_unrolled_verifies(self):
        # The same thing at the other end, in the post-zone.
        self.assertEqual(_issues(self.TRAILING), [])

    def test_the_wholly_bracketed_row_still_verifies(self):
        # The shape that always worked — guarding against fixing one and
        # breaking the other.
        self.assertEqual(_issues(self.PLAIN), [])

    def test_the_turning_chain_is_still_not_a_stitch(self):
        # The whole difficulty: every ch-1 the row WORKS counts, and the
        # "Ch 1, turn." at the end never does. If it were counted too, each of
        # these rows would come to 22 against a declared 21 and fail — so
        # these passing at all is the assertion.
        self.assertEqual(_issues(self.PLAIN, self.UNROLLED, self.TRAILING), [])

    def test_a_genuinely_wrong_count_is_still_caught(self):
        # The convention must not become a way for any row to pass.
        #
        # The mutation is the DECLARED count, not the stated repeat count, and
        # that is not arbitrary: this path solves the repetitions from the
        # previous row rather than reading the number in the text, so editing
        # "8 more times" changes nothing it looks at. (My first version of this
        # test did exactly that and passed for the wrong reason.) What it does
        # compare is produced against declared, so that is what to perturb.
        issues = _issues(self.UNROLLED, declared=25)
        self.assertTrue(issues, "a row declaring a count it does not produce should be reported")
        self.assertEqual(issues[0].severity, "error")

    def test_the_convention_is_not_applied_to_a_fabric_that_does_not_want_it(self):
        # A plain dc row's turning chain is not a stitch here either, and its
        # ch-1s are not fabric. 20 dc declared as 20 verifies; the alternate
        # must not quietly rescue a wrong one by counting chains.
        self.assertEqual(_issues("Dc in each st across. Ch 1, turn.", declared=21), [])


if __name__ == "__main__":
    unittest.main()

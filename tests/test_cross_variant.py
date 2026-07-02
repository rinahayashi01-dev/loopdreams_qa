import unittest

from loopdreams_qa import cross_variant
from loopdreams_qa.pattern_parser import parse

MATERIALS_BLOCK = """MATERIALS
Gauge: 18 sc x 20 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 4.0 mm
"""


def _pattern(stitch_guide_body: str, row1_text: str):
    raw = (
        "Test Blanket\n"
        + MATERIALS_BLOCK
        + "STITCH GUIDE\n"
        + stitch_guide_body + "\n"
        "ABBREVIATIONS\n"
        "ch = chain, sc = single crochet, rep = repeat\n"
        "PATTERN STEPS\n"
        "Foundation:Ch 22, turn.\n"
        f"Row 1: {row1_text} (21 sts)\n"
        "Finishing\n"
        "Border: Fasten off. (40 sts)\n"
    )
    return parse(raw)


class TestCrossVariantConsistency(unittest.TestCase):
    def test_claimed_equivalent_stitches_with_mismatched_row1_flagged(self):
        # Real case (Jul 2 throw-blanket batch, tenth round): both guides
        # claim to be the same stitch as each other, but one has a plain
        # setup row and the other jumps straight into alternating.
        moss = _pattern(
            "Moss Stitch: An alternating sc/ch1 pattern. Also called the linen stitch.",
            "Sc in 2nd ch from hook and in each ch across. Ch 1, turn.",
        )
        linen = _pattern(
            "Linen Stitch: An alternating sc/ch1 pattern. Also called the moss stitch.",
            "SC in 2nd ch from hook, *ch 1, skip 1 ch, SC in next ch; rep from * to end. Ch 1, turn.",
        )
        issues = cross_variant.check({"moss.pdf": moss, "linen.pdf": linen})
        self.assertEqual(len(issues), 1)
        msg = issues[0].message
        self.assertIn("linen.pdf", msg)
        self.assertIn("moss.pdf", msg)
        self.assertIn("missing its initial setup row", msg)

    def test_claimed_equivalent_stitches_with_matching_row1_not_flagged(self):
        # Both start alternating immediately in Row 1 -- consistent with
        # each other, nothing to flag even though they claim equivalence.
        moss = _pattern(
            "Moss Stitch: An alternating sc/ch1 pattern. Also called the linen stitch.",
            "SC in 2nd ch from hook, *ch 1, skip 1 ch, SC in next ch; rep from * to end. Ch 1, turn.",
        )
        linen = _pattern(
            "Linen Stitch: An alternating sc/ch1 pattern. Also called the moss stitch.",
            "SC in 2nd ch from hook, *ch 1, skip 1 ch, SC in next ch; rep from * to end. Ch 1, turn.",
        )
        issues = cross_variant.check({"moss.pdf": moss, "linen.pdf": linen})
        self.assertEqual(issues, [])

    def test_unrelated_stitches_with_different_row1_not_flagged(self):
        # Different named stitches, no claimed equivalence -- a Row 1
        # difference here is just a real design difference, not an
        # inconsistency worth flagging.
        shell = _pattern(
            "Shell Stitch: Fan-shaped clusters of 5 dc.",
            "Sc in 2nd ch from hook and in each ch across. Ch 1, turn.",
        )
        sedge = _pattern(
            "Sedge Stitch: Three-stitch clusters. Also called the shell cluster stitch.",
            "SC in 2nd ch from hook, *ch 1, skip 1 ch, SC in next ch; rep from * to end. Ch 1, turn.",
        )
        issues = cross_variant.check({"shell.pdf": shell, "sedge.pdf": sedge})
        self.assertEqual(issues, [])

    def test_no_stitch_guide_section_skipped_gracefully(self):
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 22, turn.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (21 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        no_guide = parse(raw)
        moss = _pattern(
            "Moss Stitch: An alternating sc/ch1 pattern. Also called the linen stitch.",
            "Sc in 2nd ch from hook and in each ch across. Ch 1, turn.",
        )
        issues = cross_variant.check({"plain.pdf": no_guide, "moss.pdf": moss})
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()

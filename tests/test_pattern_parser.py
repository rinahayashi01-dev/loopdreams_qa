import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import completeness

MATERIALS_BLOCK = """MATERIALS
Gauge: 18 sc x 20 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 4.0 mm
"""


class TestRepeatNMoreTimesShorthand(unittest.TestCase):
    def test_repeat_rows_x_n_more_times_closes_the_row_gap(self):
        # Real phrasing found on a real sample (tote bag, Jul 4 batch):
        # "Repeat Rows 2-3 x 38 more times." with NO leading "Rows 4-79:"
        # label at all, unlike the previously-supported "Rows N-M: Repeat
        # Row(s) P-Q." shorthand. Before this fix, this phrase was
        # invisible to the parser entirely, so the row-gap completeness
        # check saw a hard gap between Row 3 and Row 80 and raised a false
        # "no instructions for Rows 4-79" error on an otherwise-correct
        # pattern.
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, fpdc = front post double crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 72.\n"
            "Row 1: DC in 4th ch from hook and in each ch across. Ch 2, turn. (69 sts)\n"
            "Row 2: Ch 2 (counts as dc), skip first st, *fpdc around next st, dc in next 2 sts; "
            "rep from * to last 2 sts, fpdc around next st, dc in top of ch. Ch 2, turn. (69 sts)\n"
            "Row 3: Ch 2 (counts as dc), skip first st, *dc in next st, fpdc around next 2 sts; "
            "rep from * to last 2 sts, dc in next st, dc in top of ch. Ch 2, turn. (69 sts)\n"
            "Repeat Rows 2–3 × 38 more times.\n"
            "Row 80: Ch 2 (counts as dc), skip first st, *fpdc around next st, dc in next 2 sts; "
            "rep from * to last 2 sts, fpdc around next st, dc in top of ch. Fasten off. (69 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)

        labels = [r.label for r in pattern.rows]
        self.assertIn("Rows 4-79", labels)

        gap_row = next(r for r in pattern.rows if r.label == "Rows 4-79")
        self.assertEqual(gap_row.row_start, 4)
        self.assertEqual(gap_row.row_end, 79)
        self.assertEqual(gap_row.referenced_rows, [2, 3])
        self.assertEqual(gap_row.declared_count, 69)

        issues = completeness.check(pattern)
        row_gap_issues = [i for i in issues if "Rows 4" in i.message or "jumps from" in i.message]
        self.assertEqual(row_gap_issues, [])

    def test_without_the_fix_shape_missing_anchor_is_left_unrecognized(self):
        # If the referenced range's last row was never actually parsed
        # (e.g. a typo referencing a row number that doesn't exist), don't
        # guess an anchor -- leave it unrecognized rather than silently
        # inventing a row range.
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 22, turn.\n"
            "Row 1: DC in 4th ch from hook and in each ch across. Ch 2, turn. (19 sts)\n"
            "Repeat Rows 2-3 x 5 more times.\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        labels = [r.label for r in pattern.rows]
        self.assertNotIn("Rows 4-13", labels)


if __name__ == "__main__":
    unittest.main()

import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import completeness

MATERIALS_BLOCK = """MATERIALS
Gauge: 18 sc x 20 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 4.0 mm
"""

BASE = (
    "Test Tote Bag\n"
    + MATERIALS_BLOCK
    + "ABBREVIATIONS\n"
    "ch = chain, sc = single crochet, rep = repeat\n"
    "PATTERN STEPS\n"
    "Foundation:Ch 22, turn.\n"
    "Row 1: SC in 2nd ch from hook and in each ch across. Ch 1, turn. (21 sts)\n"
    "Finishing\n"
    "Assembly: Fold panel in half. Seam both side edges.\n"
)


def _zipper_liner_issues(section_body: str):
    raw = BASE + "Adding a Zipper & Liner\n" + section_body + "\n"
    pattern = parse(raw)
    return [i for i in completeness.check(pattern) if i.location == "Adding a Zipper & Liner"]


class TestZipperLinerCheck(unittest.TestCase):
    def test_liner_only_flags_missing_zipper(self):
        # Real case (tote bag, Jul 5 batch): section titled "Adding a
        # Zipper & Liner" but the body only ever gave liner instructions.
        issues = _zipper_liner_issues(
            "Adding a Liner: Cut fabric to size. Sew the liner and whip stitch it in place."
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("zipper", issues[0].message)
        self.assertIn("only liner content is present", issues[0].message)

    def test_zipper_only_flags_missing_liner(self):
        issues = _zipper_liner_issues(
            "Adding a Zipper: Pin the zipper to the top edge and sew in place."
        )
        self.assertEqual(len(issues), 1)
        self.assertIn("liner", issues[0].message)
        self.assertIn("only zipper content is present", issues[0].message)

    def test_both_present_not_flagged(self):
        issues = _zipper_liner_issues(
            "Adding a Zipper: Pin the zipper to the top edge and sew in place.\n"
            "Adding a Liner: Cut fabric to size. Sew the liner and whip stitch it in place."
        )
        self.assertEqual(issues, [])

    def test_no_zipper_liner_section_not_checked(self):
        raw = BASE
        pattern = parse(raw)
        issues = [i for i in completeness.check(pattern) if i.location == "Adding a Zipper & Liner"]
        self.assertEqual(issues, [])


if __name__ == "__main__":
    unittest.main()

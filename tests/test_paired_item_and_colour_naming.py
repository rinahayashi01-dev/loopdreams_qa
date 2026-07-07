import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import completeness

MATERIALS_BLOCK = """MATERIALS
Gauge: 16 sc x 8 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 5.0 mm
"""


def _pattern(title, pattern_steps, extra_materials=""):
    raw = (
        f"{title}\n"
        + MATERIALS_BLOCK
        + extra_materials
        + "ABBREVIATIONS\n"
        "ch = chain, sc = single crochet, rep = repeat\n"
        "PATTERN STEPS\n"
        + pattern_steps
        + "Finishing\n"
        "Border: Fasten off. (40 sts)\n"
    )
    return parse(raw)


class TestPairedItemCheck(unittest.TestCase):
    def test_mittens_with_no_second_piece_mentioned_flagged(self):
        # Real case (mittens, Jul 7 batch): the pattern only ever
        # constructs one mitten, with no "make 2"/"second mitten"/pair
        # instruction anywhere.
        pattern = _pattern(
            "Mittens — Jul 7",
            "Foundation:Ch 22, turn.\n"
            "Row 1: Sc in each st across. Ch 1, turn. (21 sts)\n",
        )
        issues = completeness.check(pattern)
        paired_issues = [i for i in issues if i.location == "Pattern" and "matched pair" in i.message]
        self.assertEqual(len(paired_issues), 1)
        self.assertEqual(paired_issues[0].severity, "error")

    def test_mittens_with_make_2_instruction_not_flagged(self):
        pattern = _pattern(
            "Mittens — Jul 7",
            "Foundation:Ch 22, turn.\n"
            "Row 1: Sc in each st across. Ch 1, turn. (21 sts)\n"
            "Make 2 mittens total, repeating the pattern for the second mitten.\n",
        )
        issues = completeness.check(pattern)
        paired_issues = [i for i in issues if i.location == "Pattern" and "matched pair" in i.message]
        self.assertEqual(paired_issues, [])

    def test_non_paired_item_title_not_flagged(self):
        pattern = _pattern(
            "Scarf — Jul 7",
            "Foundation:Ch 22, turn.\n"
            "Row 1: Sc in each st across. Ch 1, turn. (21 sts)\n",
        )
        issues = completeness.check(pattern)
        paired_issues = [i for i in issues if i.location == "Pattern" and "matched pair" in i.message]
        self.assertEqual(paired_issues, [])


class TestColourNamingConsistencyCheck(unittest.TestCase):
    def test_same_colour_under_two_identifiers_flagged(self):
        # Real case (mittens, Jul 7 batch): "Colour 2" (Foundation, Row 3)
        # and "Colour B" (Rows 4-5) both refer to "Moss", never reconciled.
        pattern = _pattern(
            "Mittens — Jul 7",
            "Foundation:With Colour 1 — Honey, magic ring. 6 sc in ring. (6 sc)\n"
            "Row 1: Sc in each st around, changing to Colour 2 — Moss in the last st. (6 sc) (6 sts)\n"
            "Row 2: With Colour B — Moss: Sc in each st around. (6 sc) (6 sts)\n",
        )
        issues = completeness.check(pattern)
        colour_issues = [i for i in issues if "different identifiers" in i.message]
        self.assertEqual(len(colour_issues), 1)
        self.assertIn("Moss", colour_issues[0].message)
        self.assertEqual(colour_issues[0].severity, "warning")

    def test_consistent_colour_naming_not_flagged(self):
        pattern = _pattern(
            "Mittens — Jul 7",
            "Foundation:With Colour 1 — Honey, magic ring. 6 sc in ring. (6 sc)\n"
            "Row 1: Sc in each st around, changing to Colour 2 — Moss in the last st. (6 sc) (6 sts)\n"
            "Row 2: With Colour 2 — Moss: Sc in each st around. (6 sc) (6 sts)\n",
        )
        issues = completeness.check(pattern)
        colour_issues = [i for i in issues if "different identifiers" in i.message]
        self.assertEqual(colour_issues, [])


if __name__ == "__main__":
    unittest.main()

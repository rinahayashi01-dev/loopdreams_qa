import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import known_constructions

MATERIALS_BLOCK = """MATERIALS
Gauge: 18 sc x 20 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 4.0 mm
"""

WAFFLE_GUIDE = (
    "Waffle Stitch: A squishy, deeply textured stitch. It is built from a\n"
    "2-row repeat using double crochet (dc) and front post double\n"
    "crochet (FPdc).\n"
    "Stitch multiple: Multiples of 3 + 2\n"
)


def _pattern(foundation_chain, row1_ordinal, row1_sts):
    raw = (
        "Test Blanket\n"
        + MATERIALS_BLOCK
        + "STITCH GUIDE\n"
        + WAFFLE_GUIDE
        + "ABBREVIATIONS\n"
        "ch = chain, dc = double crochet, fpdc = front post double crochet, rep = repeat\n"
        "PATTERN STEPS\n"
        f"Foundation:Ch {foundation_chain}.\n"
        f"Row 1: DC in {row1_ordinal} ch from hook and in each ch across. Ch 2, turn. ({row1_sts} sts)\n"
        "Finishing\n"
        "Border: Fasten off. (40 sts)\n"
    )
    return parse(raw)


SEDGE_GUIDE = (
    "Sedge Stitch: A beginner-friendly textured stitch made from small\n"
    "three-stitch clusters.\n"
    "Stitch multiple: Multiple of 3\n"
)


def _sedge_pattern(foundation_chain, skip_n):
    # Sedge's Row 1 phrases its skip as "Skip the first N chain(s) from the
    # hook" (clause type skip_first_chains_from_hook) rather than waffle's
    # ordinal "Nth ch from hook" (foundation_into_chain) -- a genuinely
    # different clause type, not just different wording of the same one
    # (confirmed empirically before adding known_constructions' handling for
    # it). Exercises that second code path.
    raw = (
        "Test Coaster\n"
        + MATERIALS_BLOCK
        + "STITCH GUIDE\n"
        + SEDGE_GUIDE
        + "ABBREVIATIONS\n"
        "ch = chain, sc = single crochet, hdc = half double crochet, dc = double crochet, rep = repeat\n"
        "PATTERN STEPS\n"
        f"Foundation:Ch {foundation_chain}.\n"
        f"Row 1: Skip the first {skip_n} chain from the hook (it doesn't count as a stitch). "
        f"Hdc in the next chain, dc in the same chain. *skip 2 chains, (sc, hdc, dc) in next chain "
        f"(sedge made); rep from * to the last chain, sc in last chain. Ch 1, turn. ({foundation_chain} sts)\n"
        "Finishing\n"
        f"Fasten off. ({foundation_chain} sts)\n"
    )
    return parse(raw)


class TestKnownConstructions(unittest.TestCase):
    def test_real_case_flags_both_row1_skip_and_foundation_multiple(self):
        # Real case (tote bag, Jul 4 batch): "4th ch from hook" (skip 3)
        # on a Ch 72 foundation. Verified against Bella Coco's published
        # Waffle Stitch pattern: canonical skip is 2 ("3rd ch from hook"),
        # and the foundation chain must be a multiple of 3, plus 2 -- 72
        # satisfies neither.
        pattern = _pattern(foundation_chain=72, row1_ordinal="4th", row1_sts=69)
        issues = known_constructions.check(pattern)
        self.assertEqual(len(issues), 2)

        row1_issue = next(i for i in issues if i.location == "Row 1")
        self.assertIn("skips 3 chain", row1_issue.message)
        self.assertIn("skips 2 chain", row1_issue.message)

        foundation_issue = next(i for i in issues if i.location == "Foundation")
        self.assertIn("72", foundation_issue.message)
        self.assertIn("71", foundation_issue.message)

    def test_canonical_construction_not_flagged(self):
        # Ch 71 = 3*23 + 2 (satisfies the multiple), "3rd ch from hook"
        # (skip 2) matches the verified reference exactly -- must be clean.
        pattern = _pattern(foundation_chain=71, row1_ordinal="3rd", row1_sts=69)
        issues = known_constructions.check(pattern)
        self.assertEqual(issues, [])

    def test_unrelated_stitch_name_not_checked(self):
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "STITCH GUIDE\n"
            "Shell Stitch: Fan-shaped clusters of 5 dc.\n"
            "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, sc = single crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 72.\n"
            "Row 1: DC in 4th ch from hook and in each ch across. Ch 2, turn. (69 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        self.assertEqual(known_constructions.check(pattern), [])

    def test_no_stitch_guide_section_not_checked(self):
        raw = (
            "Test Blanket\n"
            + MATERIALS_BLOCK
            + "ABBREVIATIONS\n"
            "ch = chain, dc = double crochet, rep = repeat\n"
            "PATTERN STEPS\n"
            "Foundation:Ch 72.\n"
            "Row 1: DC in 4th ch from hook and in each ch across. Ch 2, turn. (69 sts)\n"
            "Finishing\n"
            "Border: Fasten off. (40 sts)\n"
        )
        pattern = parse(raw)
        self.assertEqual(known_constructions.check(pattern), [])

    def test_sedge_canonical_construction_not_flagged(self):
        # Skip 1 chain, 21 chains (a clean multiple of 3) -- matches the
        # verified Daisy Farm Crafts construction exactly. Must be clean.
        pattern = _sedge_pattern(foundation_chain=21, skip_n=1)
        self.assertEqual(known_constructions.check(pattern), [])

    def test_sedge_wrong_skip_flagged(self):
        # Real regression class this entry exists to catch: LoopDreams'
        # Sedge Stitch was wrong on its very first attempt (an unsourced
        # 3n+1 construction) before being corrected against this same
        # source -- a future reintroduction of a wrong skip count should be
        # caught automatically, not require another real crocheter to find
        # it by hand.
        pattern = _sedge_pattern(foundation_chain=21, skip_n=2)
        issues = known_constructions.check(pattern)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].location, "Row 1")
        self.assertIn("skips 2 chain", issues[0].message)
        self.assertIn("skips 1 chain", issues[0].message)

    def test_sedge_wrong_foundation_multiple_flagged(self):
        # 20 isn't a multiple of 3 -- Sedge's real foundation-chain
        # requirement, unlike waffle's "multiple of 3, plus 2".
        pattern = _sedge_pattern(foundation_chain=20, skip_n=1)
        issues = known_constructions.check(pattern)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].location, "Foundation")
        self.assertIn("20", issues[0].message)


if __name__ == "__main__":
    unittest.main()

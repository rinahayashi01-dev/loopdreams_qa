"""Mitten thumb pickup with a corner st each side of the bridge
(loopdreams fix/mitten-gusset-and-top, 2026-11-18)."""
import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count

RAW_HEAD = (
    "Test Mitten\n"
    "MATERIALS\nGauge: 16 sc x 8 rows = 4 in [10 cm]\nTerminology: US\nYarn: Test yarn\nHook: 5.0 mm\n"
    "ABBREVIATIONS\nch = chain, sc = single crochet, sc2tog = sc2tog, sl st = slip stitch, rep = repeat\n"
    "PATTERN STEPS\n"
)

PICKUP = (
    "Join yarn with sl st in the marked gusset st (the first skipped st), ch 1. Sc in each of the 12 skipped "
    "gusset sts (the first sc goes in the st you joined in), sc in the gap at the corner, then sc 4 sts evenly "
    "across the bridge chain (1 sc in the free loop of each ch), sc in the gap at the other corner. Place a "
    "stitch marker in the first sc and move it up each round — work in a continuous spiral from here."
)


def _rows(pickup_count: int, corner_count: int):
    return parse(
        RAW_HEAD
        + "Row 1: Ch 36, join with sl st to form ring, taking care not to twist the chain. (36 sts)\n"
        + "Row 2: Fasten off, leaving a long tail. Thread the tail through the front loop of each remaining "
          "stitch, pull tight to close the fingertip opening, and weave in the end. (8 sts)\n"
        + f"Row 3: {PICKUP} ({pickup_count} sc) ({pickup_count} sts)\n"
        + f"Row 4: Sc in each of next 12 sts, sc2tog, sc in each of next 2 sts, sc2tog. ({corner_count} sc) ({corner_count} sts)\n"
    )


def _row_issues(pattern, label):
    return [i for i in stitch_count.check(pattern) if i.location == label]


class TestThumbCornerGap(unittest.TestCase):
    def test_pickup_with_corner_sts_verifies(self):
        p = _rows(18, 16)
        self.assertEqual(_row_issues(p, "Row 3"), [])
        self.assertEqual(_row_issues(p, "Row 4"), [])

    def test_pickup_miscount_is_an_error(self):
        # Without the corner sts counted the pickup would be 16; declaring 16
        # against a text that makes 18 must fail, not abstain.
        issues = _row_issues(_rows(16, 16), "Row 3")
        self.assertTrue(issues)
        self.assertTrue(all(i.severity == "error" for i in issues), issues)

    def test_corner_clause_is_one_st_consuming_none(self):
        from loopdreams_qa.stitch_parser import tokenize_round
        clauses = tokenize_round("sc in the gap at the other corner")
        self.assertEqual(len(clauses), 1)
        self.assertEqual((clauses[0].consumes, clauses[0].produces), (0, 1))


if __name__ == "__main__":
    unittest.main()

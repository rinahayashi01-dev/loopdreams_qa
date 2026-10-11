"""Celtic weave's crossed post trebles (loopdreams buildCelticWeaveRows,
2026-10-11). Before these, every texture row came back "cannot verify
stitch-count math" -- a Celtic pattern could never FAIL."""
import unittest

from loopdreams_qa.stitch_parser import tokenize_round

FRONT = ("Dc in first st, *skip next 2 sts, fptr around next 2 sts, working in front of the 2 sts just made, "
         "fptr around the 2 skipped sts; rep from * 3 more times, dc in last st")
BACK = ("Dc in first st, bpdc around next 2 sts, *skip next 2 sts, bptr around next 2 sts, working behind the "
        "2 sts just made, bptr around the 2 skipped sts; rep from * 2 more times, bpdc around next 2 sts, dc in last st")


def _by_raw(clauses, text):
    return next(c for c in clauses if c.raw.strip().lstrip("*").strip().lower() == text)


class TestCelticClauses(unittest.TestCase):
    def test_every_clause_is_recognised(self):
        for row in (FRONT, BACK):
            clauses = tokenize_round(row)
            unknown = [c.raw for c in clauses if c.unverifiable_reason]
            self.assertEqual(unknown, [], row)

    def test_skip_next_n_consumes_n(self):
        c = _by_raw(tokenize_round(FRONT), "skip next 2 sts")
        self.assertEqual((c.consumes, c.produces), (2, 0))

    def test_post_trebles_are_one_for_one(self):
        c = _by_raw(tokenize_round(FRONT), "fptr around next 2 sts")
        self.assertEqual((c.consumes, c.produces), (2, 2))

    # The skipped stitches were consumed by the skip; working them makes
    # stitches without using any more of the row below.
    def test_around_the_skipped_sts_consumes_nothing(self):
        c = _by_raw(tokenize_round(FRONT), "fptr around the 2 skipped sts")
        self.assertEqual((c.consumes, c.produces), (0, 2))
        c = _by_raw(tokenize_round(BACK), "bptr around the 2 skipped sts")
        self.assertEqual((c.consumes, c.produces), (0, 2))

    def test_crossing_direction_is_a_note(self):
        for row, text in ((FRONT, "working in front of the 2 sts just made"), (BACK, "working behind the 2 sts just made")):
            c = _by_raw(tokenize_round(row), text)
            self.assertEqual((c.clause_type, c.consumes, c.produces), ("note", 0, 0))

    # One repeat consumes 4 and makes 4, so a cross keeps the row's width.
    def test_a_cross_keeps_the_width(self):
        clauses = tokenize_round("skip next 2 sts, fptr around next 2 sts, working in front of the 2 sts just made, "
                                 "fptr around the 2 skipped sts")
        self.assertEqual(sum(c.consumes for c in clauses), 4)
        self.assertEqual(sum(c.produces for c in clauses), 4)


if __name__ == "__main__":
    unittest.main()

import unittest

from loopdreams_qa.stitch_parser import tokenize_round


class TestCornerClause(unittest.TestCase):
    def test_simple_stitch_corner_produces_count(self):
        # A plain stitch in a corner (every real sample seen so far, always
        # sc) has a fixed ratio, so the count-per-corner math is genuinely
        # knowable: "3 sc in corner" produces exactly 3 stitches.
        clauses = tokenize_round("3 sc in corner")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "corner")
        self.assertEqual(c.explicit_count, 3)
        self.assertFalse(c.is_compound)
        self.assertEqual(c.produces, 3)
        self.assertIsNone(c.unverifiable_reason)

    def test_compound_stitch_corner_is_unverifiable_not_guessed(self):
        # Real bug (never triggered by any real sample, every corner seen
        # so far is plain sc): a compound stitch in a corner used to
        # silently fall back to `(prod or 1) * count`, guessing 1 produced
        # stitch per repeat instead of leaving it unverifiable -- the only
        # place in the codebase that guessed instead of reporting "can't
        # verify" for a compound stitch. Must now leave produces unset and
        # carry a specific unverifiable_reason, exactly like every other
        # compound-stitch clause shape (each_st_across/around, etc.).
        clauses = tokenize_round("3 bo in corner", custom_compound=frozenset({"bo"}))
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.clause_type, "corner")
        self.assertEqual(c.explicit_count, 3)
        self.assertTrue(c.is_compound)
        self.assertIsNone(c.produces)
        self.assertIn("bo", c.unverifiable_reason)


if __name__ == "__main__":
    unittest.main()

import unittest

from loopdreams_qa.stitch_parser import tokenize_round


class TestDoNotFastenOff(unittest.TestCase):
    """loopdreams' double-layer potholder: Square 2 keeps its loop for the
    joining round, so its last row ends "Do not fasten off." That used to be an
    unrecognised clause, which left the row's stitch count unverifiable."""

    def test_is_a_no_op_note(self):
        clauses = tokenize_round("Sc in each st across. Do not fasten off.")
        kinds = [c.clause_type for c in clauses]
        self.assertNotIn("unknown", kinds)
        dnfo = [c for c in clauses if "not fasten" in c.raw.lower()]
        self.assertEqual(len(dnfo), 1)
        # The opposite of a fasten off: it must not count as finishing.
        self.assertEqual(dnfo[0].clause_type, "note")
        self.assertEqual((dnfo[0].consumes, dnfo[0].produces), (0, 0))

    def test_plain_fasten_off_unchanged(self):
        clauses = tokenize_round("Sc in each st across. Fasten off.")
        self.assertIn("fasten_off", [c.clause_type for c in clauses])


if __name__ == "__main__":
    unittest.main()

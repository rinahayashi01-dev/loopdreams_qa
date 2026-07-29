import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count
from loopdreams_qa.stitch_parser import tokenize_round

MATERIALS_BLOCK = """MATERIALS
Gauge: 16 sc x 8 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 5.0 mm
"""


def _pattern(pattern_steps: str):
    raw = (
        "Test Tote Bag\n"
        + MATERIALS_BLOCK
        + "ABBREVIATIONS\n"
        "ch = chain, sc = single crochet, rep = repeat\n"
        "PATTERN STEPS\n"
        + pattern_steps
    )
    return parse(raw)


class TestBoTokenRatio(unittest.TestCase):
    # Real abbreviation (Tote Bag advanced, loopdreams builders.ts
    # buildToteBagRows' isBobble branch, Jul 29 batch): "*bo in next st,
    # sc in next st; rep from * ..." -- "bo" is the generator's own hardcoded
    # bobble-stitch shorthand (5 incomplete dc pulled through together in
    # one st), never spelled out anywhere in the pattern's own abbreviation
    # key. Unlike shell/cluster/moss/etc., whose real construction varies
    # pattern to pattern, this is a fixed, always-the-same-construction
    # template abbreviation -- always exactly one previous-row stitch in,
    # one stitch out, the same as a plain dc replacing that stitch.
    def test_bo_has_a_one_to_one_ratio(self):
        clauses = tokenize_round("bo in next st")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.stitch, "bo")
        self.assertEqual(c.consumes, 1)
        self.assertEqual(c.produces, 1)
        self.assertFalse(c.is_compound)
        self.assertIsNone(c.unverifiable_reason)

    def test_bo_recognized_inside_a_repeat_group(self):
        clauses = tokenize_round("*bo in next st")
        self.assertEqual(len(clauses), 1)
        c = clauses[0]
        self.assertEqual(c.stitch, "bo")
        self.assertEqual(c.consumes, 1)
        self.assertEqual(c.produces, 1)

    def test_bo_never_defined_in_abbreviation_key_still_recognized(self):
        # The real generator never emits a "bo = bobble (...)" abbreviation-
        # key entry anywhere in the pattern text (confirmed against
        # loopdreams/supabase/functions/generate-pattern/index.ts and
        # builders.ts) -- so this must work with NO custom_compound tokens
        # supplied at all, unlike a pattern-defined compound stitch.
        clauses = tokenize_round("bo in next st", custom_compound=frozenset())
        self.assertEqual(clauses[0].consumes, 1)
        self.assertEqual(clauses[0].produces, 1)


class TestToteBagBobbleFullPattern(unittest.TestCase):
    # Real row shapes (Tote Bag advanced, loopdreams builders.ts
    # buildToteBagRows, Jul 29 batch): a 4-row repeat alternating a plain sc
    # row with a bobble row, the bobble row itself alternating which edge
    # width (1 st or 2 sts) opens/closes it across the 4-row cycle.
    def _raw(self):
        return (
            "Foundation: Ch 11.\n"
            "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (10 sts)\n"
            "Row 2: Sc in first st, *bo in next st, sc in next st; rep from * to last st, sc in last st. "
            "Ch 1, turn. (10 sts)\n"
            "Row 3: Sc in each st across. Ch 1, turn. (10 sts)\n"
            "Row 4: Sc in each of first 2 sts, *bo in next st, sc in next st; rep from * to last 2 sts, "
            "sc in each of last 2 sts. Fasten off. (10 sts)\n"
        )

    def test_full_pattern_verifies_clean(self):
        pattern = _pattern(self._raw())
        issues = stitch_count.check(pattern)
        self.assertEqual([i for i in issues if i.severity == "error"], [])

    def test_edge_width_one_bobble_row_verifies_clean(self):
        pattern = _pattern(self._raw())
        issues = stitch_count.check(pattern)
        row2_errors = [i for i in issues if i.location == "Row 2" and i.severity == "error"]
        self.assertEqual(row2_errors, [])

    def test_edge_width_two_bobble_row_verifies_clean(self):
        pattern = _pattern(self._raw())
        issues = stitch_count.check(pattern)
        row4_errors = [i for i in issues if i.location == "Row 4" and i.severity == "error"]
        self.assertEqual(row4_errors, [])

    def test_wrong_declared_count_still_caught(self):
        raw = self._raw().replace(
            "Row 2: Sc in first st, *bo in next st, sc in next st; rep from * to last st, sc in last st. "
            "Ch 1, turn. (10 sts)",
            "Row 2: Sc in first st, *bo in next st, sc in next st; rep from * to last st, sc in last st. "
            "Ch 1, turn. (99 sts)",
        )
        pattern = _pattern(raw)
        issues = stitch_count.check(pattern)
        row2_errors = [i for i in issues if i.location == "Row 2" and i.severity == "error"]
        self.assertEqual(len(row2_errors), 1)


if __name__ == "__main__":
    unittest.main()

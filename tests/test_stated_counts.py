"""Rows that state their own numbers are checked against them.

Three places where a row said everything needed to verify it, yet a wrong
number only reached REVIEW or passed outright. Found by mutating correct
loopdreams output one number at a time (loopdreams, 2026-09-27).
"""
import unittest
from types import SimpleNamespace

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count
from loopdreams_qa.stitch_parser import tokenize_round


def _scarf(chain, row1):
    return parse(
        "Test Scarf\nMATERIALS\nGauge: 14 sc x 16 rows = 4 in [10 cm]\nTerminology: US\n"
        "Yarn: Test yarn\nHook: 5.0 mm\nABBREVIATIONS\nch = chain, sc = single crochet\n"
        f"PATTERN STEPS\nFoundation: Ch {chain}, turn.\n"
        f"Row 1: {row1} Ch 1, turn. (10 sts)\n"
        "Row 2: Sc in each st across. Ch 1, turn. (10 sts)\n"
        "Finishing\nBorder: Fasten off. (10 sts)\n"
    )


def _row1(pattern):
    return [i for i in stitch_count.check(pattern) if i.location == "Row 1"]


SKIP = "Skip the first chain from the hook (it doesn't count as a stitch). "


class TestStatedSkipShortfall(unittest.TestCase):
    def test_correct_colour_row_passes(self):
        self.assertEqual(_row1(_scarf(11, SKIP + "With Colour 2, 4 sc in next 4 chs, "
                                      "changing to Colour 1 in the last st; 6 sc in next 6 chs.")), [])

    def test_a_run_one_short_is_an_error_when_the_skip_is_stated(self):
        # Used to be a warning ("no ordinal clause stating how many chains were
        # meant as a turning-chain equivalent") though the row states exactly that.
        issues = _row1(_scarf(11, SKIP + "With Colour 2, 3 sc in next 3 chs, "
                                  "changing to Colour 1 in the last st; 6 sc in next 6 chs."))
        self.assertTrue(any(i.severity == "error" for i in issues), issues)

    def test_without_a_stated_skip_the_shortfall_stays_a_warning(self):
        # The shawl case: nothing says how many chains were skipped, so a
        # shortfall of one may be the unstated convention. Unchanged.
        issues = _row1(_scarf(11, "4 sc in next 4 chs, 6 sc in next 6 chs."))
        self.assertTrue(issues)
        self.assertTrue(all(i.severity == "warning" for i in issues), issues)


class TestSelfContradictingRun(unittest.TestCase):
    def test_numbers_that_cannot_both_hold_are_an_error(self):
        issues = _row1(_scarf(11, SKIP + "With Colour 2, 5 sc in next 4 chs, "
                                  "changing to Colour 1 in the last st; 6 sc in next 6 chs."))
        errors = [i for i in issues if i.severity == "error"]
        self.assertTrue(errors, issues)
        self.assertIn("contradicts itself", errors[0].message)

    def test_a_clean_multiple_may_be_an_increase_and_stays_unverifiable(self):
        c = tokenize_round("6 sc in next 3 sts")[0]
        self.assertIsNone(c.contradiction)
        self.assertIsNotNone(c.unverifiable_reason)

    def test_equal_numbers_are_not_a_contradiction(self):
        self.assertIsNone(tokenize_round("5 sc in next 5 chs")[0].contradiction)


OVAL = ("Ch {ch}. Skip the first chain from the hook (it doesn't count as a stitch). "
        "Sc in the next chain and each of next {n} chs, 3 sc in last ch, working on the opposite side "
        "of the foundation chain: sc in each of next {m} chs, 3 sc in next ch. Place a stitch marker "
        "in the first st — work in a continuous spiral from here on, do not join or turn.")


def _oval(ch, n, m):
    row = SimpleNamespace(label="Round 1", clauses=tokenize_round(OVAL.format(ch=ch, n=n, m=m)))
    return stitch_count._check_oval_foundation(row)


class TestOvalFoundation(unittest.TestCase):
    def test_the_real_egg_adds_up(self):
        self.assertEqual(_oval(5, 2, 3), [])

    def test_a_chain_one_off_either_way_is_an_error(self):
        # The stitches alone still total 12 here, which is why this passed before.
        for ch in (4, 6):
            issues = _oval(ch, 2, 3)
            self.assertEqual(len(issues), 1, ch)
            self.assertEqual(issues[0].severity, "error")
            self.assertIn(f"Ch {ch}", issues[0].message)

    def test_the_second_side_must_match_the_first(self):
        self.assertTrue(_oval(5, 2, 2))
        self.assertTrue(_oval(5, 2, 4))

    def test_not_an_oval_is_left_alone(self):
        row = SimpleNamespace(label="Round 1", clauses=tokenize_round(
            "Ch 5. Skip the first chain from the hook (it doesn't count as a stitch). "
            "Sc in the next chain and each of next 2 chs, 3 sc in last ch."))
        self.assertEqual(stitch_count._check_oval_foundation(row), [])


if __name__ == "__main__":
    unittest.main()

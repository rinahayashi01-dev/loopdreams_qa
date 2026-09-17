import unittest

from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.checks import stitch_count

MATERIALS_BLOCK = """MATERIALS
Gauge: 18 sc x 20 rows = 4 in [10 cm]
Terminology: US
Yarn: Test yarn
Hook: 4.0 mm
"""


def _row2_issues(row2_text):
    raw = (
        "Test Blanket\n"
        + MATERIALS_BLOCK
        + "ABBREVIATIONS\n"
        "ch = chain, sc = single crochet, dc = double crochet, rep = repeat\n"
        "PATTERN STEPS\n"
        "Foundation:Ch 21, turn.\n"
        "Row 1: Sc in 2nd ch from hook and in each ch across. Ch 1, turn. (20 sts)\n"
        f"Row 2: {row2_text} Ch 1, turn. (20 sts)\n"
        "Finishing\n"
        "Border: Fasten off. (40 sts)\n"
    )
    pattern = parse(raw)
    issues = stitch_count.check(pattern)
    return [i for i in issues if i.location == "Row 2"]


class TestMultipleRepeatGroupsPerRow(unittest.TestCase):
    def test_single_repeat_group_still_verifies_normally(self):
        # Sanity check: the ordinary single-repeat-group shape must still
        # resolve cleanly (20 sts in, 20 repeats of a 1-in/1-out unit, 20
        # sts declared) -- no regression from the multi-group guard below.
        issues = _row2_issues("*Sc in next st; rep from *.")
        self.assertEqual(issues, [])

    def test_two_repeat_groups_in_one_row_flagged_not_silently_wrong(self):
        # Real gap found while reviewing the "single repeat group per row"
        # V1 limitation documented in ARCHITECTURE.md since the very first
        # version of this tool: a SECOND '*...rep from *' group in the same
        # row was never actually detected anywhere. _check_repeat_group
        # only locates the FIRST opener/closer pair and treats everything
        # after the first closer as flat, one-time "post" content --
        # _zone_sum skips repeat_close clauses entirely as no-ops rather
        # than flagging them, so a second group's own opener/body/closer
        # would silently get summed as if it occurred exactly once. With
        # the right declared counts (as constructed here: 19 reps of the
        # first group + 1 occurrence of the second happens to total 20),
        # this used to return a confident, clean PASS with no warning at
        # all -- numerically self-consistent, but meaningless, since the
        # second group was never actually verified as a repeat construct.
        # Must now be caught and flagged instead.
        #
        # Neither group here states how many times it is worked ("rep from *"
        # means "to the end"), so it stays unverifiable — two groups and one
        # equation. The message now names that reason specifically rather than
        # the old blanket "only one repeat group is supported", because rows
        # that DO state their counts are verified; see the tests below.
        issues = _row2_issues("*Sc in next st; rep from *. *Dc in next st; rep from *.")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "warning")
        self.assertIn("does not state how many times", issues[0].message)

    def test_two_counted_repeat_groups_are_verified(self):
        # What the counts make possible. 20 sts in: 12 reps of a 1-in/1-out
        # unit then 8 of another is 20 consumed and 20 produced, which is what
        # the row declares. Previously this was waved through as unverifiable.
        issues = _row2_issues(
            "*Sc in next st; rep from * 11 more times. *Dc in next st; rep from * 7 more times.")
        self.assertEqual(issues, [])

    def test_two_counted_groups_that_do_not_add_up_are_an_error(self):
        # The point of reading the counts is to be able to contradict them.
        # 12 + 4 = 16 stitches worked out of the 20 the previous row leaves.
        issues = _row2_issues(
            "*Sc in next st; rep from * 11 more times. *Dc in next st; rep from * 3 more times.")
        self.assertTrue(issues, "an under-worked row should be reported")
        self.assertEqual(issues[0].severity, "error")
        self.assertIn("consume 16 stitches", issues[0].message)

    def test_a_counted_group_beside_an_uncounted_one_stays_unverified(self):
        # Partial information is not enough, and guessing the missing half is
        # exactly the failure this tool exists to avoid.
        issues = _row2_issues(
            "*Sc in next st; rep from * 11 more times. *Dc in next st; rep from *.")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "warning")
        self.assertIn("does not state how many times", issues[0].message)


if __name__ == "__main__":
    unittest.main()

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
        issues = _row2_issues("*Sc in next st; rep from *. *Dc in next st; rep from *.")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].severity, "warning")
        self.assertIn("more than one repeat group", issues[0].message)


if __name__ == "__main__":
    unittest.main()

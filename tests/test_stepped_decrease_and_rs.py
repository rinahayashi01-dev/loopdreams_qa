"""A textured fabric (sedge, moss/linen) is shaped a whole pattern repeat at a
time: the row stops N sts short, "leaving the last N sts unworked", and turns.
And a shaped piece names its right side on its first row. Both first used by
loopdreams' V-neck cardigan in a compound stitch (2026-09-26)."""
import unittest

from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse
from loopdreams_qa.stitch_parser import tokenize_round
from loopdreams_qa.checks import stitch_count

BASE = {
    "title": "Moss front", "gauge_sts_per_in": 4, "gauge_rows_per_in": 4,
    "yarn_weight_name": "Medium", "hook_label": "5.0 mm",
    "abbreviations": [{"abbr": "sc", "definition": "single crochet"}, {"abbr": "ch", "definition": "chain"}],
}
MOSS = "Sc in first st, *ch 1, sc in next ch-1 sp, skip next st; rep from * {n} more times"


def _rows(step_text, step_count=9, after_count=9):
    return [
        {"row_number": 1, "stitch_count": 11, "instructions": "Foundation: Ch 12, turn.", "section": None},
        {"row_number": 2, "stitch_count": 11, "instructions": "Skip the first 1 chain from the hook (it doesn't count as a stitch). Sc in the next chain and in each ch across. Ch 1, turn.", "section": None},
        {"row_number": 3, "stitch_count": 11, "instructions": "Sc in first st, *ch 1, skip 1 st, sc in next st; rep from * 4 more times. Ch 1, turn.", "section": None},
        {"row_number": 4, "stitch_count": step_count, "instructions": step_text, "section": None},
        {"row_number": 5, "stitch_count": after_count, "instructions": MOSS.format(n=3) + f". Fasten off, weave in ends. ({after_count} sts)", "section": None},
    ]


def _errors(rows):
    return [i for i in stitch_count.check(parse(build_raw_text({**BASE, "rows": rows}))) if i.severity == "error"]


def _warnings(rows):
    return [i for i in stitch_count.check(parse(build_raw_text({**BASE, "rows": rows}))) if i.severity == "warning"]


class TestLeaveUnworked(unittest.TestCase):
    def test_clause_consumes_the_stitches_and_makes_none(self):
        for text, n in [("leaving the last 3 sts unworked", 3), ("Leave the last 2 sts unworked", 2)]:
            [c] = tokenize_round(text)
            self.assertEqual((c.clause_type, c.consumes, c.produces), ("skip", n, 0), text)

    def test_a_stepped_moss_row_verifies(self):
        step = "Decrease row: " + MOSS.format(n=3) + ", leaving the last 2 sts unworked. Ch 1, turn. (9 sts)"
        rows = _rows(step)
        self.assertEqual(_errors(rows), [])
        self.assertEqual(_warnings(rows), [])

    def test_a_wrong_count_on_the_step_is_caught(self):
        step = "Decrease row: " + MOSS.format(n=3) + ", leaving the last 2 sts unworked. Ch 1, turn. (10 sts)"
        self.assertTrue(_errors(_rows(step, step_count=10)))

    def test_dropping_the_leave_clause_is_caught(self):
        # Without it the row no longer accounts for the 2 sts it stops short of.
        step = "Decrease row: " + MOSS.format(n=3) + ". Ch 1, turn. (9 sts)"
        self.assertTrue(_errors(_rows(step)))


class TestRightSideDesignation(unittest.TestCase):
    def test_naming_and_marking_the_rs_is_a_no_op(self):
        text = "The side facing you as you work this row is the right side (RS); clip a marker to it"
        for c in tokenize_round(text):
            self.assertEqual((c.consumes, c.produces), (0, 0), c.raw)

    def test_it_does_not_cost_a_row_its_verification(self):
        rows = _rows("Decrease row: " + MOSS.format(n=3) + ", leaving the last 2 sts unworked. Ch 1, turn. (9 sts)")
        rows[2] = {**rows[2], "instructions": rows[2]["instructions"].replace(
            ". Ch 1, turn.", ". The side facing you as you work this row is the right side (RS); clip a marker to it. Ch 1, turn.")}
        self.assertEqual(_warnings(rows), [])
        self.assertEqual(_errors(rows), [])


if __name__ == "__main__":
    unittest.main()

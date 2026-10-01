"""A scarf's "Fringe:"/"Tassels:" rows are finishing, not numbered pattern rows.

loopdreams labels a fringed or tasselled scarf's two sc rows and its final
fringe/tassel step "Fringe: ..."/"Tassels: ...". _FINISHING_ROW_RE didn't
know either label, so the backward walk that collects the trailing finishing
rows stopped at the last row: nothing was collected, the Border round before
it (when there is one) was stranded as a numbered row, and every fringed or
tasselled scarf FAILed "No Finishing/assembly section found."

Fixture: real generator output (buildScarfRows, dc, 2 x 5 in), copied verbatim
from loopdreams fix/scarf-fringe-before-border, where the sc rows come before
the border.
"""
import json
import os
import unittest

from loopdreams_qa.cli import run_for_pattern
from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse

_FIXTURE = os.path.join(os.path.dirname(__file__), "data", "scarf_fringe_tassels.json")


def _report(rows):
    payload = {"title": "Test Scarf", "gauge_sts_per_in": 4, "gauge_rows_per_in": 2,
               "yarn_weight_name": "Medium", "hook_label": "5.0 mm", "abbreviations": [],
               "rows": [{**r, "section": None} for r in rows]}
    return run_for_pattern(parse(build_raw_text(payload)), quiet=True)


def _messages(report):
    return [i["message"] for issues in report["issues"].values() for i in issues]


class TestFringeTasselsAreFinishing(unittest.TestCase):
    def setUp(self):
        with open(_FIXTURE) as f:
            self.cases = json.load(f)

    def test_no_missing_finishing_error(self):
        for name, rows in self.cases.items():
            with self.subTest(name):
                report = _report(rows)
                self.assertNotIn("No Finishing/assembly section found.", _messages(report))
                self.assertNotEqual(report["summary"]["status"], "FAIL")

    def test_border_between_sc_rows_and_fringe_is_not_a_numbered_row(self):
        report = _report(self.cases["fringe_sc_border"])
        stranded = [m for m in _messages(report) if "is numbered as a pattern row" in m]
        self.assertEqual(stranded, [])

    def test_body_is_still_checked(self):
        # The labels must not swallow the body: a miscounted body row still fails.
        rows = json.loads(json.dumps(self.cases["fringe_sc_border"]))
        rows[3]["stitch_count"] += 1
        self.assertEqual(_report(rows)["summary"]["status"], "FAIL")

    def test_unlabelled_last_row_still_needs_finishing(self):
        # Only the labels are finishing: an unlabelled closing step is not.
        rows = json.loads(json.dumps(self.cases["fringe_no_border"]))
        for r in rows[-3:]:
            r["instructions"] = r["instructions"].replace("Fringe: ", "", 1)
        rows = rows[:-1]  # last remaining row is a plain sc row ending "Fasten off."
        rows[-1]["instructions"] = rows[-1]["instructions"].replace(" Fasten off.", "")
        self.assertIn("No Finishing/assembly section found.", _messages(_report(rows)))


if __name__ == "__main__":
    unittest.main()

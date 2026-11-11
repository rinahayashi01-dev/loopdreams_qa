"""A fringed or tasselled scarf's end-prep sc rows are checked, not skipped.

loopdreams buildScarfEdgeScRow writes an sc row across each short end before
the border: the first end into the unused loops of the foundation chain, the
second into the last row, each "(N sc ...)" and "(N sts)". Finishing had no
Fringe/Tassels label, so both rows fell into one unlabelled chunk full of
prose the tokenizer didn't know, and every such scarf was REVIEW. Each row is
now its own chunk, read only in the generator's exact shape, and checked as
one sc in each st of the edge it names.

Fixture: buildScarfRows / buildScarfCompoundRows output on loopdreams main
(2026-11-11), copied verbatim.
"""
import copy
import json
import os
import unittest

from loopdreams_qa.cli import run_for_pattern
from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse

_FIXTURE = os.path.join(os.path.dirname(__file__), "data", "scarf_end_prep_rows.json")


def _report(rows):
    payload = {"title": "Test Scarf", "gauge_sts_per_in": 4, "gauge_rows_per_in": 4,
               "yarn_weight_name": "Medium", "hook_label": "5.0 mm", "abbreviations": [],
               "rows": [{**r, "section": None} for r in rows]}
    return run_for_pattern(parse(build_raw_text(payload)), quiet=True)


def _issues(report):
    return [i for issues in report["issues"].values() for i in issues if i["severity"] != "info"]


def _prep_indexes(rows):
    return [i for i, r in enumerate(rows) if "Prepare the" in r["instructions"]]


class EndPrepRowsTest(unittest.TestCase):
    def setUp(self):
        with open(_FIXTURE) as f:
            self.cases = json.load(f)

    def test_every_case_passes(self):
        for name, rows in self.cases.items():
            with self.subTest(name):
                report = _report(rows)
                self.assertEqual(report["summary"]["status"], "PASS", _issues(report))

    def test_both_rows_are_checked_rows(self):
        rows = self.cases["fringe_sc_border"]
        payload = {"title": "t", "abbreviations": [], "rows": [{**r, "section": None} for r in rows]}
        labels = [r.label for r in parse(build_raw_text(payload)).rows]
        self.assertIn("Fringe prep, first end", labels)
        self.assertIn("Fringe prep, second end", labels)

    def test_a_miscount_on_either_end_fails(self):
        for name, rows in self.cases.items():
            for end, i in enumerate(_prep_indexes(rows), 1):
                for delta in (-1, 1):
                    with self.subTest(name=name, end=end, delta=delta):
                        bad = copy.deepcopy(rows)
                        n = bad[i]["stitch_count"]
                        bad[i]["stitch_count"] = n + delta
                        bad[i]["instructions"] = bad[i]["instructions"].replace(f"({n} sc", f"({n + delta} sc")
                        self.assertEqual(_report(bad)["summary"]["status"], "FAIL")

    def test_the_two_stated_counts_must_agree(self):
        rows = copy.deepcopy(self.cases["tassels_dc_crab_rounded"])
        i = _prep_indexes(rows)[1]
        n = rows[i]["stitch_count"]
        rows[i]["instructions"] = rows[i]["instructions"].replace(f"({n} sc", f"({n - 1} sc")
        report = _report(rows)
        self.assertEqual(report["summary"]["status"], "FAIL")
        self.assertTrue(any("two different counts" in i["message"] for i in _issues(report)))

    def test_the_first_end_is_checked_against_row_1(self):
        # The first end goes along the foundation edge, under Row 1.
        report = _report(_with_count(self.cases["fringe_shell_no_border"], 0, +1))
        msgs = [i["message"] for i in _issues(report)]
        self.assertTrue(any("Row 1 (worked along its foundation edge)" in m for m in msgs), msgs)

    def test_a_reworded_row_is_left_unverified_not_guessed(self):
        # Only the generator's own shape is read. Anything else stays a
        # warning, never a confident count.
        rows = copy.deepcopy(self.cases["fringe_sc_border"])
        i = _prep_indexes(rows)[1]
        rows[i]["instructions"] = rows[i]["instructions"].replace(
            "Sc in the same st and in each st across", "Sc evenly across")
        report = _report(rows)
        self.assertEqual(report["summary"]["status"], "REVIEW", _issues(report))

    def test_the_wrong_edge_for_the_end_is_not_read(self):
        # A "first end" that joins to the final row isn't the generator's
        # shape: abstain rather than check it against the wrong row.
        rows = copy.deepcopy(self.cases["fringe_sc_border"])
        first, second = _prep_indexes(rows)
        rows[second]["instructions"] = rows[second]["instructions"].replace("second end", "first end")
        self.assertNotEqual(_report(rows)["summary"]["status"], "PASS")


def _with_count(rows, which, delta):
    bad = copy.deepcopy(rows)
    i = _prep_indexes(bad)[which]
    n = bad[i]["stitch_count"]
    bad[i]["stitch_count"] = n + delta
    bad[i]["instructions"] = bad[i]["instructions"].replace(f"({n} sc", f"({n + delta} sc")
    return bad


if __name__ == "__main__":
    unittest.main()

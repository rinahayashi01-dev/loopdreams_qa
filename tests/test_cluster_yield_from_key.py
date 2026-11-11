"""A named stitch's yield is read from the pattern's own key.

KNOWN_UNVERIFIABLE.md §1: the Granny Square motif's Rounds 3 and 4 abstained
because "cluster" is a compound word with no fixed ratio. The motif's key
defines it as "2 dc worked together in the same space", which is a joined
cluster: one place in, one stitch out, and the rounds say "(16 Clusters, ...)".
That is read from the key, never assumed for the word. A key that doesn't say
the stitches are worked together in one place still abstains.

Fixture: buildBasicMotifRows(12, 12) and its deriveLegendEntries key on
loopdreams main (2026-11-11), copied verbatim.
"""
import copy
import json
import os
import unittest

from loopdreams_qa import abbreviations as ab
from loopdreams_qa.cli import run_for_pattern
from loopdreams_qa.from_pattern_json import build_raw_text
from loopdreams_qa.pattern_parser import parse

_FIXTURE = os.path.join(os.path.dirname(__file__), "data", "granny_motif_cluster.json")


def _report(case):
    payload = {"title": "Granny Square Blanket", "gauge_sts_per_in": 4, "gauge_rows_per_in": 2,
               "yarn_weight_name": "Medium", "hook_label": "5.0 mm",
               "abbreviations": case["abbreviations"],
               "rows": [{**r, "section": None} for r in case["rows"]]}
    return run_for_pattern(parse(build_raw_text(payload)), quiet=True)


def _issues(report):
    return [i for issues in report["issues"].values() for i in issues if i["severity"] != "info"]


class OneStitchTokensTest(unittest.TestCase):
    def test_joined_in_one_place(self):
        key = {"cluster": "cluster (2 dc worked together in the same space: ...)"}
        self.assertEqual(ab.one_stitch_tokens(key), frozenset({"cluster"}))

    def test_not_said_to_be_worked_together(self):
        # A granny "cluster" of 3 separate dc is three stitches.
        self.assertEqual(ab.one_stitch_tokens({"cluster": "cluster (3 dc in the same space)"}), frozenset())

    def test_worked_together_over_several_stitches(self):
        # That's a decrease: it uses up more than one place.
        key = {"cluster": "cluster (2 dc worked together over the next 2 sts)"}
        self.assertEqual(ab.one_stitch_tokens(key), frozenset())

    def test_only_named_stitches(self):
        # A plain stitch's own definition is never re-read.
        self.assertEqual(ab.one_stitch_tokens({"dc": "double crochet worked together in the same st"}),
                         frozenset())


class GrannyClusterRoundsTest(unittest.TestCase):
    def setUp(self):
        with open(_FIXTURE) as f:
            self.case = json.load(f)

    def _mutated(self, round_no, old, new, count=None):
        case = copy.deepcopy(self.case)
        row = case["rows"][round_no - 1]
        self.assertIn(old, row["instructions"])
        row["instructions"] = row["instructions"].replace(old, new)
        if count is not None:
            row["stitch_count"] = count
        return case

    def test_the_pattern_passes(self):
        report = _report(self.case)
        self.assertEqual(report["summary"]["status"], "PASS", _issues(report))

    def test_a_wrong_count_fails(self):
        for case in (self._mutated(3, "(16 Clusters, 16 ch-1 sps)", "(17 Clusters, 17 ch-1 sps)", 17),
                     self._mutated(4, "(24 Clusters, 24 ch-1 sps)", "(23 Clusters, 23 ch-1 sps)", 23)):
            with self.subTest():
                self.assertEqual(_report(case)["summary"]["status"], "FAIL")

    def test_a_wrong_repeat_fails(self):
        for case in (self._mutated(3, "14 more times", "13 more times"),
                     self._mutated(4, "6 more times", "5 more times")):
            with self.subTest():
                self.assertEqual(_report(case)["summary"]["status"], "FAIL")

    def test_without_the_key_saying_so_it_still_abstains(self):
        case = copy.deepcopy(self.case)
        for a in case["abbreviations"]:
            if a["abbr"] == "cluster":
                a["definition"] = "cluster (3 dc in the same space)"
        report = _report(case)
        self.assertEqual(report["summary"]["status"], "REVIEW")
        self.assertTrue(any("'cluster' has no fixed" in i["message"] for i in _issues(report)))


if __name__ == "__main__":
    unittest.main()

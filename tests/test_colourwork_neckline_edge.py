"""A cardigan V-neck Front carrying a design, with its neckline edge TIDIED:
where the V cuts the design down to a sliver at the centre-front edge, the edge
run takes its inward neighbour's colour (loopdreams tidyNeckEdge, the default
since 2026-09-27; "keep" leaves the cut design as it is). The pattern JSON says
which with `neckline_edge`; absent means keep, as every earlier pattern did.

The fixtures are real generator output (buildCardiganRows, chest 20, V-neck,
design on the Fronts only, through applyGarmentPanelColourwork) for the three
sampling paths: sedge (resampled straight to cluster columns), moss (per real
sc) and sc (per stitch). Each was generated both ways from the same design."""
import json
import os
import unittest

from loopdreams_qa.checks import colourwork_orientation as co
from loopdreams_qa import from_pattern_json as fpj

A, B = "#C9A227", "#4F7942"
with open(os.path.join(os.path.dirname(__file__), "data", "neckline_edge_fronts.json")) as f:
    FX = json.load(f)
DESIGN = [[A if c == "A" else B for c in row] for row in FX["F"]]


def colour_issues(rows, edge):
    payload = {"title": "t", "gauge_sts_per_in": 4, "gauge_rows_per_in": 3, "yarn_weight_name": "x",
               "hook_label": "x", "abbreviations": [], "palette": [A, B], "design_grid": DESIGN, "rows": rows}
    if edge is not None:
        payload["neckline_edge"] = edge
    # The same steps as from_pattern_json.main().
    pattern = fpj.parse(fpj.build_raw_text(payload))
    pattern.design_grid = payload["design_grid"]
    pattern.design_palette = payload["palette"]
    pattern.neckline_edge = payload.get("neckline_edge")
    pattern.design_rows = payload["rows"]
    return [i for i in co.check(pattern) if i.severity in ("error", "warning")]


class TidyNeckEdgeRule(unittest.TestCase):
    """The rule itself, case for case with loopdreams' tidyNeckEdge tests."""

    def test_plain_sliver_folds_into_neighbour(self):
        self.assertEqual(co._tidy_neck_edge(["A", "A", "A", "B", "B"], True, 3), ["A"] * 5)
        self.assertEqual(co._tidy_neck_edge(["B", "A", "A", "A"], False, 3), ["A"] * 4)

    def test_three_wide_is_not_a_sliver(self):
        self.assertEqual(co._tidy_neck_edge(["A", "B", "B", "B"], True, 3), ["A", "B", "B", "B"])

    def test_only_the_neck_end_is_touched(self):
        self.assertEqual(co._tidy_neck_edge(["B", "A", "A", "A"], True, 3), ["B", "A", "A", "A"])

    def test_textured_single_position(self):
        self.assertEqual(co._tidy_neck_edge(["A", "A", "B"], True, 2), ["A", "A", "A"])
        self.assertEqual(co._tidy_neck_edge(["A", "B", "B"], True, 2), ["A", "B", "B"])

    def test_one_run_and_two_slivers(self):
        self.assertEqual(co._tidy_neck_edge(["A", "A"], True, 3), ["A", "A"])
        self.assertEqual(co._tidy_neck_edge(["A", "B", "C"], True, 3), ["A", "B", "B"])


class NecklineEdgeFronts(unittest.TestCase):
    def test_each_setting_passes_its_own_output(self):
        for kind in ("sedge", "moss", "sc"):
            with self.subTest(kind=kind):
                self.assertEqual(colour_issues(FX[f"{kind}_tidy"], "tidy"), [])
                self.assertEqual(colour_issues(FX[f"{kind}_keep"], "keep"), [])

    def test_absent_means_keep(self):
        for kind in ("sedge", "moss", "sc"):
            with self.subTest(kind=kind):
                self.assertEqual(colour_issues(FX[f"{kind}_keep"], None), [])
                self.assertTrue(colour_issues(FX[f"{kind}_tidy"], None))

    def test_the_wrong_setting_fails(self):
        # Tidy really is checked: a tidied Front judged as kept, or a kept one
        # judged as tidied, is a different fabric from the design.
        for kind in ("sedge", "moss", "sc"):
            with self.subTest(kind=kind):
                self.assertTrue(any(i.severity == "error" for i in colour_issues(FX[f"{kind}_tidy"], "keep")))
                self.assertTrue(any(i.severity == "error" for i in colour_issues(FX[f"{kind}_keep"], "tidy")))

    def test_the_fixtures_differ(self):
        for kind in ("sedge", "moss", "sc"):
            with self.subTest(kind=kind):
                self.assertNotEqual(FX[f"{kind}_tidy"], FX[f"{kind}_keep"])


if __name__ == "__main__":
    unittest.main()

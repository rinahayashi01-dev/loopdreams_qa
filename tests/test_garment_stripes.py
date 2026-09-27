"""Stripes on a sweater or cardigan (loopdreams, 2026-09-27). Each body panel is
coloured from its OWN stripe grid at its exact stitch x row size
(garmentStripePanels), sent as `design_panels` and used here in place of a
slice of design_grid.

The fixtures are real generator output with 3-colour vertical stripes, which
change colour nearly every stitch: a moss cardigan (V-neck, tidied edge) and a
dc sweater. Grids are stored as palette-index strings to keep the file small."""
import copy
import json
import os
import unittest

from loopdreams_qa import from_pattern_json as fpj
from loopdreams_qa.checks import colourwork_orientation as co
from loopdreams_qa.checks import completeness

with open(os.path.join(os.path.dirname(__file__), "data", "garment_stripes.json")) as f:
    FX = json.load(f)
PAL = FX["palette"]


def _panels(case):
    return {s: [[PAL[int(ch)] for ch in row] for row in g] for s, g in FX[case]["design_panels"].items()}


def issues(case, panels=None, rows=None, check=co.check):
    panels = panels or _panels(case)
    payload = {"title": case, "gauge_sts_per_in": 4, "gauge_rows_per_in": 3, "yarn_weight_name": "x",
               "hook_label": "x", "abbreviations": [], "palette": PAL, "design_grid": panels["Back"],
               "rows": rows or FX[case]["rows"]}
    pattern = fpj.parse(fpj.build_raw_text(payload))
    pattern.design_grid = payload["design_grid"]
    pattern.design_palette = PAL
    pattern.neckline_edge = FX[case].get("neckline_edge")
    pattern.design_panels = panels
    pattern.design_rows = payload["rows"]
    return [i for i in check(pattern) if i.severity in ("error", "warning")]


class GarmentStripes(unittest.TestCase):
    def test_each_panel_matches_its_own_stripes(self):
        for case in ("cardigan_moss", "sweater_dc"):
            with self.subTest(case=case):
                self.assertEqual(issues(case), [])

    def test_panels_are_not_a_slice_of_the_back(self):
        # Without design_panels the Fronts would be judged against halves of
        # the Back's stripes, which start from a different seam.
        case = "cardigan_moss"
        pattern_panels = _panels(case)
        self.assertNotEqual(pattern_panels["Right Front"], [r[:len(r) // 2] for r in pattern_panels["Back"]])

    def test_swapped_fronts_fail(self):
        panels = _panels("cardigan_moss")
        self.assertNotEqual(panels["Right Front"], panels["Left Front"])
        panels["Right Front"], panels["Left Front"] = panels["Left Front"], panels["Right Front"]
        self.assertTrue(any(i.severity == "error" for i in issues("cardigan_moss", panels=panels)))

    def test_a_wrong_colour_fails(self):
        rows = copy.deepcopy(FX["sweater_dc"]["rows"])
        i = next(k for k, r in enumerate(rows) if r["section"] == "Front" and "changing to Colour 2" in r["instructions"])
        rows[i]["instructions"] = rows[i]["instructions"].replace("changing to Colour 2", "changing to Colour 3", 1)
        self.assertTrue(any(i.severity == "error" for i in issues("sweater_dc", rows=rows)))


class MossRowWithoutARepeat(unittest.TestCase):
    """A coloured moss row whose colour changes every repeat has no
    "rep from *" left: each (ch 1, sc) unit is written out once. Its ch-1
    spaces still count toward the row total, as they do inside a repeat."""

    def _row_issues(self, text, declared):
        payload = {"title": "t", "gauge_sts_per_in": 4, "gauge_rows_per_in": 4, "yarn_weight_name": "x",
                   "hook_label": "x", "abbreviations": [], "rows": [
                       {"row_number": 1, "stitch_count": 5, "instructions": "Foundation: Ch 6, turn.", "section": "Back"},
                       {"row_number": 2, "stitch_count": 5, "instructions": "Skip the first 1 chain from the hook (it doesn't count as a stitch). Sc in next 5 chs. Ch 1, turn.", "section": "Back"},
                       {"row_number": 3, "stitch_count": declared, "instructions": text, "section": "Back"}]}
        pattern = fpj.parse(fpj.build_raw_text(payload))
        from loopdreams_qa.checks import stitch_count
        return [i for i in stitch_count.check(pattern) if i.location == "Row 2" and i.severity == "error"]

    ROW = ("With Colour 1, Sc in first st, changing to Colour 2 in the last st; ch 1, skip 1 st, sc in next st, "
           "changing to Colour 1 in the last st; ch 1, skip 1 st, sc in next st. Ch 1, turn.")

    def test_units_written_out_count_their_chains(self):
        self.assertEqual(self._row_issues(self.ROW, 5), [])

    def test_a_wrong_declared_count_still_fails(self):
        self.assertTrue(self._row_issues(self.ROW, 6))
        # 3 is the plain reading (chains not counted), which main already accepts;
        # 4 matches neither reading.
        self.assertTrue(self._row_issues(self.ROW, 4))


class ColourNameIsAProperNoun(unittest.TestCase):
    def _warnings(self, text):
        class P:  # the check reads raw_text only
            raw_text = text
        return completeness._check_colour_naming_consistency(P())

    def test_instruction_after_a_dash_is_not_a_name(self):
        text = ("skip first st (the chain already 'fills' that slot in Colour 1 — pick up Colour 2 for the next st); "
                "skip first st (the chain already 'fills' that slot in Colour 2 — pick up Colour 1 for the next st)")
        self.assertEqual(self._warnings(text), [])

    def test_a_real_name_under_two_identifiers_still_warns(self):
        self.assertTrue(self._warnings("Colour 2 — Moss ... Colour B — Moss"))


if __name__ == "__main__":
    unittest.main()
